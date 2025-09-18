import unittest
import datetime
import tempfile
import pandas as pd
from unittest.mock import patch, MagicMock, mock_open
from typing import Dict, Iterator, Any
from itertools import repeat
from src.data_generator import (
    generate_random_product_title,
    generate_random_date,
    generate_pii_data,
    main
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
    """Unit tests for data-generator.py.

    Tests the functionality of data generation functions and main logic.
    """

    def setUp(self) -> None:
        """Set up test fixtures before each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_env_file = mock_open(read_data="FREQUENCY=10")
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

        pii_gen: Iterator[Dict[str, str]] = generate_pii_data()
        pii: Dict[str, str] = next(pii_gen)

        expected: Dict[str, str] = {
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
        pii_gen: Iterator[Dict[str, str]] = generate_pii_data()
        with self.assertRaises(Exception):
            next(pii_gen)

    @patch("builtins.open", new_callable=mock_open)
    @patch("src.data_generator.load_dotenv")
    @patch("src.data_generator.os.getenv")
    @patch("src.data_generator.os.makedirs")
    @patch("src.data_generator.random")
    @patch("src.data_generator.fake")
    @patch("pandas.DataFrame.to_csv")
    @patch("src.data_generator.logger")
    @patch("src.data_generator.time.sleep")
    def test_main_valid_frequency(
        self,
        mock_sleep: MagicMock,
        mock_logger: MagicMock,
        mock_to_csv: MagicMock,
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
            mock_to_csv: Mock for DataFrame.to_csv method.
            mock_fake: Mock for Faker instance.
            mock_random: Mock for random module.
            mock_makedirs: Mock for os.makedirs function.
            mock_getenv: Mock for os.getenv function.
            mock_load_dotenv: Mock for load_dotenv function.
            mock_open: Mock for builtins.open function.

        Verifies that main generates a CSV with expected data and logs correctly.
        """
        # Mock environment variable
        mock_getenv.return_value = "10"

        # Mock random behaviors
        mock_random.randint.side_effect = [
            50,  # num_rows
            *repeat(1, 50),  # quantity for 50 rows
            *repeat(50, 50),  # discount_percentage for 50 rows
            *repeat(1, 100),  # random_days for 50 rows (2 calls per row for delivery_date and order_date)
        ]
        mock_random.uniform.side_effect = [
            *repeat(100.0, 50),  # original_price for 50 rows
            *repeat(4.5, 50),  # product_rating for 50 rows
        ]
        mock_random.choice.side_effect = [
            *repeat("Electronics", 50),  # category for 50 rows
            *repeat("Laptop", 50),  # base for 50 rows
            *repeat("Premium", 50),  # adjective for 50 rows
            *repeat(True, 50),  # is_best_seller for 50 rows
        ]
        mock_random.choices.return_value = ["A" * 10]  # order_id (single value, reused for simplicity)

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
        mock_logger.info.assert_any_call("Starting data generation with frequency of 10 seconds between batches.")
        mock_logger.info.assert_any_call(mock_any_string_containing("Generated MINI_DATA_PLATFORM/data/raw/batch_1_"))

        # Verify CSV output
        mock_to_csv.assert_called_once()
        args, _ = mock_to_csv.call_args
        csv_path: str = args[0]
        self.assertTrue(csv_path.startswith("MINI_DATA_PLATFORM/data/raw/batch_1_"))

        # Verify DataFrame structure
        df: pd.DataFrame = mock_to_csv.call_args[0][0]
        self.assertEqual(len(df), 50)  # num_rows
        expected_columns: list[str] = [
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
        sample_row: pd.Series = df.iloc[0]
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
        self.assertEqual(str(cm.exception), "Invalid FREQUENCY value in .env. Must be a positive integer (seconds).")
        mock_logger.error.assert_called_with(
            "Invalid FREQUENCY value in .env. Must be a positive integer (seconds)."
        )


if __name__ == "__main__":
    unittest.main()