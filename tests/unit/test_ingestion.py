"""Unit tests for MinIO ingestion module."""

import io
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from minio.error import S3Error

from dags.src.ingestion.minio_client import (
    get_minio_client,
    get_minio_credentials,
    get_object_size,
    get_raw_data,
    list_raw_keys,
    move_processed_file,
)


def test_get_minio_credentials_success(mock_vault_client):
    """Test successful retrieval of MinIO credentials from Vault."""
    credentials = get_minio_credentials(mock_vault_client)

    assert credentials[0] == "minio:9000"  # endpoint
    assert credentials[1] == "test_access_key"
    assert credentials[2] == "test_secret_key"
    assert isinstance(credentials[3], bool)  # secure flag


def test_get_minio_credentials_vault_error():
    """Test MinIO credentials retrieval with Vault error."""
    mock_vault = MagicMock()
    mock_vault.secrets.kv.v2.read_secret_version.side_effect = Exception("Vault error")

    with pytest.raises(Exception):
        get_minio_credentials(mock_vault)


def test_get_minio_client_success(mock_vault_client):
    """Test successful MinIO client initialization."""
    with patch("dags.src.ingestion.minio_client.Minio") as mock_minio:
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio.return_value = mock_client

        with patch.dict(os.environ, {"MINIO_SECURE": "False"}):
            client = get_minio_client(mock_vault_client)

            assert client is not None
            mock_client.bucket_exists.assert_called_once_with("data-platform")


def test_get_minio_client_bucket_not_found(mock_vault_client):
    """Test MinIO client initialization when bucket doesn't exist."""
    with patch("dags.src.ingestion.minio_client.Minio") as mock_minio:
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        mock_minio.return_value = mock_client

        with patch.dict(os.environ, {"MINIO_SECURE": "False"}):
            with pytest.raises(S3Error):
                get_minio_client(mock_vault_client)


def test_get_object_size_success(mock_minio_client):
    """Test successful object size retrieval."""
    mock_stat = MagicMock()
    mock_stat.size = 1024
    mock_minio_client.stat_object.return_value = mock_stat

    size = get_object_size(mock_minio_client, "raw/test.csv")

    assert size == 1024
    mock_minio_client.stat_object.assert_called_once_with("data-platform", "raw/test.csv")


def test_get_object_size_not_found(mock_minio_client):
    """Test object size retrieval when object doesn't exist."""
    mock_minio_client.stat_object.side_effect = S3Error(
        "NoSuchKey", "The specified key does not exist.", "resource", "request_id", "host_id"
    )

    with pytest.raises(S3Error):
        get_object_size(mock_minio_client, "raw/nonexistent.csv")


def test_get_raw_data_small_file(mock_minio_client):
    """Test reading small CSV file without chunking."""
    csv_content = "order_id,customer_name,order_date,delivery_date,data_collected_at\n"
    csv_content += "ABC123,John Doe,2025-01-01,2025-01-05,2025-01-01\n"

    mock_response = MagicMock()
    mock_response.read.return_value = csv_content.encode()
    mock_minio_client.get_object.return_value = mock_response

    mock_stat = MagicMock()
    mock_stat.size = 500  # Small file
    mock_minio_client.stat_object.return_value = mock_stat

    df = get_raw_data(mock_minio_client, "raw/small.csv")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df["order_id"].iloc[0] == "ABC123"


def test_get_raw_data_large_file_chunking(mock_minio_client):
    """Test reading large CSV file with chunking."""
    csv_content = "order_id,customer_name,order_date,delivery_date,data_collected_at\n"
    csv_content += "ABC123,John Doe,2025-01-01,2025-01-05,2025-01-01\n"

    mock_response = MagicMock()
    mock_response.read.return_value = csv_content.encode()
    mock_minio_client.get_object.return_value = mock_response

    mock_stat = MagicMock()
    mock_stat.size = 2 * 1024 * 1024 * 1024  # 2GB
    mock_minio_client.stat_object.return_value = mock_stat

    result = get_raw_data(mock_minio_client, "raw/large.csv")

    # Should return iterator for large files
    from collections.abc import Iterator

    assert isinstance(result, Iterator)


def test_list_raw_keys_success(mock_minio_client):
    """Test listing raw object keys."""
    mock_obj1 = MagicMock()
    mock_obj1.object_name = "raw/file1.csv"
    mock_obj2 = MagicMock()
    mock_obj2.object_name = "raw/file2.csv"

    mock_minio_client.list_objects.return_value = [mock_obj1, mock_obj2]

    keys = list_raw_keys(mock_minio_client)

    assert len(keys) == 2
    assert "raw/file1.csv" in keys
    assert "raw/file2.csv" in keys
    mock_minio_client.list_objects.assert_called_once_with(
        "data-platform", prefix="raw/", recursive=True
    )


def test_list_raw_keys_empty(mock_minio_client):
    """Test listing raw keys when no objects exist."""
    mock_minio_client.list_objects.return_value = []

    keys = list_raw_keys(mock_minio_client)

    assert len(keys) == 0


def test_move_processed_file_success(mock_minio_client):
    """Test successful file move from raw to processed."""
    destination = move_processed_file(mock_minio_client, "raw/test.csv")

    assert destination == "processed/test.csv"
    mock_minio_client.copy_object.assert_called_once()
    mock_minio_client.remove_object.assert_called_once_with("data-platform", "raw/test.csv")


def test_move_processed_file_invalid_source(mock_minio_client):
    """Test move with invalid source prefix."""
    with pytest.raises(ValueError, match="Source key must start with 'raw/'"):
        move_processed_file(mock_minio_client, "invalid/test.csv")


def test_move_processed_file_copy_error(mock_minio_client):
    """Test file move with copy error."""
    mock_minio_client.copy_object.side_effect = S3Error(
        "CopyError", "Copy failed", "resource", "request_id", "host_id"
    )

    with pytest.raises(S3Error):
        move_processed_file(mock_minio_client, "raw/test.csv")
