"""Integration tests for ingestion and validation components."""

import io
from unittest.mock import MagicMock

import pandas as pd

from dags.src.ingestion.minio_client import get_raw_data
from dags.src.utils.schemas import SalesRecord
from dags.src.validation.validator import validate_data


def test_ingest_and_validate_valid_data(mock_minio_with_csv_data):
    """Test ingesting CSV from MinIO and validating valid data."""
    # Ingest data
    df = get_raw_data(mock_minio_with_csv_data, "raw/test.csv")

    # Validate
    valid_df, invalid_df = validate_data(df, SalesRecord)

    # Verify results
    assert len(valid_df) == 3
    assert len(invalid_df) == 0
    assert all(valid_df.columns == df.columns)


def test_ingest_and_validate_mixed_data(mock_minio_with_csv_data):
    """Test ingesting and validating data with both valid and invalid records."""
    # Get valid data first
    df = get_raw_data(mock_minio_with_csv_data, "raw/test.csv")

    # Add invalid record
    invalid_row = pd.DataFrame(
        [
            {
                "order_id": "SHORT",  # Invalid
                "customer_name": "Test",
                "customer_email": "not-an-email",  # Invalid
                "customer_phone": "555",
                "customer_address": "Address",
                "product_title": "Product",
                "product_rating": 6.0,  # Invalid
                "discounted_price": -10.0,  # Invalid
                "original_price": 100.0,
                "discount_percentage": 200,  # Invalid
                "is_best_seller": True,
                "delivery_date": pd.Timestamp("2025-10-01"),
                "data_collected_at": pd.Timestamp("2025-10-01"),
                "product_category": "Test",
                "quantity": 0,  # Invalid
                "order_date": pd.Timestamp("2025-10-01"),
            }
        ]
    )

    mixed_df = pd.concat([df, invalid_row], ignore_index=True)

    # Validate
    valid_df, invalid_df = validate_data(mixed_df, SalesRecord)

    # Should have 3 valid and 1 invalid
    assert len(valid_df) == 3
    assert len(invalid_df) == 1
    assert "validation_error" in invalid_df.columns


def test_ingest_csv_with_missing_columns():
    """Test validation fails gracefully with missing required columns."""
    # Create mock MinIO with incomplete CSV
    incomplete_df = pd.DataFrame(
        [{"order_id": "ABC123", "customer_name": "John"}]  # Missing required columns
    )

    csv_buffer = io.BytesIO()
    incomplete_df.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.read.return_value = csv_data
    mock_client.get_object.return_value = mock_response

    mock_stat = MagicMock()
    mock_stat.size = len(csv_data)
    mock_client.stat_object.return_value = mock_stat

    # Ingest
    df = get_raw_data(mock_client, "raw/incomplete.csv")

    # Validate - should handle missing columns
    valid_df, invalid_df = validate_data(df, SalesRecord)

    # All records should be invalid due to missing columns
    assert len(valid_df) == 0
    assert len(invalid_df) == 1


def test_ingest_and_validate_preserves_data_types(mock_minio_with_csv_data):
    """Test that ingestion and validation preserve correct data types."""
    # Ingest
    df = get_raw_data(mock_minio_with_csv_data, "raw/test.csv")

    # Validate
    valid_df, invalid_df = validate_data(df, SalesRecord)

    # Check data types are preserved
    assert valid_df["order_id"].dtype == "object"  # String
    assert valid_df["quantity"].dtype in ["int64", "int32"]  # Integer
    assert valid_df["discounted_price"].dtype == "float64"  # Float
    assert pd.api.types.is_datetime64_any_dtype(valid_df["order_date"])
