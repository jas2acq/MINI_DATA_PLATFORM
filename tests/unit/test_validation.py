"""Unit tests for data validation module."""

import pandas as pd

from dags.src.utils.schemas import SalesRecord
from dags.src.validation.validator import validate_data


def test_validate_valid_data(sample_sales_data):
    """Test validation with all valid data."""
    valid_df, invalid_df = validate_data(sample_sales_data, SalesRecord)

    assert len(valid_df) == 2
    assert len(invalid_df) == 0
    assert list(valid_df.columns) == list(sample_sales_data.columns)


def test_validate_invalid_data(sample_invalid_data):
    """Test validation with all invalid data."""
    valid_df, invalid_df = validate_data(sample_invalid_data, SalesRecord)

    assert len(valid_df) == 0
    assert len(invalid_df) == 1
    assert "validation_error" in invalid_df.columns


def test_validate_mixed_data(sample_sales_data, sample_invalid_data):
    """Test validation with mixed valid and invalid data."""
    mixed_data = pd.concat([sample_sales_data, sample_invalid_data], ignore_index=True)

    valid_df, invalid_df = validate_data(mixed_data, SalesRecord)

    assert len(valid_df) == 2
    assert len(invalid_df) == 1
