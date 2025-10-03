"""Shared fixtures for integration tests."""

import io
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture
def integration_sales_data():
    """Create realistic sales data for integration testing."""
    return pd.DataFrame(
        [
            {
                "order_id": "ORD2025001",
                "customer_name": "Alice Johnson",
                "customer_email": "alice.johnson@example.com",
                "customer_phone": "555-0100",
                "customer_address": "100 Main St, Springfield",
                "product_title": "Wireless Mouse - Tech Edition",
                "product_rating": 4.5,
                "discounted_price": 29.99,
                "original_price": 49.99,
                "discount_percentage": 40,
                "is_best_seller": True,
                "delivery_date": date(2025, 10, 20),
                "data_collected_at": date(2025, 10, 1),
                "product_category": "Electronics",
                "quantity": 2,
                "order_date": date(2025, 10, 15),
            },
            {
                "order_id": "ORD2025002",
                "customer_name": "Bob Smith",
                "customer_email": "bob.smith@example.com",
                "customer_phone": "555-0200",
                "customer_address": "200 Oak Ave, Portland",
                "product_title": "Running Shoes - Sport Pro",
                "product_rating": 4.8,
                "discounted_price": 89.99,
                "original_price": 129.99,
                "discount_percentage": 31,
                "is_best_seller": False,
                "delivery_date": date(2025, 10, 22),
                "data_collected_at": date(2025, 10, 1),
                "product_category": "Sports",
                "quantity": 1,
                "order_date": date(2025, 10, 16),
            },
            {
                "order_id": "ORD2025003",
                "customer_name": "Carol White",
                "customer_email": "carol.white@example.com",
                "customer_phone": "555-0300",
                "customer_address": "300 Pine Rd, Seattle",
                "product_title": "Coffee Maker Deluxe",
                "product_rating": 4.2,
                "discounted_price": 79.99,
                "original_price": 119.99,
                "discount_percentage": 33,
                "is_best_seller": True,
                "delivery_date": date(2025, 10, 18),
                "data_collected_at": date(2025, 10, 1),
                "product_category": "Home & Kitchen",
                "quantity": 1,
                "order_date": date(2025, 10, 14),
            },
        ]
    )


@pytest.fixture
def mock_minio_with_csv_data(integration_sales_data):
    """Create mock MinIO client with CSV data."""
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True

    # Mock CSV data as bytes
    csv_buffer = io.BytesIO()
    integration_sales_data.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    mock_response = MagicMock()
    mock_response.read.return_value = csv_data
    mock_client.get_object.return_value = mock_response

    # Mock object size
    mock_stat = MagicMock()
    mock_stat.size = len(csv_data)
    mock_client.stat_object.return_value = mock_stat

    return mock_client


@pytest.fixture
def mock_postgres_with_transactions():
    """Create mock PostgreSQL connection with transaction support."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # Mock dimension ID returns
    customer_id = 1
    product_id = 1
    date_id = 1

    def mock_fetchone_side_effect(*args, **kwargs):
        nonlocal customer_id, product_id, date_id
        # Alternate between returning different IDs
        if "customer" in str(args):
            customer_id += 1
            return (customer_id,)
        elif "product" in str(args):
            product_id += 1
            return (product_id,)
        else:
            date_id += 1
            return (date_id,)

    mock_cursor.fetchone.side_effect = mock_fetchone_side_effect
    mock_cursor.fetchall.return_value = [
        (1, date(2025, 10, 15)),
        (2, date(2025, 10, 16)),
        (3, date(2025, 10, 14)),
    ]

    return mock_conn
