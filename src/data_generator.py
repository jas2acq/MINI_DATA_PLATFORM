"""Sales data generator for testing and development purposes.

Security Note: This module uses Python's random module and Faker for generating
test data. These pseudorandom generators are NOT cryptographically secure and
should ONLY be used for test data generation, not for security-sensitive operations
like token generation or cryptographic keys.
"""
import datetime
import io
import logging
import os
import random  # nosem: python.lang.security.audit.non-crypto-random-module-used
import string
import time
from collections.abc import Iterator
from typing import Any

import hvac
import pandas as pd
from dotenv import load_dotenv
from faker import Faker  # nosem: python.lang.security.audit.non-crypto-random-module-used
from minio.error import S3Error

from minio import Minio

# Configure logging to append to a file in logs directory
os.makedirs("MINI_DATA_PLATFORM/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("MINI_DATA_PLATFORM/logs/sales_data_generator.log", mode="a"),
        logging.StreamHandler(),
    ],
)
logger: logging.Logger = logging.getLogger(__name__)

# Initialize Faker with en_US locale
fake: Faker = Faker("en_US")

# Lists for random product data generation
PRODUCT_CATEGORIES: list[str] = [
    "Electronics",
    "Books",
    "Clothing",
    "Home & Kitchen",
    "Toys",
    "Beauty",
    "Sports",
]
PRODUCT_BASES: list[str] = [
    "Laptop",
    "Smartphone",
    "Book",
    "T-Shirt",
    "Blender",
    "Toy Car",
    "Lipstick",
    "Running Shoes",
]


def generate_random_product_title(category: str) -> str:
    """Generate a random product title based on a category.

    Args:
        category: The product category to include in the title.

    Returns:
        A formatted product title string.

    Raises:
        Exception: If an error occurs during title generation.
    """
    try:
        base: str = random.choice(PRODUCT_BASES)
        adjective: str = random.choice(
            ["Premium", "Budget", "High-End", "Eco-Friendly", "Portable", "Durable"]
        )
        return f"{adjective} {base} - {category} Edition"
    except Exception as e:
        logger.error(f"Error generating product title: {str(e)}")
        raise


def generate_random_date(start_date: datetime.date, end_date: datetime.date) -> datetime.date:
    """Generate a random date between start_date and end_date.

    Args:
        start_date: The earliest possible date.
        end_date: The latest possible date.

    Returns:
        A random date between start_date and end_date.

    Raises:
        Exception: If an error occurs during date generation.
    """
    try:
        delta: datetime.timedelta = end_date - start_date
        random_days: int = random.randint(0, delta.days)
        return start_date + datetime.timedelta(days=random_days)
    except Exception as e:
        logger.error(f"Error generating random date: {str(e)}")
        raise


def generate_pii_data() -> Iterator[dict[str, str]]:
    """Generate PII data using Faker.

    Yields:
        A dictionary containing fake customer_name, customer_email, customer_phone,
        and customer_address.

    Raises:
        Exception: If an error occurs during PII data generation.
    """
    while True:
        try:
            name: str = fake.name()
            yield {
                "customer_name": name,
                "customer_email": fake.email(),
                "customer_phone": fake.phone_number(),
                "customer_address": fake.address().replace("\n", ", "),
            }
        except Exception as e:
            logger.error(f"Error generating PII data: {str(e)}")
            raise


def get_vault_client() -> hvac.Client:
    """Initialize and authenticate Vault client.

    Returns:
        Authenticated hvac.Client instance.

    Raises:
        ValueError: If Vault environment variables are missing or authentication fails.
        Exception: If Vault client initialization fails.
    """
    vault_addr: str | None = os.getenv("VAULT_ADDR")
    vault_token: str | None = os.getenv("VAULT_DEV_ROOT_TOKEN_ID")

    if not vault_addr:
        logger.error(
            "VAULT_ADDR not found in .env file. Please add VAULT_ADDR=<vault_url> to .env."
        )
        raise ValueError("VAULT_ADDR not found in .env file.")
    if not vault_token:
        logger.error(
            "VAULT_DEV_ROOT_TOKEN_ID not found in .env file. Please add VAULT_DEV_ROOT_TOKEN_ID=<token> to .env."
        )
        raise ValueError("VAULT_DEV_ROOT_TOKEN_ID not found in .env file.")

    try:
        client: hvac.Client = hvac.Client(url=vault_addr, token=vault_token)
        if not client.is_authenticated():
            logger.error("Vault authentication failed. Check VAULT_DEV_ROOT_TOKEN_ID.")
            raise ValueError("Vault authentication failed.")
        logger.info("Successfully authenticated with Vault")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Vault client: {str(e)}")
        raise


