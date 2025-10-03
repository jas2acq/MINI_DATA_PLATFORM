"""End-to-end tests for complete ETL pipeline."""

import io
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from dags.src.pipeline import run_pipeline


def test_complete_etl_pipeline_success(e2e_complete_dataset, mock_e2e_environment):
    """Test complete ETL pipeline from ingestion to loading."""
    # Setup CSV data in MinIO mock
    csv_buffer = io.BytesIO()
    e2e_complete_dataset.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    mock_response = MagicMock()
    mock_response.read.return_value = csv_data
    mock_e2e_environment["minio"].get_object.return_value = mock_response

    mock_stat = MagicMock()
    mock_stat.size = len(csv_data)
    mock_e2e_environment["minio"].stat_object.return_value = mock_stat

    # Mock all external dependencies
    with patch("dags.src.pipeline.get_vault_client") as mock_vault_client:
        with patch("dags.src.pipeline.get_minio_client") as mock_minio_client:
            with patch("dags.src.loading.postgres_loader.psycopg2.connect") as mock_pg_connect:
                with patch("os.path.exists", return_value=True):
                    # Setup mocks
                    mock_vault_client.return_value = mock_e2e_environment["vault"]
                    mock_minio_client.return_value = mock_e2e_environment["minio"]
                    mock_pg_connect.return_value = mock_e2e_environment["postgres"]

                    # Run complete pipeline
                    run_pipeline("raw/e2e_test.csv")

                    # Verify all components were called
                    mock_vault_client.assert_called()
                    mock_minio_client.assert_called()

                    # Verify data was moved to processed
                    mock_e2e_environment["minio"].copy_object.assert_called_once()
                    mock_e2e_environment["minio"].remove_object.assert_called_once()


def test_e2e_pipeline_with_mixed_valid_invalid_data(mock_e2e_environment):
    """Test pipeline handles mixed valid and invalid data end-to-end."""
    # Create dataset with valid and invalid records
    mixed_data = pd.DataFrame(
        [
            {
                "order_id": "E2EVALID01",
                "customer_name": "Valid User",
                "customer_email": "valid@example.com",
                "customer_phone": "555-0001",
                "customer_address": "123 Valid St",
                "product_title": "Valid Product",
                "product_rating": 4.5,
                "discounted_price": 99.99,
                "original_price": 149.99,
                "discount_percentage": 33,
                "is_best_seller": True,
                "delivery_date": pd.Timestamp("2025-10-25"),
                "data_collected_at": pd.Timestamp("2025-10-01"),
                "product_category": "Electronics",
                "quantity": 1,
                "order_date": pd.Timestamp("2025-10-20"),
            },
            {
                "order_id": "INV",  # Invalid - too short
                "customer_name": "Invalid User",
                "customer_email": "not-email",  # Invalid
                "customer_phone": "123",
                "customer_address": "Addr",
                "product_title": "Product",
                "product_rating": 10.0,  # Invalid
                "discounted_price": -50.0,  # Invalid
                "original_price": 100.0,
                "discount_percentage": 200,  # Invalid
                "is_best_seller": True,
                "delivery_date": pd.Timestamp("2025-10-01"),
                "data_collected_at": pd.Timestamp("2025-10-01"),
                "product_category": "Test",
                "quantity": 0,  # Invalid
                "order_date": pd.Timestamp("2025-10-01"),
            },
        ]
    )

    # Setup CSV data
    csv_buffer = io.BytesIO()
    mixed_data.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    mock_response = MagicMock()
    mock_response.read.return_value = csv_data
    mock_e2e_environment["minio"].get_object.return_value = mock_response

    mock_stat = MagicMock()
    mock_stat.size = len(csv_data)
    mock_e2e_environment["minio"].stat_object.return_value = mock_stat

    with patch("dags.src.pipeline.get_vault_client") as mock_vault_client:
        with patch("dags.src.pipeline.get_minio_client") as mock_minio_client:
            with patch("dags.src.loading.postgres_loader.psycopg2.connect") as mock_pg_connect:
                with patch("os.path.exists", return_value=True):
                    mock_vault_client.return_value = mock_e2e_environment["vault"]
                    mock_minio_client.return_value = mock_e2e_environment["minio"]
                    mock_pg_connect.return_value = mock_e2e_environment["postgres"]

                    # Run pipeline
                    run_pipeline("raw/mixed_data.csv")

                    # Verify quarantine was called for invalid data
                    put_calls = mock_e2e_environment["minio"].put_object.call_args_list
                    assert any("quarantine" in str(call) for call in put_calls)


