"""MinIO client functions for data ingestion from object storage.

This module handles all interactions with MinIO, including downloading CSV files,
listing objects, and moving files between prefixes.
"""

import io
import os
from collections.abc import Iterator

import hvac
import pandas as pd
import urllib3
from minio.commonconfig import CopySource
from minio.error import S3Error

from dags.src.utils.helpers import setup_logger
from minio import Minio

# Initialize logger
logger = setup_logger("ingestion", "logs/ingestion.log")

# Constants
BUCKET_NAME = "data-platform"
RAW_PREFIX = "raw/"
PROCESSED_PREFIX = "processed/"
CHUNK_SIZE_THRESHOLD = 1073741824  # 1GB in bytes


def get_minio_credentials(vault_client: hvac.Client) -> tuple[str, str, str, bool]:
    """Retrieve MinIO credentials from Vault.

    Args:
        vault_client: Authenticated Vault client instance.

    Returns:
        Tuple of (endpoint, access_key, secret_key, secure).

    Raises:
        hvac.exceptions.VaultError: If secret retrieval fails.
        KeyError: If required secret keys are missing.
    """
    try:
        # Read MinIO secrets from Vault
        secret_response = vault_client.secrets.kv.v2.read_secret_version(
            path="minio",
            mount_point="kv",
        )
        secrets = secret_response["data"]["data"]

        access_key = secrets["access_key"]
        secret_key = secrets["secret_key"]

        # Get endpoint from environment or default
        endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        secure = os.getenv("MINIO_SECURE", "False").lower() == "true"

        logger.info("Successfully retrieved MinIO credentials from Vault")
        return endpoint, access_key, secret_key, secure

    except hvac.exceptions.VaultError as e:
        logger.error(f"Failed to retrieve MinIO credentials from Vault: {str(e)}")
        raise
    except KeyError as e:
        logger.error(f"Missing required key in MinIO secrets: {str(e)}")
        raise


def get_minio_client(vault_client: hvac.Client) -> Minio:
    """Initialize and return a MinIO client using credentials from Vault.

    Uses strict SSL certificate verification for secure HTTPS connections.

    Args:
        vault_client: Authenticated Vault client instance.

    Returns:
        Initialized Minio client with SSL verification.

    Raises:
        hvac.exceptions.VaultError: If credential retrieval fails.
        S3Error: If MinIO connection fails.
    """
    try:
        endpoint, access_key, secret_key, secure = get_minio_credentials(vault_client)

        # Create custom HTTP client with strict SSL verification
        http_client = None
        if secure:
            ca_cert_path = os.getenv("MINIO_CA_CERT", "/opt/airflow/certs/ca.crt")
            if os.path.exists(ca_cert_path):
                http_client = urllib3.PoolManager(
                    cert_reqs="CERT_REQUIRED",
                    ca_certs=ca_cert_path,
                )
                logger.info(f"Using CA certificate for SSL verification: {ca_cert_path}")
            else:
                logger.warning(
                    f"CA certificate not found at {ca_cert_path}, using default SSL verification"
                )

        client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            http_client=http_client,
        )

        # Verify connection by checking if bucket exists
        if not client.bucket_exists(BUCKET_NAME):
            raise ValueError(f"Bucket '{BUCKET_NAME}' does not exist")

        logger.info(f"Successfully connected to MinIO at {endpoint}")
        return client

    except S3Error as e:
        logger.error(f"MinIO connection error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize MinIO client: {str(e)}")
        raise


def get_object_size(minio_client: Minio, object_key: str) -> int:
    """Get the size of an object in bytes.

    Args:
        minio_client: Initialized MinIO client.
        object_key: Object key (path) in the bucket.

    Returns:
        Size of the object in bytes.

    Raises:
        S3Error: If object doesn't exist or stat operation fails.
    """
    try:
        stat = minio_client.stat_object(BUCKET_NAME, object_key)
        if stat.size is None:
            raise ValueError(f"Object '{object_key}' has no size information")
        return stat.size
    except S3Error as e:
        logger.error(f"Failed to get size for object '{object_key}': {str(e)}")
        raise