def get_minio_credentials_from_vault(vault_client: hvac.Client) -> tuple[str, str]:
    """Fetch MinIO credentials from Vault.

    Args:
        vault_client: Authenticated Vault client.

    Returns:
        Tuple of (access_key, secret_key).

    Raises:
        Exception: If fetching credentials from Vault fails.
    """
    try:
        secret_response = vault_client.secrets.kv.v2.read_secret_version(
            path="minio", mount_point="kv"
        )
        secrets: dict = secret_response["data"]["data"]
        access_key: str = secrets["root_user"]
        secret_key: str = secrets["root_password"]
        logger.info("Successfully fetched MinIO credentials from Vault")
        return access_key, secret_key
    except Exception as e:
        logger.error(f"Failed to fetch MinIO credentials from Vault: {str(e)}")
        raise


def load_and_validate_env() -> tuple[int, str, bool]:
    """Load and validate environment variables from .env file.

    Returns:
        Tuple of (frequency_int, minio_endpoint, minio_secure).

    Raises:
        ValueError: If any required environment variable is missing or invalid.
    """
    load_dotenv()
    frequency: str | None = os.getenv("FREQUENCY")
    minio_endpoint: str | None = os.getenv("MINIO_ENDPOINT")
    minio_secure: str | None = os.getenv("MINIO_SECURE", "False")

    if not frequency:
        logger.error(
            "FREQUENCY not found in .env file. Please add FREQUENCY=<integer> to .env (seconds)."
        )
        raise ValueError("FREQUENCY not found in .env file.")
    if not minio_endpoint:
        logger.error(
            "MINIO_ENDPOINT not found in .env file. Please add MINIO_ENDPOINT=<endpoint> to .env."
        )
        raise ValueError("MINIO_ENDPOINT not found in .env file.")

    try:
        frequency_int: int = int(frequency)
        if frequency_int <= 0:
            raise ValueError("FREQUENCY must be a positive integer.")
    except ValueError:
        logger.error("Invalid FREQUENCY value in .env. Must be a positive integer (seconds).")
        raise ValueError(
            "Invalid FREQUENCY value in .env. Must be a positive integer (seconds)."
        ) from None

    try:
        minio_secure_bool: bool = minio_secure.lower() == "true"
    except AttributeError:
        logger.error("Invalid MINIO_SECURE value in .env. Must be 'True' or 'False'.")
        raise ValueError("Invalid MINIO_SECURE value in .env. Must be 'True' or 'False'.") from None

    return frequency_int, minio_endpoint, minio_secure_bool


def initialize_minio_client(endpoint: str, access_key: str, secret_key: str, secure: bool) -> Minio:
    """Initialize MinIO client and ensure the data-platform bucket exists.

    Args:
        endpoint: MinIO server endpoint.
        access_key: MinIO access key.
        secret_key: MinIO secret key.
        secure: Whether to use HTTPS.

    Returns:
        Initialized MinIO client.

    Raises:
        S3Error: If an error occurs during MinIO operations.
        Exception: If MinIO client initialization fails.
    """
    try:
        minio_client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        bucket_name: str = "data-platform"
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            logger.info(f"Created MinIO bucket: {bucket_name}")
        return minio_client
    except S3Error as e:
        logger.error(f"Error checking or creating MinIO bucket data-platform: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize MinIO client: {str(e)}")
        raise


