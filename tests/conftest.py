"""Shared test fixtures for ETL pipeline testing."""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture
def mock_vault_client():
    """Create a mock Vault client."""
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {
            "data": {
                "access_key": "test_access_key",
                "secret_key": "test_secret_key",
                "user": "test_user",
                "password": "test_password",
                "host": "localhost",
                "port": "5432",
                "dbname": "test_db",
            }
        }
    }
    return mock_client


@pytest.fixture
def mock_minio_client():
    """Create a mock MinIO client."""
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True
    return mock_client


@pytest.fixture
def sample_sales_data():
    """Create sample valid sales data."""
    return pd.DataFrame(
        [
            {
                "order_id": "ABC1234567",
                "customer_name": "John Doe",
                "customer_email": "john@example.com",
                "customer_phone": "555-1234",
                "customer_address": "123 Main St",
                "product_title": "Premium Laptop - Electronics Edition",
                "product_rating": 4.5,
                "discounted_price": 999.99,
                "original_price": 1499.99,
                "discount_percentage": 33,
                "is_best_seller": True,
                "delivery_date": date(2025, 11, 1),
                "data_collected_at": date(2025, 10, 1),
                "product_category": "Electronics",
                "quantity": 1,
                "order_date": date(2025, 10, 15),
            },
            {
                "order_id": "XYZ9876543",
                "customer_name": "Jane Smith",
                "customer_email": "jane@example.com",
                "customer_phone": "555-5678",
                "customer_address": "456 Oak Ave",
                "product_title": "Running Shoes - Sports Edition",
                "product_rating": 5.0,
                "discounted_price": 79.99,
                "original_price": 129.99,
                "discount_percentage": 38,
                "is_best_seller": False,
                "delivery_date": date(2025, 10, 25),
                "data_collected_at": date(2025, 10, 1),
                "product_category": "Sports",
                "quantity": 2,
                "order_date": date(2025, 10, 15),
            },
        ]
    )


@pytest.fixture
def sample_invalid_data():
    """Create sample invalid sales data."""
    return pd.DataFrame(
        [
            {
                "order_id": "SHORT",  # Invalid: too short
                "customer_name": "Test User",
                "customer_email": "invalid-email",  # Invalid email format
                "customer_phone": "555-1234",
                "customer_address": "789 Pine Rd",
                "product_title": "Test Product",
                "product_rating": 6.0,  # Invalid: out of range
                "discounted_price": -10.99,  # Invalid: negative
                "original_price": 99.99,
                "discount_percentage": 150,  # Invalid: over 100
                "is_best_seller": True,
                "delivery_date": date(2025, 10, 1),
                "data_collected_at": date(2025, 10, 1),
                "product_category": "Test",
                "quantity": 0,  # Invalid: must be >= 1
                "order_date": date(2025, 10, 15),
            }
        ]
    )


@pytest.fixture
def mock_postgres_connection():
    """Create a mock PostgreSQL connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (1,)  # Mock ID return
    mock_cursor.fetchall.return_value = [(1, date(2025, 10, 15))]
    return mock_conn
