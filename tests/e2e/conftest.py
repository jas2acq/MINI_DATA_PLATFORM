"""Shared fixtures for end-to-end tests."""

import io
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture
def e2e_complete_dataset():
    """Create complete realistic dataset for e2e testing."""
    return pd.DataFrame(
        [
            {
                "order_id": "E2E0001001",
                "customer_name": "David Brown",
                "customer_email": "david.brown@example.com",
                "customer_phone": "555-1001",
                "customer_address": "101 First St, Boston",
                "product_title": "Laptop Computer Pro",
                "product_rating": 4.7,
                "discounted_price": 1299.99,
                "original_price": 1899.99,
                "discount_percentage": 32,
                "is_best_seller": True,
                "delivery_date": date(2025, 10, 25),
                "data_collected_at": date(2025, 10, 1),
                "product_category": "Electronics",
                "quantity": 1,
                "order_date": date(2025, 10, 20),
            },
            {
                "order_id": "E2E0001002",
                "customer_name": "Emma Wilson",
                "customer_email": "emma.wilson@example.com",
                "customer_phone": "555-1002",
                "customer_address": "202 Second Ave, Chicago",
                "product_title": "Yoga Mat Premium",
                "product_rating": 4.9,
                "discounted_price": 49.99,
                "original_price": 79.99,
                "discount_percentage": 38,
                "is_best_seller": True,
                "delivery_date": date(2025, 10, 23),
                "data_collected_at": date(2025, 10, 1),
                "product_category": "Sports",
                "quantity": 2,
                "order_date": date(2025, 10, 18),
            },
            {
                "order_id": "E2E0001003",
                "customer_name": "Frank Miller",
                "customer_email": "frank.miller@example.com",
                "customer_phone": "555-1003",
                "customer_address": "303 Third Blvd, Denver",
                "product_title": "Smart Watch Series 5",
                "product_rating": 4.6,
                "discounted_price": 299.99,
                "original_price": 449.99,
                "discount_percentage": 33,
                "is_best_seller": False,
                "delivery_date": date(2025, 10, 28),
                "data_collected_at": date(2025, 10, 1),
                "product_category": "Electronics",
                "quantity": 1,
                "order_date": date(2025, 10, 21),
            },
            {
                "order_id": "E2E0001004",
                "customer_name": "Grace Lee",
                "customer_email": "grace.lee@example.com",
                "customer_phone": "555-1004",
                "customer_address": "404 Fourth Way, Miami",
                "product_title": "Kitchen Blender Max",
                "product_rating": 4.4,
                "discounted_price": 89.99,
                "original_price": 139.99,
                "discount_percentage": 36,
                "is_best_seller": True,
                "delivery_date": date(2025, 10, 24),
                "data_collected_at": date(2025, 10, 1),
                "product_category": "Home & Kitchen",
                "quantity": 1,
                "order_date": date(2025, 10, 19),
            },
            {
                "order_id": "E2E0001005",
                "customer_name": "Henry Taylor",
                "customer_email": "henry.taylor@example.com",
                "customer_phone": "555-1005",
                "customer_address": "505 Fifth Circle, Austin",
                "product_title": "Gaming Mouse RGB",
                "product_rating": 4.8,
                "discounted_price": 59.99,
                "original_price": 99.99,
                "discount_percentage": 40,
                "is_best_seller": True,
                "delivery_date": date(2025, 10, 26),
                "data_collected_at": date(2025, 10, 1),
                "product_category": "Electronics",
                "quantity": 3,
                "order_date": date(2025, 10, 22),
            },
        ]
    )


@pytest.fixture
def mock_e2e_environment():
    """Create complete mock environment for e2e testing."""
    mocks = {
        "vault": MagicMock(),
        "minio": MagicMock(),
        "postgres": MagicMock(),
    }

    # Vault mock
    mocks["vault"].is_authenticated.return_value = True
    mocks["vault"].secrets.kv.v2.read_secret_version.return_value = {
        "data": {
            "data": {
                "access_key": "e2e_access_key",
                "secret_key": "e2e_secret_key",
                "user": "e2e_user",
                "password": "e2e_password",
                "host": "localhost",
                "port": "5432",
                "dbname": "e2e_db",
            }
        }
    }

    # MinIO mock
    mocks["minio"].bucket_exists.return_value = True

    # PostgreSQL mock
    mock_cursor = MagicMock()
    mocks["postgres"].cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (1,)
    mock_cursor.fetchall.return_value = [
        (1, date(2025, 10, 18)),
        (2, date(2025, 10, 19)),
        (3, date(2025, 10, 20)),
        (4, date(2025, 10, 21)),
        (5, date(2025, 10, 22)),
    ]

    return mocks