def generate_batch_data(
    pii_generator: Iterator[dict[str, str]],
    start_date: datetime.date,
    end_date: datetime.date,
    batch_num: int,
) -> tuple[pd.DataFrame, str]:
    """Generate a batch of sales data and return the DataFrame and object name.

    Args:
        pii_generator: Iterator yielding PII data dictionaries.
        start_date: Earliest date for random date generation.
        end_date: Latest date for random date generation.
        batch_num: Batch number for object naming.

    Returns:
        Tuple of (DataFrame with batch data, MinIO object name).

    Raises:
        Exception: If an error occurs during data generation.
    """
    try:
        num_rows: int = random.randint(50, 200)
        data: list[dict[str, Any]] = []

        for _ in range(num_rows):
            category: str = random.choice(PRODUCT_CATEGORIES)
            original_price: float = round(random.uniform(20, 2000), 2)
            discount_percentage: int = random.randint(0, 70)
            discounted_price: float = round(original_price * (1 - discount_percentage / 100), 2)
            product_rating: float = round(random.uniform(1.0, 5.0), 1)
            is_best_seller: bool = random.choice([True, False])
            delivery_date: str = generate_random_date(start_date, end_date).strftime("%Y-%m-%d")
            data_collected_at: str = datetime.date.today().strftime("%Y-%m-%d")
            product_title: str = generate_random_product_title(category)

            pii: dict[str, str] = next(pii_generator)

            order_id: str = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
            quantity: int = random.randint(1, 5)
            order_date: str = generate_random_date(start_date, end_date).strftime("%Y-%m-%d")

            row: dict[str, Any] = {
                "order_id": order_id,
                "customer_name": pii["customer_name"],
                "customer_email": pii["customer_email"],
                "customer_phone": pii["customer_phone"],
                "customer_address": pii["customer_address"],
                "product_title": product_title,
                "product_rating": product_rating,
                "discounted_price": discounted_price,
                "original_price": original_price,
                "discount_percentage": discount_percentage,
                "is_best_seller": is_best_seller,
                "delivery_date": delivery_date,
                "data_collected_at": data_collected_at,
                "product_category": category,
                "quantity": quantity,
                "order_date": order_date,
            }
            data.append(row)

        df: pd.DataFrame = pd.DataFrame(data)
        timestamp: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        object_name: str = f"raw/batch_{batch_num}_{timestamp}.csv"
        return df, object_name
    except Exception as e:
        logger.error(f"Error generating batch {batch_num}: {str(e)}")
        raise


def upload_batch_to_minio(minio_client: Minio, df: pd.DataFrame, object_name: str) -> None:
    """Upload a batch DataFrame to MinIO as a CSV.

    Args:
        minio_client: Initialized MinIO client.
        df: DataFrame containing batch data.
        object_name: MinIO object name (path in bucket).

    Raises:
        S3Error: If an error occurs during upload.
    """
    try:
        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        minio_client.put_object(
            "data-platform",
            object_name,
            csv_buffer,
            length=csv_buffer.getbuffer().nbytes,
            content_type="text/csv",
        )
        logger.info(f"Uploaded {object_name} with {len(df)} rows to MinIO bucket data-platform.")
    except S3Error as e:
        logger.error(f"Error uploading {object_name} to MinIO bucket data-platform: {str(e)}")
        raise


def main() -> None:
    """Main function to generate sales data CSVs and upload to MinIO bucket.

    Orchestrates data generation and upload by reading environment variables,
    fetching credentials from Vault, initializing MinIO client, and generating
    batches at specified intervals.

    Raises:
        ValueError: If required environment variables are missing or invalid.
        S3Error: If an error occurs during MinIO operations.
        Exception: If an error occurs during batch generation or Vault operations.
    """
    try:
        # Load and validate environment variables
        frequency, minio_endpoint, minio_secure = load_and_validate_env()

        # Initialize Vault client and fetch MinIO credentials
        vault_client = get_vault_client()
        minio_access_key, minio_secret_key = get_minio_credentials_from_vault(vault_client)

        # Initialize MinIO client
        minio_client = initialize_minio_client(
            minio_endpoint, minio_access_key, minio_secret_key, minio_secure
        )

        # Initialize PII data generator
        pii_generator: Iterator[dict[str, str]] = generate_pii_data()

        # Generate batches indefinitely with frequency delay
        batch_num: int = 1
        start_date: datetime.date = datetime.date(2023, 1, 1)
        end_date: datetime.date = datetime.date.today()

        logger.info(
            f"Starting data generation with frequency of {frequency} seconds between batches."
        )

        while True:
            try:
                # Generate batch data
                df, object_name = generate_batch_data(
                    pii_generator, start_date, end_date, batch_num
                )

                # Upload to MinIO
                upload_batch_to_minio(minio_client, df, object_name)

                batch_num += 1
                time.sleep(frequency)

            except KeyboardInterrupt:
                logger.info("Received KeyboardInterrupt. Stopping data generation.")
                break
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {str(e)}")
                raise

    except Exception as e:
        logger.critical(f"Script execution failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
