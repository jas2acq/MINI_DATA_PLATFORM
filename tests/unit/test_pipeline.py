"""Unit tests for ETL pipeline orchestrator."""

from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest
from minio.error import S3Error

from dags.src.pipeline import run_pipeline, save_invalid_data_to_quarantine


def test_save_invalid_data_to_quarantine_success(mock_minio_client, sample_invalid_data):
    """Test successful quarantine of invalid records."""
    sample_invalid_data["validation_error"] = "Invalid data"

    save_invalid_data_to_quarantine(mock_minio_client, sample_invalid_data, "raw/test.csv")

    mock_minio_client.put_object.assert_called_once()
    args = mock_minio_client.put_object.call_args
    assert args[0][0] == "data-platform"
    assert args[0][1] == "quarantine/test.csv"


def test_save_invalid_data_to_quarantine_empty_dataframe(mock_minio_client):
    """Test quarantine with empty DataFrame."""
    empty_df = pd.DataFrame()

    save_invalid_data_to_quarantine(mock_minio_client, empty_df, "raw/test.csv")

    # Should not attempt to upload
    mock_minio_client.put_object.assert_not_called()


def test_save_invalid_data_to_quarantine_s3_error(mock_minio_client, sample_invalid_data):
    """Test quarantine with S3 upload error."""
    sample_invalid_data["validation_error"] = "Invalid data"
    mock_response = Mock()
    mock_response.status = 500
    mock_minio_client.put_object.side_effect = S3Error(
        response=mock_response,
        code="UploadError",
        message="Upload failed",
        resource="quarantine/test.csv",
        request_id="req123",
        host_id="host456",
    )

    with pytest.raises(S3Error):
        save_invalid_data_to_quarantine(mock_minio_client, sample_invalid_data, "raw/test.csv")


def test_run_pipeline_success_single_dataframe(sample_sales_data):
    """Test successful pipeline execution with single DataFrame."""
    # Mock all dependencies
    with patch("dags.src.pipeline.get_vault_client") as mock_vault:
        with patch("dags.src.pipeline.get_minio_client") as mock_minio:
            with patch("dags.src.pipeline.get_object_size") as mock_size:
                with patch("dags.src.pipeline.get_raw_data") as mock_get_data:
                    with patch("dags.src.pipeline.validate_data") as mock_validate:
                        with patch("dags.src.pipeline.transform_sales_data") as mock_transform:
                            with patch("dags.src.pipeline.upsert_data") as mock_upsert:
                                with patch("dags.src.pipeline.move_processed_file") as mock_move:
                                    # Setup mocks
                                    mock_vault.return_value = MagicMock()
                                    mock_minio_instance = MagicMock()
                                    mock_minio.return_value = mock_minio_instance
                                    mock_size.return_value = 1024  # Small file
                                    mock_get_data.return_value = sample_sales_data

                                    # Valid data, no invalid data
                                    mock_validate.return_value = (
                                        sample_sales_data,
                                        pd.DataFrame(),
                                    )
                                    mock_transform.return_value = sample_sales_data
                                    mock_move.return_value = "processed/test.csv"

                                    # Run pipeline
                                    run_pipeline("raw/test.csv")

                                    # Verify all steps called
                                    mock_vault.assert_called_once()
                                    mock_minio.assert_called_once()
                                    mock_size.assert_called_once_with(
                                        mock_minio_instance, "raw/test.csv"
                                    )
                                    mock_get_data.assert_called_once()
                                    mock_validate.assert_called_once()
                                    mock_transform.assert_called_once()
                                    mock_upsert.assert_called_once()
                                    mock_move.assert_called_once()


def test_run_pipeline_with_invalid_records(sample_sales_data, sample_invalid_data):
    """Test pipeline with both valid and invalid records."""
    with patch("dags.src.pipeline.get_vault_client") as mock_vault:
        with patch("dags.src.pipeline.get_minio_client") as mock_minio:
            with patch("dags.src.pipeline.get_object_size") as mock_size:
                with patch("dags.src.pipeline.get_raw_data") as mock_get_data:
                    with patch("dags.src.pipeline.validate_data") as mock_validate:
                        with patch("dags.src.pipeline.transform_sales_data") as mock_transform:
                            with patch("dags.src.pipeline.upsert_data"):
                                with patch("dags.src.pipeline.move_processed_file") as mock_move:
                                    with patch(
                                        "dags.src.pipeline.save_invalid_data_to_quarantine"
                                    ) as mock_quarantine:
                                        # Setup mocks
                                        mock_vault.return_value = MagicMock()
                                        mock_minio.return_value = MagicMock()
                                        mock_size.return_value = 1024
                                        mock_get_data.return_value = pd.concat(
                                            [sample_sales_data, sample_invalid_data]
                                        )

                                        # Return valid and invalid data
                                        mock_validate.return_value = (
                                            sample_sales_data,
                                            sample_invalid_data,
                                        )
                                        mock_transform.return_value = sample_sales_data
                                        mock_move.return_value = "processed/test.csv"

                                        # Run pipeline
                                        run_pipeline("raw/test.csv")

                                        # Verify quarantine was called
                                        mock_quarantine.assert_called_once()


