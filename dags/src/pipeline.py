"""Main ETL pipeline orchestrator for processing sales data.

This module orchestrates the complete ETL workflow for a single file:
ingestion, validation, transformation, and loading into PostgreSQL.
"""

import io

from minio.error import S3Error

from dags.src.ingestion.minio_client import (
    BUCKET_NAME,
    get_minio_client,
    get_object_size,
    get_raw_data,
    move_processed_file,
)
from dags.src.loading.postgres_loader import upsert_data
from dags.src.transformation.transformer import transform_sales_data
from dags.src.utils.helpers import get_vault_client, setup_logger
from dags.src.utils.schemas import SalesRecord
from dags.src.validation.validator import validate_data

# Initialize logger
logger = setup_logger("pipeline", "logs/pipeline.log")


def save_invalid_data_to_quarantine(
    minio_client,
    invalid_df,
    original_file_key: str,
) -> None:
    """Save invalid records to quarantine prefix in MinIO.

    Args:
        minio_client: Initialized MinIO client.
        invalid_df: DataFrame containing invalid records.
        original_file_key: Original file key to derive quarantine filename.

    Raises:
        S3Error: If upload to quarantine fails.
    """
    if invalid_df.empty:
        logger.info("No invalid records to quarantine")
        return

    try:
        # Extract filename and create quarantine key
        filename = original_file_key.replace("raw/", "")
        quarantine_key = f"quarantine/{filename}"

        # Convert DataFrame to CSV bytes
        csv_buffer = io.BytesIO()
        invalid_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        # Upload to quarantine
        minio_client.put_object(
            BUCKET_NAME,
            quarantine_key,
            csv_buffer,
            length=csv_buffer.getbuffer().nbytes,
            content_type="text/csv",
        )

        logger.info(f"Quarantined {len(invalid_df)} invalid records to '{quarantine_key}'")

    except S3Error as e:
        logger.error(f"Failed to save invalid data to quarantine: {str(e)}")
        raise


def run_pipeline(file_key: str) -> None:
    """Execute ETL pipeline for a single file.

    Workflow:
    1. Initialize Vault client and retrieve credentials
    2. Connect to MinIO and check file size
    3. Ingest data from MinIO (with chunking if needed)
    4. Validate data against schema
    5. Quarantine invalid records
    6. Transform valid data
    7. Load transformed data into PostgreSQL
    8. Move processed file to processed/ prefix

    Args:
        file_key: MinIO object key for the file to process (e.g., 'raw/batch_1.csv').

    Raises:
        Exception: If any step in the pipeline fails.
    """
    logger.info(f"Starting ETL pipeline for file: {file_key}")

    try:
        # Step 1: Initialize Vault client
        logger.info("Initializing Vault client")
        vault_client = get_vault_client()

        # Step 2: Connect to MinIO
        logger.info("Connecting to MinIO")
        minio_client = get_minio_client(vault_client)

        # Step 3: Check file size for chunking decision
        logger.info("Checking file size")
        file_size = get_object_size(minio_client, file_key)
        logger.info(f"File size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")

        # Step 4: Ingest data from MinIO
        logger.info("Ingesting data from MinIO")
        raw_data = get_raw_data(minio_client, file_key)

        # Step 5: Validate data
        logger.info("Validating data against schema")
        validation_result = validate_data(raw_data, SalesRecord)

        # Handle validation results based on whether data is chunked
        if isinstance(raw_data, type(iter([]))):
            # Chunked data processing
            logger.info("Processing in chunked mode")
            valid_chunks = []
            invalid_chunks = []

            for valid_df, invalid_df in validation_result:
                if not valid_df.empty:
                    valid_chunks.append(valid_df)
                if not invalid_df.empty:
                    invalid_chunks.append(invalid_df)

            # Quarantine all invalid records
            if invalid_chunks:
                import pandas as pd

                combined_invalid = pd.concat(invalid_chunks, ignore_index=True)
                logger.warning(f"Found {len(combined_invalid)} invalid records across all chunks")
                save_invalid_data_to_quarantine(minio_client, combined_invalid, file_key)

            # Transform valid chunks
            logger.info("Transforming valid data chunks")
            transformed_chunks = []
            for valid_chunk in valid_chunks:
                transformed_chunk = transform_sales_data(valid_chunk)
                transformed_chunks.append(transformed_chunk)

            # Load transformed data
            logger.info("Loading transformed data to PostgreSQL")
            for transformed_chunk in transformed_chunks:
                upsert_data(vault_client, transformed_chunk)

        else:
            # Single DataFrame processing
            valid_df, invalid_df = validation_result

            # Step 6: Quarantine invalid records
            if not invalid_df.empty:
                logger.warning(f"Found {len(invalid_df)} invalid records")
                save_invalid_data_to_quarantine(minio_client, invalid_df, file_key)

            # Check if we have valid data to process
            if valid_df.empty:
                logger.warning("No valid records to process")
                raise ValueError(f"All records in {file_key} failed validation. Check quarantine.")

            # Step 7: Transform valid data
            logger.info(f"Transforming {len(valid_df)} valid records")
            transformed_df = transform_sales_data(valid_df)

            # Step 8: Load into PostgreSQL
            logger.info("Loading transformed data to PostgreSQL")
            upsert_data(vault_client, transformed_df)

        # Step 9: Move file to processed/
        logger.info("Moving file to processed prefix")
        destination_key = move_processed_file(minio_client, file_key)
        logger.info(f"File moved to: {destination_key}")

        logger.info(f"ETL pipeline completed successfully for {file_key}")

    except Exception as e:
        logger.error(f"ETL pipeline failed for {file_key}: {str(e)}")
        raise
