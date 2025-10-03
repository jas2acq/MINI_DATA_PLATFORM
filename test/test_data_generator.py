import datetime
import io
import tempfile
import unittest
from collections.abc import Iterator
from itertools import repeat
from typing import Any
from unittest.mock import MagicMock, mock_open, patch

import pandas as pd

from src.data_generator import (
    generate_pii_data,
    generate_random_date,
    generate_random_product_title,
    main,
)


def mock_any_string_containing(substring: str) -> Any:
    """Helper to match any string containing a substring for mock assertions.

    Args:
        substring: The substring to check for.

    Returns:
        A mock object that matches any string containing the substring.
    """

    class StringContaining:
        def __init__(self, substring: str) -> None:
            self.substring = substring

        def __eq__(self, other: Any) -> bool:
            return isinstance(other, str) and self.substring in other

    return StringContaining(substring)


class TestDataGenerator(unittest.TestCase):
    """Unit tests for data_generator.py.

    Tests the functionality of data generation functions and main logic.
    """

    def setUp(self) -> None:
        """Set up test fixtures before each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_env_file = mock_open(
            read_data="FREQUENCY=10\nMINIO_ENDPOINT=localhost:9000\nMINIO_ACCESS_KEY=testkey\nMINIO_SECRET_KEY=testsecret\nMINIO_SECURE=False"
        )
        self.start_date = datetime.date(2023, 1, 1)
        self.end_date = datetime.date(2023, 12, 31)

    def tearDown(self) -> None:
        """Clean up test fixtures after each test."""
        self.temp_dir.cleanup()

    @patch("src.data_generator.random.choice")
    def test_generate_random_product_title(self, mock_choice: MagicMock) -> None:
        """Test generate_random_product_title function.

        Args:
            mock_choice: Mock for random.choice function.

        Verifies that the function returns a correctly formatted product title.
        """
        mock_choice.side_effect = ["Laptop", "Premium"]
        title: str = generate_random_product_title("Electronics")
        self.assertEqual(title, "Premium Laptop - Electronics Edition")
        self.assertIn("Electronics", title)

    @patch("src.data_generator.random.choice")
    def test_generate_random_product_title_error(self, mock_choice: MagicMock) -> None:
        """Test generate_random_product_title with error.

        Args:
            mock_choice: Mock for random.choice function.

        Verifies that the function raises an exception on error.
        """
        mock_choice.side_effect = Exception("Mock error")
        with self.assertRaises(Exception):
            generate_random_product_title("Electronics")

    @patch("src.data_generator.random.randint")
    def test_generate_random_date(self, mock_randint: MagicMock) -> None:
        """Test generate_random_date function.

        Args:
            mock_randint: Mock for random.randint function.

        Verifies that the function returns a date within the specified range.
        """
        mock_randint.return_value = 100
        result: datetime.date = generate_random_date(self.start_date, self.end_date)
        expected: datetime.date = self.start_date + datetime.timedelta(days=100)
        self.assertEqual(result, expected)
        self.assertTrue(self.start_date <= result <= self.end_date)

    def test_generate_random_date_invalid_range(self) -> None:
        """Test generate_random_date with invalid date range.

        Verifies that the function raises an exception for invalid date ranges.
        """
        with self.assertRaises(Exception):
            generate_random_date(self.end_date, self.start_date)  # end_date < start_date

    @patch("src.data_generator.fake")
    def test_generate_pii_data(self, mock_fake: MagicMock) -> None:
        """Test generate_pii_data generator function.

        Args:
            mock_fake: Mock for Faker instance.

        Verifies that the generator yields a dictionary with expected PII fields.
        """
        mock_fake.name.return_value = "John Doe"
        mock_fake.email.return_value = "john.doe@example.com"
        mock_fake.phone_number.return_value = "+1-123-456-7890"
        mock_fake.address.return_value = "123 Main St, City, ST 12345"

        pii_gen: Iterator[dict[str, str]] = generate_pii_data()
        pii: dict[str, str] = next(pii_gen)

        expected: dict[str, str] = {
            "customer_name": "John Doe",
            "customer_email": "john.doe@example.com",
            "customer_phone": "+1-123-456-7890",
            "customer_address": "123 Main St, City, ST 12345",
        }
        self.assertEqual(pii, expected)
        self.assertEqual(len(pii), 4)

    @patch("src.data_generator.fake")
    def test_generate_pii_data_error(self, mock_fake: MagicMock) -> None:
        """Test generate_pii_data with error.

        Args:
            mock_fake: Mock for Faker instance.

        Verifies that the generator raises an exception on error.
        """
        mock_fake.name.side_effect = Exception("Mock Faker error")
        pii_gen: Iterator[dict[str, str]] = generate_pii_data()
        with self.assertRaises(Exception):
            next(pii_gen)

    @patch("builtins.open", new_callable=mock_open)
    @patch("src.data_generator.load_dotenv")
    @patch("src.data_generator.os.getenv")
    @patch("src.data_generator.os.makedirs")
    @patch("src.data_generator.random")
    @patch("src.data_generator.fake")
    @patch("src.data_generator.Minio")
    @patch("src.data_generator.get_vault_client")
    @patch("src.data_generator.get_minio_credentials_from_vault")
    @patch("src.data_generator.logger")
    @patch("src.data_generator.time.sleep")
    def test_main_valid_frequency(
        self,
        mock_sleep: MagicMock,
        mock_logger: MagicMock,
        mock_get_minio_creds: MagicMock,
        mock_get_vault: MagicMock,
        mock_minio: MagicMock,
        mock_fake: MagicMock,
        mock_random: MagicMock,
        mock_makedirs: MagicMock,
        mock_getenv: MagicMock,
        mock_load_dotenv: MagicMock,
        mock_open: MagicMock,
    ) -> None:
        """Test main function with valid FREQUENCY.

        Args:
            mock_sleep: Mock for time.sleep function.
            mock_logger: Mock for logger instance.
            mock_get_minio_creds: Mock for get_minio_credentials_from_vault function.
            mock_get_vault: Mock for get_vault_client function.
            mock_minio: Mock for Minio client.
            mock_fake: Mock for Faker instance.
            mock_random: Mock for random module.
            mock_makedirs: Mock for os.makedirs function.
            mock_getenv: Mock for os.getenv function.
            mock_load_dotenv: Mock for load_dotenv function.
            mock_open: Mock for builtins.open function.

        Verifies that main generates data and uploads to MinIO with expected structure.
        """
        # Mock Vault client and credentials
        mock_vault_client = MagicMock()
        mock_get_vault.return_value = mock_vault_client
        mock_get_minio_creds.return_value = ("testkey", "testsecret")

        # Mock environment variables
        mock_getenv.side_effect = [
            "10",  # FREQUENCY
            "localhost:9000",  # MINIO_ENDPOINT
            "False",  # MINIO_SECURE
        ]

        # Set a fixed number of rows for predictable testing
        num_rows = 50

        # Mock MinIO client
        mock_minio_client = MagicMock()
        mock_minio.return_value = mock_minio_client
        mock_minio_client.bucket_exists.return_value = True

        # Mock random behaviors
        mock_random.randint.side_effect = [
            num_rows,  # num_rows
            *repeat(1, num_rows),  # quantity
            *repeat(50, num_rows),  # discount_percentage
            *repeat(100, num_rows * 2),  # random_days for delivery_date and order_date
        ]
        mock_random.uniform.side_effect = [
            *repeat(100.0, num_rows),  # original_price
            *repeat(4.5, num_rows),  # product_rating
        ]
        # Choice calls per row: category, is_best_seller, base, adjective
        choice_values = []
        for _ in range(num_rows):
            choice_values.extend(["Electronics", True, "Laptop", "Premium"])
        mock_random.choice.side_effect = choice_values
        mock_random.choices.side_effect = [
            ["A" * 10]
            for _ in range(num_rows)  # order_id
        ]

        # Mock Faker
        mock_fake.name.return_value = "John Doe"
        mock_fake.email.return_value = "john.doe@example.com"
        mock_fake.phone_number.return_value = "+1-123-456-7890"
        mock_fake.address.return_value = "123 Main St, City, ST 12345"

        # Mock time.sleep to raise KeyboardInterrupt after one iteration
        mock_sleep.side_effect = KeyboardInterrupt

        # Run main
        main()

        # Verify logging
        mock_logger.info.assert_any_call(
            "Starting data generation with frequency of 10 seconds between batches."
        )
        mock_logger.info.assert_any_call(mock_any_string_containing("Uploaded raw/batch_1_"))

        # Verify MinIO upload
        mock_minio_client.put_object.assert_called_once()
        args, kwargs = mock_minio_client.put_object.call_args
        self.assertEqual(args[0], "data-platform")  # bucket_name
        self.assertTrue(args[1].startswith("raw/batch_1_"))  # object_name
        self.assertEqual(kwargs["content_type"], "text/csv")

        # Capture the DataFrame from the put_object call
        csv_buffer: io.BytesIO = args[2]
        csv_buffer.seek(0)
        df = pd.read_csv(csv_buffer)  # type: ignore[reportUnknownMemberType]

        # Verify DataFrame structure
        self.assertEqual(len(df), num_rows)
        expected_columns = [
            "order_id",
            "customer_name",
            "customer_email",
            "customer_phone",
            "customer_address",
            "product_title",
            "product_rating",
            "discounted_price",
            "original_price",
            "discount_percentage",
            "is_best_seller",
            "delivery_date",
            "data_collected_at",
            "product_category",
            "quantity",
            "order_date",
        ]
        self.assertEqual(list(df.columns), expected_columns)

        # Verify sample row
        sample_row = df.iloc[0]
        self.assertEqual(sample_row["order_id"], "A" * 10)
        self.assertEqual(sample_row["customer_name"], "John Doe")
        self.assertEqual(sample_row["product_title"], "Premium Laptop - Electronics Edition")
        self.assertEqual(sample_row["product_category"], "Electronics")
        self.assertEqual(sample_row["quantity"], 1)

    @patch("builtins.open", new_callable=mock_open)
    @patch("src.data_generator.os.getenv")
    @patch("src.data_generator.logger")
    def test_main_missing_frequency(
        self,
        mock_logger: MagicMock,
        mock_getenv: MagicMock,
        mock_open: MagicMock,
    ) -> None:
        """Test main with missing FREQUENCY in .env.

        Args:
            mock_logger: Mock for logger instance.
            mock_getenv: Mock for os.getenv function.
            mock_open: Mock for builtins.open function.

        Verifies that main raises ValueError for missing FREQUENCY.
        """
        mock_getenv.return_value = None
        with self.assertRaises(ValueError) as cm:
            main()
        self.assertEqual(str(cm.exception), "FREQUENCY not found in .env file.")
        mock_logger.error.assert_called_with(
            "FREQUENCY not found in .env file. Please add FREQUENCY=<integer> to .env (seconds)."
        )

    @patch("builtins.open", new_callable=mock_open)
    @patch("src.data_generator.os.getenv")
    @patch("src.data_generator.logger")
    def test_main_invalid_frequency(
        self,
        mock_logger: MagicMock,
        mock_getenv: MagicMock,
        mock_open: MagicMock,
    ) -> None:
        """Test main with invalid FREQUENCY in .env.

        Args:
            mock_logger: Mock for logger instance.
            mock_getenv: Mock for os.getenv function.
            mock_open: Mock for builtins.open function.

        Verifies that main raises ValueError for invalid FREQUENCY.
        """
        mock_getenv.return_value = "invalid"
        with self.assertRaises(ValueError) as cm:
            main()
        self.assertEqual(
            str(cm.exception),
            "Invalid FREQUENCY value in .env. Must be a positive integer (seconds).",
        )
        mock_logger.error.assert_called_with(
            "Invalid FREQUENCY value in .env. Must be a positive integer (seconds)."
        )


if __name__ == "__main__":
    unittest.main()
