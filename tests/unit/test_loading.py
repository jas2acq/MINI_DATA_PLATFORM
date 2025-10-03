"""Unit tests for PostgreSQL loading module."""

import os
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import psycopg2
import pytest

from dags.src.loading.postgres_loader import (
    get_postgres_connection,
    get_postgres_credentials,
    upsert_data,
    upsert_dimension_customer,
    upsert_dimension_date,
    upsert_dimension_product,
    upsert_fact_sales,
)


def test_get_postgres_credentials_success(mock_vault_client):
    """Test successful retrieval of PostgreSQL credentials."""
    credentials = get_postgres_credentials(mock_vault_client)

    assert credentials["host"] == "localhost"
    assert credentials["port"] == "5432"
    assert credentials["dbname"] == "test_db"
    assert credentials["user"] == "test_user"
    assert credentials["password"] == "test_password"


def test_get_postgres_credentials_vault_error():
    """Test credentials retrieval with Vault error."""
    mock_vault = MagicMock()
    mock_vault.secrets.kv.v2.read_secret_version.side_effect = Exception("Vault error")

    with pytest.raises(Exception):
        get_postgres_credentials(mock_vault)


def test_get_postgres_credentials_missing_key(mock_vault_client):
    """Test credentials retrieval with missing required key."""
    mock_vault_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"user": "test_user"}}  # Missing password
    }

    with pytest.raises(KeyError):
        get_postgres_credentials(mock_vault_client)