def test_e2e_pipeline_all_invalid_data_fails(mock_e2e_environment):
    """Test pipeline raises error when all data is invalid."""
    # Create dataset with only invalid records
    invalid_data = pd.DataFrame(
        [
            {
                "order_id": "BAD",
                "customer_name": "Bad",
                "customer_email": "bad",
                "customer_phone": "1",
                "customer_address": "A",
                "product_title": "B",
                "product_rating": 10.0,
                "discounted_price": -100.0,
                "original_price": 100.0,
                "discount_percentage": 300,
                "is_best_seller": True,
                "delivery_date": pd.Timestamp("2025-10-01"),
                "data_collected_at": pd.Timestamp("2025-10-01"),
                "product_category": "X",
                "quantity": 0,
                "order_date": pd.Timestamp("2025-10-01"),
            }
        ]
    )

    csv_buffer = io.BytesIO()
    invalid_data.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    mock_response = MagicMock()
    mock_response.read.return_value = csv_data
    mock_e2e_environment["minio"].get_object.return_value = mock_response

    mock_stat = MagicMock()
    mock_stat.size = len(csv_data)
    mock_e2e_environment["minio"].stat_object.return_value = mock_stat

    with patch("dags.src.pipeline.get_vault_client") as mock_vault_client:
        with patch("dags.src.pipeline.get_minio_client") as mock_minio_client:
            with patch("os.path.exists", return_value=True):
                mock_vault_client.return_value = mock_e2e_environment["vault"]
                mock_minio_client.return_value = mock_e2e_environment["minio"]

                # Pipeline should raise error for all invalid data
                with pytest.raises(ValueError, match="All records.*failed validation"):
                    run_pipeline("raw/all_invalid.csv")


def test_e2e_pipeline_data_transformations_applied(
    e2e_complete_dataset, mock_e2e_environment
):
    """Test that all transformations are correctly applied end-to-end."""
    csv_buffer = io.BytesIO()
    e2e_complete_dataset.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    mock_response = MagicMock()
    mock_response.read.return_value = csv_data
    mock_e2e_environment["minio"].get_object.return_value = mock_response

    mock_stat = MagicMock()
    mock_stat.size = len(csv_data)
    mock_e2e_environment["minio"].stat_object.return_value = mock_stat

    captured_data = []

    def capture_upsert_data(*args, **kwargs):
        """Capture data being inserted to verify transformations."""
        if len(args) > 1 and isinstance(args[1], pd.DataFrame):
            captured_data.append(args[1].copy())

    with patch("dags.src.pipeline.get_vault_client") as mock_vault_client:
        with patch("dags.src.pipeline.get_minio_client") as mock_minio_client:
            with patch("dags.src.loading.postgres_loader.psycopg2.connect") as mock_pg_connect:
                with patch(
                    "dags.src.loading.postgres_loader.upsert_data",
                    side_effect=capture_upsert_data,
                ):
                    with patch("os.path.exists", return_value=True):
                        mock_vault_client.return_value = mock_e2e_environment["vault"]
                        mock_minio_client.return_value = mock_e2e_environment["minio"]
                        mock_pg_connect.return_value = mock_e2e_environment["postgres"]

                        run_pipeline("raw/e2e_transform_test.csv")

                        # Verify transformations were applied
                        assert len(captured_data) > 0
                        df = captured_data[0]

                        # Check anonymization columns exist
                        assert "customer_email_hash" in df.columns
                        assert "customer_phone_redacted" in df.columns
                        assert "customer_address_redacted" in df.columns

                        # Check profit calculation exists
                        assert "profit" in df.columns
                        assert df["profit"].notna().all()


def test_e2e_pipeline_error_handling(mock_e2e_environment):
    """Test pipeline handles errors gracefully."""
    csv_buffer = io.BytesIO()
    csv_buffer.write(b"order_id,customer_name\nABC123,Test")
    csv_data = csv_buffer.getvalue()

    mock_response = MagicMock()
    mock_response.read.return_value = csv_data
    mock_e2e_environment["minio"].get_object.return_value = mock_response

    mock_stat = MagicMock()
    mock_stat.size = len(csv_data)
    mock_e2e_environment["minio"].stat_object.return_value = mock_stat

    with patch("dags.src.pipeline.get_vault_client") as mock_vault_client:
        with patch("dags.src.pipeline.get_minio_client") as mock_minio_client:
            with patch("os.path.exists", return_value=True):
                mock_vault_client.return_value = mock_e2e_environment["vault"]
                mock_minio_client.return_value = mock_e2e_environment["minio"]

                # Should raise error due to missing required columns
                with pytest.raises(ValueError):
                    run_pipeline("raw/error_test.csv")
