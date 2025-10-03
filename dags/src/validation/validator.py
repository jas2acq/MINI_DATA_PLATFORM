"""Data validation module for schema and business rule validation.

This module validates incoming data against the Pydantic schema and
separates valid records from invalid ones for quarantine.
"""

from collections.abc import Iterator

import pandas as pd
from pydantic import BaseModel, ValidationError

from dags.src.utils.helpers import setup_logger

# Initialize logger
logger = setup_logger("validation", "logs/validation.log")


def validate_data(
    data: pd.DataFrame | Iterator[pd.DataFrame],
    schema: type[BaseModel],
) -> tuple[pd.DataFrame, pd.DataFrame] | Iterator[tuple[pd.DataFrame, pd.DataFrame]]:
    """Validate DataFrame rows against a Pydantic schema.

    Validates each row in the DataFrame against the provided Pydantic schema.
    Returns separate DataFrames for valid and invalid records.

    For chunked input (Iterator of DataFrames), returns an iterator of
    (valid_df, invalid_df) tuples.

    Args:
        data: Single DataFrame or iterator of DataFrames to validate.
        schema: Pydantic BaseModel schema for validation.

    Returns:
        Tuple of (valid_df, invalid_df) or iterator of such tuples.

    Raises:
        TypeError: If data is not a DataFrame or Iterator of DataFrames.
    """
    if isinstance(data, pd.DataFrame):
        return _validate_single_dataframe(data, schema)
    elif isinstance(data, Iterator):
        return _validate_chunked_dataframes(data, schema)
    else:
        raise TypeError(f"Data must be pd.DataFrame or Iterator[pd.DataFrame], got {type(data)}")


def _validate_single_dataframe(
    df: pd.DataFrame,
    schema: type[BaseModel],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate a single DataFrame against schema.

    Args:
        df: DataFrame to validate.
        schema: Pydantic BaseModel schema for validation.

    Returns:
        Tuple of (valid_df, invalid_df).
    """
    valid_records = []
    invalid_records = []
    validation_errors = []

    logger.info(f"Starting validation of {len(df)} records")

    for idx, row in df.iterrows():
        try:
            # Convert row to dict and validate
            record_dict = row.to_dict()
            validated_record = schema(**record_dict)

            # Add validated record to valid list
            valid_records.append(validated_record.model_dump())

        except ValidationError as e:
            # Log validation failure
            error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
            logger.warning(f"Row {idx} validation failed: {error_details}")

            # Add to invalid records with error details
            invalid_record = row.to_dict()
            invalid_record["validation_error"] = error_details
            invalid_record["row_index"] = idx
            invalid_records.append(invalid_record)
            validation_errors.append(error_details)

        except Exception as e:
            # Catch unexpected errors
            logger.error(f"Unexpected error validating row {idx}: {str(e)}")
            invalid_record = row.to_dict()
            invalid_record["validation_error"] = f"Unexpected error: {str(e)}"
            invalid_record["row_index"] = idx
            invalid_records.append(invalid_record)

    # Create result DataFrames
    valid_df = pd.DataFrame(valid_records) if valid_records else pd.DataFrame()
    invalid_df = pd.DataFrame(invalid_records) if invalid_records else pd.DataFrame()

    # Log results
    logger.info(
        f"Validation complete: {len(valid_df)} valid records, {len(invalid_df)} invalid records"
    )

    if len(invalid_df) > 0:
        logger.warning("Invalid records will be quarantined")

    return valid_df, invalid_df


def _validate_chunked_dataframes(
    df_iterator: Iterator[pd.DataFrame],
    schema: type[BaseModel],
) -> Iterator[tuple[pd.DataFrame, pd.DataFrame]]:
    """Validate chunked DataFrames against schema.

    Args:
        df_iterator: Iterator yielding DataFrames.
        schema: Pydantic BaseModel schema for validation.

    Yields:
        Tuple of (valid_df, invalid_df) for each chunk.
    """
    logger.info("Starting chunked validation")
    chunk_num = 0

    for chunk_df in df_iterator:
        chunk_num += 1
        logger.info(f"Validating chunk {chunk_num} with {len(chunk_df)} records")

        valid_df, invalid_df = _validate_single_dataframe(chunk_df, schema)

        logger.info(
            f"Chunk {chunk_num} validation complete: {len(valid_df)} valid, "
            f"{len(invalid_df)} invalid"
        )

        yield valid_df, invalid_df

    logger.info(f"Completed validation of {chunk_num} chunks")