def test_get_postgres_connection_success(mock_vault_client):
    """Test successful PostgreSQL connection."""
    with patch("dags.src.loading.postgres_loader.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # Security Note: /tmp path used only for testing purposes
        # In production, CA certificates should be stored in secure, read-only locations
        with patch.dict(os.environ, {"POSTGRES_CA_CERT": "/tmp/ca.crt"}):  # nosem: python.lang.security.audit.non-literal-import.non-literal-import
            with patch("os.path.exists", return_value=True):
                connection = get_postgres_connection(mock_vault_client)

                assert connection is not None
                mock_connect.assert_called_once()
                call_args = mock_connect.call_args[1]
                assert call_args["sslmode"] == "verify-full"
                assert call_args["sslrootcert"] == "/tmp/ca.crt"  # Test value only


def test_get_postgres_connection_error(mock_vault_client):
    """Test PostgreSQL connection failure."""
    with patch("dags.src.loading.postgres_loader.psycopg2.connect") as mock_connect:
        mock_connect.side_effect = psycopg2.Error("Connection failed")

        with pytest.raises(psycopg2.Error):
            get_postgres_connection(mock_vault_client)


def test_upsert_dimension_customer_success(mock_postgres_connection, sample_sales_data):
    """Test successful customer dimension upsert."""
    # Add required columns for transformation
    sample_sales_data["customer_email_hash"] = "hash123"
    sample_sales_data["customer_phone_redacted"] = "***-****"
    sample_sales_data["customer_address_redacted"] = "*** **** **"

    result_df = upsert_dimension_customer(mock_postgres_connection, sample_sales_data)

    assert "customer_id" in result_df.columns
    assert mock_postgres_connection.commit.called
    assert mock_postgres_connection.cursor.called


def test_upsert_dimension_customer_database_error(mock_postgres_connection, sample_sales_data):
    """Test customer upsert with database error."""
    sample_sales_data["customer_email_hash"] = "hash123"
    sample_sales_data["customer_phone_redacted"] = "***-****"
    sample_sales_data["customer_address_redacted"] = "*** **** **"

    mock_cursor = mock_postgres_connection.cursor.return_value
    mock_cursor.execute.side_effect = psycopg2.Error("DB error")

    with pytest.raises(psycopg2.Error):
        upsert_dimension_customer(mock_postgres_connection, sample_sales_data)

    assert mock_postgres_connection.rollback.called


def test_upsert_dimension_product_success(mock_postgres_connection, sample_sales_data):
    """Test successful product dimension upsert."""
    result_df = upsert_dimension_product(mock_postgres_connection, sample_sales_data)

    assert "product_id" in result_df.columns
    assert mock_postgres_connection.commit.called


def test_upsert_dimension_product_database_error(mock_postgres_connection, sample_sales_data):
    """Test product upsert with database error."""
    mock_cursor = mock_postgres_connection.cursor.return_value
    mock_cursor.execute.side_effect = psycopg2.Error("DB error")

    with pytest.raises(psycopg2.Error):
        upsert_dimension_product(mock_postgres_connection, sample_sales_data)

    assert mock_postgres_connection.rollback.called


def test_upsert_dimension_date_success(mock_postgres_connection, sample_sales_data):
    """Test successful date dimension upsert."""
    result_df = upsert_dimension_date(mock_postgres_connection, sample_sales_data)

    assert "order_date_id" in result_df.columns
    assert "delivery_date_id" in result_df.columns
    assert mock_postgres_connection.commit.called


def test_upsert_dimension_date_database_error(mock_postgres_connection, sample_sales_data):
    """Test date upsert with database error."""
    mock_cursor = mock_postgres_connection.cursor.return_value
    mock_cursor.execute.side_effect = psycopg2.Error("DB error")

    with pytest.raises(psycopg2.Error):
        upsert_dimension_date(mock_postgres_connection, sample_sales_data)

    assert mock_postgres_connection.rollback.called


def test_upsert_fact_sales_success(mock_postgres_connection):
    """Test successful fact sales upsert."""
    sales_df = pd.DataFrame(
        [
            {
                "order_id": "ABC123",
                "customer_id": 1,
                "product_id": 1,
                "order_date_id": 1,
                "delivery_date_id": 1,
                "quantity": 2,
                "discounted_price": 99.99,
                "original_price": 149.99,
                "discount_percentage": 33,
                "profit": 15.00,
                "data_collected_at": date(2025, 10, 1),
            }
        ]
    )

    upsert_fact_sales(mock_postgres_connection, sales_df)

    assert mock_postgres_connection.commit.called
    mock_cursor = mock_postgres_connection.cursor.return_value
    assert mock_cursor.execute.called


def test_upsert_fact_sales_database_error(mock_postgres_connection):
    """Test fact sales upsert with database error."""
    sales_df = pd.DataFrame(
        [
            {
                "order_id": "ABC123",
                "customer_id": 1,
                "product_id": 1,
                "order_date_id": 1,
                "delivery_date_id": 1,
                "quantity": 2,
                "discounted_price": 99.99,
                "original_price": 149.99,
                "discount_percentage": 33,
                "profit": 15.00,
                "data_collected_at": date(2025, 10, 1),
            }
        ]
    )

    mock_cursor = mock_postgres_connection.cursor.return_value
    mock_cursor.execute.side_effect = psycopg2.Error("DB error")

    with pytest.raises(psycopg2.Error):
        upsert_fact_sales(mock_postgres_connection, sales_df)

    assert mock_postgres_connection.rollback.called


def test_upsert_data_single_dataframe(mock_vault_client, sample_sales_data):
    """Test upserting a single DataFrame."""
    sample_sales_data["customer_email_hash"] = "hash123"
    sample_sales_data["customer_phone_redacted"] = "***-****"
    sample_sales_data["customer_address_redacted"] = "*** **** **"
    sample_sales_data["profit"] = 50.0

    with patch("dags.src.loading.postgres_loader.get_postgres_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [(1, date(2025, 10, 15))]
        mock_get_conn.return_value = mock_conn

        upsert_data(mock_vault_client, sample_sales_data)

        assert mock_conn.close.called


def test_upsert_data_invalid_type(mock_vault_client):
    """Test upsert with invalid data type."""
    with patch("dags.src.loading.postgres_loader.get_postgres_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        with pytest.raises(TypeError, match="Data must be pd.DataFrame or Iterator"):
            upsert_data(mock_vault_client, "invalid_data")


def test_upsert_data_connection_cleanup(mock_vault_client, sample_sales_data):
    """Test that connection is closed even on error."""
    sample_sales_data["customer_email_hash"] = "hash123"
    sample_sales_data["customer_phone_redacted"] = "***-****"
    sample_sales_data["customer_address_redacted"] = "*** **** **"

    with patch("dags.src.loading.postgres_loader.get_postgres_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.Error("DB error")
        mock_get_conn.return_value = mock_conn

        with pytest.raises(psycopg2.Error):
            upsert_data(mock_vault_client, sample_sales_data)

        # Connection should still be closed
        assert mock_conn.close.called
