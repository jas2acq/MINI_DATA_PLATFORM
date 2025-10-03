"""Integration tests for validation and transformation components."""

import pandas as pd
import pytest

from dags.src.transformation.transformer import transform_sales_data
from dags.src.utils.schemas import SalesRecord
from dags.src.validation.validator import validate_data


def test_validate_then_transform_valid_data(integration_sales_data):
    """Test validating and transforming valid sales data."""
    # Validate
    valid_df, invalid_df = validate_data(integration_sales_data, SalesRecord)

    assert len(valid_df) == 3
    assert len(invalid_df) == 0

    # Transform
    transformed_df = transform_sales_data(valid_df)

    # Verify transformations applied
    assert "customer_email_hash" in transformed_df.columns
    assert "customer_phone_redacted" in transformed_df.columns
    assert "customer_address_redacted" in transformed_df.columns
    assert "profit" in transformed_df.columns

    # Verify PII anonymization
    assert all(transformed_df["customer_email_hash"].str.len() == 64)  # SHA-256 hash
    assert all(transformed_df["customer_phone_redacted"] == "***-****")
    assert all(transformed_df["customer_address_redacted"] == "*** **** **")


def test_transform_maintains_valid_data_integrity(integration_sales_data):
    """Test that transformation maintains data integrity for valid records."""
    # Validate
    valid_df, _ = validate_data(integration_sales_data, SalesRecord)

    # Store original values
    original_order_ids = valid_df["order_id"].tolist()
    original_quantities = valid_df["quantity"].tolist()

    # Transform
    transformed_df = transform_sales_data(valid_df)

    # Verify key fields unchanged
    assert transformed_df["order_id"].tolist() == original_order_ids
    assert transformed_df["quantity"].tolist() == original_quantities


def test_transform_calculates_profit_correctly(integration_sales_data):
    """Test that profit calculation is correct after validation."""
    # Validate
    valid_df, _ = validate_data(integration_sales_data, SalesRecord)

    # Transform
    transformed_df = transform_sales_data(valid_df)

    # Verify profit calculation (discounted_price - (original_price * 0.6))
    for _, row in transformed_df.iterrows():
        expected_profit = row["discounted_price"] - (row["original_price"] * 0.6)
        assert abs(row["profit"] - expected_profit) < 0.01  # Allow for rounding


def test_validation_filters_invalid_before_transformation(integration_sales_data):
    """Test that invalid data is filtered out before transformation."""
    # Add invalid record
    invalid_row = pd.DataFrame(
        [
            {
                "order_id": "INV",
                "customer_name": "Invalid User",
                "customer_email": "not-valid",
                "customer_phone": "123",
                "customer_address": "Addr",
                "product_title": "Product",
                "product_rating": 10.0,
                "discounted_price": -50.0,
                "original_price": 100.0,
                "discount_percentage": 150,
                "is_best_seller": True,
                "delivery_date": pd.Timestamp("2025-10-01"),
                "data_collected_at": pd.Timestamp("2025-10-01"),
                "product_category": "Test",
                "quantity": -1,
                "order_date": pd.Timestamp("2025-10-01"),
            }
        ]
    )

    mixed_data = pd.concat([integration_sales_data, invalid_row], ignore_index=True)

    # Validate
    valid_df, invalid_df = validate_data(mixed_data, SalesRecord)

    assert len(valid_df) == 3
    assert len(invalid_df) == 1

    # Transform only valid data
    transformed_df = transform_sales_data(valid_df)

    # Transformed data should only contain valid records
    assert len(transformed_df) == 3
    assert "INV" not in transformed_df["order_id"].values


def test_transform_preserves_column_count(integration_sales_data):
    """Test that transformation adds expected new columns."""
    # Validate
    valid_df, _ = validate_data(integration_sales_data, SalesRecord)
    original_columns = set(valid_df.columns)

    # Transform
    transformed_df = transform_sales_data(valid_df)
    new_columns = set(transformed_df.columns)

    # New columns should be added
    expected_new_columns = {
        "customer_email_hash",
        "customer_phone_redacted",
        "customer_address_redacted",
        "profit",
    }

    assert expected_new_columns.issubset(new_columns)


def test_transformation_handles_edge_case_values(integration_sales_data):
    """Test transformation handles edge case values correctly."""
    # Validate
    valid_df, _ = validate_data(integration_sales_data, SalesRecord)

    # Transform
    transformed_df = transform_sales_data(valid_df)

    # Check that all anonymized fields are not null
    assert transformed_df["customer_email_hash"].notna().all()
    assert transformed_df["customer_phone_redacted"].notna().all()
    assert transformed_df["customer_address_redacted"].notna().all()
    assert transformed_df["profit"].notna().all()

    # Check profit is within reasonable range
    assert (transformed_df["profit"] >= -1000).all()  # Reasonable lower bound
    assert (transformed_df["profit"] <= 10000).all()  # Reasonable upper bound
