"""Data transformation module for business logic and PII anonymization.

This module applies transformations to validated sales data including
PII anonymization, profit calculation, and data type conversions.
"""

import hashlib
from collections.abc import Iterator

import pandas as pd

from dags.src.utils.helpers import setup_logger

# Initialize logger
logger = setup_logger("transformation", "logs/transformation.log")


def transform_sales_data(
    data: pd.DataFrame | Iterator[pd.DataFrame],
) -> pd.DataFrame | Iterator[pd.DataFrame]:
    """Apply business transformations to sales data.

    Transformations include:
    - PII anonymization (email hashing, phone/address redaction)
    - Profit calculation
    - Date type conversions
    - Monetary value rounding

    Args:
        data: Single DataFrame or iterator of DataFrames.

    Returns:
        Transformed DataFrame or iterator of DataFrames.

    Raises:
        TypeError: If data is not a DataFrame or Iterator of DataFrames.
    """
    if isinstance(data, pd.DataFrame):
        return _transform_single_dataframe(data)
    elif isinstance(data, Iterator):
        return _transform_chunked_dataframes(data)
    else:
        raise TypeError(f"Data must be pd.DataFrame or Iterator[pd.DataFrame], got {type(data)}")


def _transform_single_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Transform a single DataFrame.

    Args:
        df: DataFrame to transform.

    Returns:
        Transformed DataFrame.
    """
    logger.info(f"Starting transformation of {len(df)} records")

    # Create a copy to avoid modifying original
    transformed_df = df.copy()

    # PII Anonymization
    transformed_df = _anonymize_pii(transformed_df)

    # Calculate profit
    transformed_df = _calculate_profit(transformed_df)

    # Convert dates to datetime
    transformed_df = _convert_dates(transformed_df)

    # Round monetary values
    transformed_df = _round_monetary_values(transformed_df)

    logger.info(f"Transformation complete for {len(transformed_df)} records")

    return transformed_df


def _transform_chunked_dataframes(
    df_iterator: Iterator[pd.DataFrame],
) -> Iterator[pd.DataFrame]:
    """Transform chunked DataFrames.

    Args:
        df_iterator: Iterator yielding DataFrames.

    Yields:
        Transformed DataFrames.
    """
    logger.info("Starting chunked transformation")
    chunk_num = 0

    for chunk_df in df_iterator:
        chunk_num += 1
        logger.info(f"Transforming chunk {chunk_num} with {len(chunk_df)} records")

        transformed_chunk = _transform_single_dataframe(chunk_df)

        logger.info(f"Chunk {chunk_num} transformation complete")

        yield transformed_chunk

    logger.info(f"Completed transformation of {chunk_num} chunks")


def _anonymize_pii(df: pd.DataFrame) -> pd.DataFrame:
    """Anonymize personally identifiable information.

    - Hash email addresses using SHA-256
    - Redact phone numbers (keep last 4 digits)
    - Redact addresses (keep only city/state)

    Args:
        df: DataFrame with PII columns.

    Returns:
        DataFrame with anonymized PII.
    """
    logger.info("Anonymizing PII fields")

    # Hash email addresses
    if "customer_email" in df.columns:
        df["customer_email_hash"] = df["customer_email"].apply(_hash_email)
        df = df.drop(columns=["customer_email"])

    # Redact phone numbers
    if "customer_phone" in df.columns:
        df["customer_phone_redacted"] = df["customer_phone"].apply(_redact_phone)
        df = df.drop(columns=["customer_phone"])

    # Redact addresses
    if "customer_address" in df.columns:
        df["customer_address_redacted"] = df["customer_address"].apply(_redact_address)
        df = df.drop(columns=["customer_address"])

    return df


def _hash_email(email: str) -> str:
    """Hash email address using SHA-256.

    Args:
        email: Email address to hash.

    Returns:
        SHA-256 hash of the email.
    """
    return hashlib.sha256(email.encode()).hexdigest()


def _redact_phone(phone: str) -> str:
    """Redact phone number, keeping only last 4 digits.

    Args:
        phone: Phone number to redact.

    Returns:
        Redacted phone number (e.g., "***-***-1234").
    """
    # Extract digits only
    digits = "".join(filter(str.isdigit, phone))

    if len(digits) >= 4:
        return f"***-***-{digits[-4:]}"
    else:
        return "***-***-****"


def _redact_address(address: str) -> str:
    """Redact address, keeping only general location info.

    Args:
        address: Address to redact.

    Returns:
        Redacted address (e.g., "City, State REDACTED").
    """
    # Simple redaction: return placeholder
    # In production, might extract city/state using regex
    return "Address REDACTED"


def _calculate_profit(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate profit as discounted_price - (original_price * 0.6).

    Assumes cost of goods sold is 60% of original price.

    Args:
        df: DataFrame with price columns.

    Returns:
        DataFrame with profit column added.
    """
    logger.info("Calculating profit")

    if "discounted_price" in df.columns and "original_price" in df.columns:
        df["profit"] = df["discounted_price"] - (df["original_price"] * 0.6)
    else:
        logger.warning("Cannot calculate profit: missing price columns")

    return df


def _convert_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert date columns to datetime objects.

    Args:
        df: DataFrame with date columns.

    Returns:
        DataFrame with converted date types.
    """
    logger.info("Converting date columns")

    date_columns = ["order_date", "delivery_date", "data_collected_at"]

    for col in date_columns:
        if col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def _round_monetary_values(df: pd.DataFrame) -> pd.DataFrame:
    """Round monetary values to 2 decimal places.

    Args:
        df: DataFrame with monetary columns.

    Returns:
        DataFrame with rounded monetary values.
    """
    logger.info("Rounding monetary values")

    monetary_columns = ["discounted_price", "original_price", "profit"]

    for col in monetary_columns:
        if col in df.columns:
            df[col] = df[col].round(2)

    return df