def test_run_pipeline_all_invalid_records(sample_invalid_data):
    """Test pipeline when all records are invalid."""
    with patch("dags.src.pipeline.get_vault_client") as mock_vault:
        with patch("dags.src.pipeline.get_minio_client") as mock_minio:
            with patch("dags.src.pipeline.get_object_size") as mock_size:
                with patch("dags.src.pipeline.get_raw_data") as mock_get_data:
                    with patch("dags.src.pipeline.validate_data") as mock_validate:
                        with patch(
                            "dags.src.pipeline.save_invalid_data_to_quarantine"
                        ) as mock_quarantine:
                            # Setup mocks
                            mock_vault.return_value = MagicMock()
                            mock_minio.return_value = MagicMock()
                            mock_size.return_value = 1024
                            mock_get_data.return_value = sample_invalid_data

                            # All invalid, no valid data
                            mock_validate.return_value = (
                                pd.DataFrame(),
                                sample_invalid_data,
                            )

                            # Run pipeline - should raise error
                            with pytest.raises(ValueError, match="All records.*failed validation"):
                                run_pipeline("raw/test.csv")

                            # Quarantine should still be called
                            mock_quarantine.assert_called_once()


def test_run_pipeline_vault_error():
    """Test pipeline with Vault connection error."""
    with patch("dags.src.pipeline.get_vault_client") as mock_vault:
        mock_vault.side_effect = Exception("Vault connection failed")

        with pytest.raises(Exception, match="Vault connection failed"):
            run_pipeline("raw/test.csv")


def test_run_pipeline_minio_error():
    """Test pipeline with MinIO connection error."""
    with patch("dags.src.pipeline.get_vault_client") as mock_vault:
        with patch("dags.src.pipeline.get_minio_client") as mock_minio:
            mock_vault.return_value = MagicMock()
            mock_response = Mock()
            mock_response.status = 500
            mock_minio.side_effect = S3Error(
                response=mock_response,
                code="ConnectionError",
                message="MinIO failed",
                resource="minio:9000",
                request_id="req123",
                host_id="host456",
            )

            with pytest.raises(S3Error):
                run_pipeline("raw/test.csv")


def test_run_pipeline_transformation_error(sample_sales_data):
    """Test pipeline with transformation error."""
    with patch("dags.src.pipeline.get_vault_client") as mock_vault:
        with patch("dags.src.pipeline.get_minio_client") as mock_minio:
            with patch("dags.src.pipeline.get_object_size") as mock_size:
                with patch("dags.src.pipeline.get_raw_data") as mock_get_data:
                    with patch("dags.src.pipeline.validate_data") as mock_validate:
                        with patch("dags.src.pipeline.transform_sales_data") as mock_transform:
                            # Setup mocks
                            mock_vault.return_value = MagicMock()
                            mock_minio.return_value = MagicMock()
                            mock_size.return_value = 1024
                            mock_get_data.return_value = sample_sales_data
                            mock_validate.return_value = (
                                sample_sales_data,
                                pd.DataFrame(),
                            )
                            mock_transform.side_effect = Exception("Transformation failed")

                            with pytest.raises(Exception, match="Transformation failed"):
                                run_pipeline("raw/test.csv")


def test_run_pipeline_database_error(sample_sales_data):
    """Test pipeline with database loading error."""
    with patch("dags.src.pipeline.get_vault_client") as mock_vault:
        with patch("dags.src.pipeline.get_minio_client") as mock_minio:
            with patch("dags.src.pipeline.get_object_size") as mock_size:
                with patch("dags.src.pipeline.get_raw_data") as mock_get_data:
                    with patch("dags.src.pipeline.validate_data") as mock_validate:
                        with patch("dags.src.pipeline.transform_sales_data") as mock_transform:
                            with patch("dags.src.pipeline.upsert_data") as mock_upsert:
                                # Setup mocks
                                mock_vault.return_value = MagicMock()
                                mock_minio.return_value = MagicMock()
                                mock_size.return_value = 1024
                                mock_get_data.return_value = sample_sales_data
                                mock_validate.return_value = (
                                    sample_sales_data,
                                    pd.DataFrame(),
                                )
                                mock_transform.return_value = sample_sales_data
                                mock_upsert.side_effect = Exception("Database error")

                                with pytest.raises(Exception, match="Database error"):
                                    run_pipeline("raw/test.csv")