def get_raw_data(
    minio_client: Minio,
    object_key: str,
    use_chunking: bool | None = None,
    chunk_size: int = 10000,
) -> pd.DataFrame | Iterator[pd.DataFrame]:
    """Download and read CSV data from MinIO.

    For files larger than 1GB, returns an iterator of DataFrame chunks.
    For smaller files, returns a single DataFrame.

    Args:
        minio_client: Initialized MinIO client.
        object_key: Object key (path) in the bucket.
        use_chunking: Force chunking mode (None=auto-detect based on size).
        chunk_size: Number of rows per chunk when chunking (default: 10000).

    Returns:
        DataFrame or iterator of DataFrame chunks.

    Raises:
        S3Error: If download fails.
        pd.errors.ParserError: If CSV parsing fails.
    """
    try:
        # Auto-detect chunking based on file size if not specified
        if use_chunking is None:
            object_size = get_object_size(minio_client, object_key)
            use_chunking = object_size > CHUNK_SIZE_THRESHOLD
            if use_chunking:
                logger.info(
                    f"File size ({object_size} bytes) exceeds threshold, using chunked processing"
                )

        # Get object data
        response = minio_client.get_object(BUCKET_NAME, object_key)
        data = response.read()
        response.close()
        response.release_conn()

        # Convert to DataFrame or iterator
        if use_chunking:
            logger.info(f"Reading '{object_key}' in chunks of {chunk_size} rows")
            return pd.read_csv(
                io.BytesIO(data),
                chunksize=chunk_size,
                parse_dates=["order_date", "delivery_date", "data_collected_at"],
            )
        else:
            logger.info(f"Reading '{object_key}' as single DataFrame")
            return pd.read_csv(
                io.BytesIO(data),
                parse_dates=["order_date", "delivery_date", "data_collected_at"],
            )

    except S3Error as e:
        logger.error(f"Failed to download object '{object_key}': {str(e)}")
        raise
    except pd.errors.ParserError as e:
        logger.error(f"Failed to parse CSV from '{object_key}': {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error reading '{object_key}': {str(e)}")
        raise


def list_raw_keys(minio_client: Minio, prefix: str = RAW_PREFIX) -> list[str]:
    """List all object keys in the specified prefix.

    Args:
        minio_client: Initialized MinIO client.
        prefix: Prefix to list objects from (default: 'raw/').

    Returns:
        List of object keys (paths).

    Raises:
        S3Error: If listing operation fails.
    """
    try:
        objects = minio_client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True)
        keys = [obj.object_name for obj in objects]
        logger.info(f"Found {len(keys)} objects with prefix '{prefix}'")
        return keys
    except S3Error as e:
        logger.error(f"Failed to list objects with prefix '{prefix}': {str(e)}")
        raise


def move_processed_file(
    minio_client: Minio,
    source_key: str,
    destination_prefix: str = PROCESSED_PREFIX,
) -> str:
    """Move a file from raw/ to processed/ prefix.

    Args:
        minio_client: Initialized MinIO client.
        source_key: Source object key (must start with 'raw/').
        destination_prefix: Destination prefix (default: 'processed/').

    Returns:
        Destination object key.

    Raises:
        ValueError: If source_key doesn't start with 'raw/'.
        S3Error: If copy or delete operation fails.
    """
    if not source_key.startswith(RAW_PREFIX):
        raise ValueError(f"Source key must start with '{RAW_PREFIX}', got: {source_key}")

    try:
        # Extract filename from source key
        filename = source_key[len(RAW_PREFIX) :]
        destination_key = f"{destination_prefix}{filename}"

        # Copy object to new location
        minio_client.copy_object(
            bucket_name=BUCKET_NAME,
            object_name=destination_key,
            source=CopySource(BUCKET_NAME, source_key),
        )
        logger.info(f"Copied '{source_key}' to '{destination_key}'")

        # Remove original object
        minio_client.remove_object(BUCKET_NAME, source_key)
        logger.info(f"Removed original object '{source_key}'")

        return destination_key

    except S3Error as e:
        logger.error(f"Failed to move object from '{source_key}': {str(e)}")
        raise
