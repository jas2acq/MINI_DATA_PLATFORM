"""Unit tests for data transformation module."""

from dags.src.transformation.transformer import transform_sales_data


def test_transform_anonymizes_pii(sample_sales_data):
    """Test that PII fields are anonymized."""
    transformed_df = transform_sales_data(sample_sales_data)

    # Email should be hashed
    assert "customer_email_hash" in transformed_df.columns
    assert "customer_email" not in transformed_df.columns
    assert len(transformed_df["customer_email_hash"].iloc[0]) == 64  # SHA-256 length

    # Phone should be redacted
    assert "customer_phone_redacted" in transformed_df.columns
    assert "customer_phone" not in transformed_df.columns
    assert "***" in transformed_df["customer_phone_redacted"].iloc[0]

    # Address should be redacted
    assert "customer_address_redacted" in transformed_df.columns
    assert "customer_address" not in transformed_df.columns


def test_transform_calculates_profit(sample_sales_data):
    """Test that profit is calculated correctly."""
    transformed_df = transform_sales_data(sample_sales_data)

    assert "profit" in transformed_df.columns

    # Profit = discounted_price - (original_price * 0.6)
    for idx, row in sample_sales_data.iterrows():
        expected_profit = row["discounted_price"] - (row["original_price"] * 0.6)
        actual_profit = transformed_df.loc[idx, "profit"]
        assert round(actual_profit, 2) == round(expected_profit, 2)


def test_transform_rounds_monetary_values(sample_sales_data):
    """Test that monetary values are rounded to 2 decimals."""
    transformed_df = transform_sales_data(sample_sales_data)

    for col in ["discounted_price", "original_price", "profit"]:
        for value in transformed_df[col]:
            assert round(value, 2) == value


def test_transform_preserves_original(sample_sales_data):
    """Test that transformation doesn't modify original DataFrame."""
    original_cols = list(sample_sales_data.columns)
    _ = transform_sales_data(sample_sales_data)

    assert list(sample_sales_data.columns) == original_cols
