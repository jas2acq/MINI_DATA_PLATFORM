"""PostgreSQL loading module for upserting data into analytics database.

This module handles database connections and upserts data into the star schema,
managing dimension tables first, then fact tables.
"""

import os
from collections.abc import Iterator

import hvac
import pandas as pd
import psycopg2
from psycopg2.extensions import connection as PgConnection

from dags.src.utils.helpers import setup_logger

# Initialize logger
logger = setup_logger("loading", "logs/loading.log")


def get_postgres_credentials(vault_client: hvac.Client) -> dict[str, str]:
    """Retrieve PostgreSQL credentials from Vault.

    Args:
        vault_client: Authenticated Vault client instance.

    Returns:
        Dictionary containing database connection parameters.

    Raises:
        hvac.exceptions.VaultError: If secret retrieval fails.
        KeyError: If required secret keys are missing.
    """
    try:
        # Read PostgreSQL secrets from Vault
        secret_response = vault_client.secrets.kv.v2.read_secret_version(
            path="postgres_analytics",
            mount_point="kv",
        )
        secrets = secret_response["data"]["data"]

        credentials = {
            "host": secrets.get("host", os.getenv("POSTGRES_ANALYTICS_HOST", "postgres-analytics")),
            "port": secrets.get("port", os.getenv("POSTGRES_ANALYTICS_PORT", "5432")),
            "dbname": secrets.get("dbname", os.getenv("POSTGRES_ANALYTICS_DB", "shadowpostgresdb")),
            "user": secrets["user"],
            "password": secrets["password"],
        }

        logger.info("Successfully retrieved PostgreSQL credentials from Vault")
        return credentials

    except hvac.exceptions.VaultError as e:
        logger.error(f"Failed to retrieve PostgreSQL credentials from Vault: {str(e)}")
        raise
    except KeyError as e:
        logger.error(f"Missing required key in PostgreSQL secrets: {str(e)}")
        raise


def get_postgres_connection(vault_client: hvac.Client) -> PgConnection:
    """Establish and return a PostgreSQL database connection.

    Uses strict SSL certificate verification for secure connections.

    Args:
        vault_client: Authenticated Vault client instance.

    Returns:
        psycopg2 connection object.

    Raises:
        psycopg2.Error: If connection fails.
    """
    try:
        credentials = get_postgres_credentials(vault_client)

        # Get CA certificate path for SSL verification
        ca_cert_path = os.getenv("POSTGRES_CA_CERT", "/opt/airflow/certs/ca.crt")

        connection_params = {
            "host": credentials["host"],
            "port": credentials["port"],
            "dbname": credentials["dbname"],
            "user": credentials["user"],
            "password": credentials["password"],
            "sslmode": "verify-full",  # Enforce strict SSL certificate verification
            "connect_timeout": 30,
        }

        # Add CA certificate if it exists
        if os.path.exists(ca_cert_path):
            connection_params["sslrootcert"] = ca_cert_path
            logger.info(f"Using CA certificate for SSL verification: {ca_cert_path}")
        else:
            logger.warning(
                f"CA certificate not found at {ca_cert_path}, "
                "SSL verification may fail"
            )

        connection = psycopg2.connect(**connection_params)

        logger.info(
            f"Successfully connected to PostgreSQL at {credentials['host']} "
            "with SSL certificate verification"
        )
        return connection

    except psycopg2.Error as e:
        logger.error(f"PostgreSQL connection error: {str(e)}")
        raise


def upsert_dimension_customer(
    conn: PgConnection,
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Upsert customer dimension data and return DataFrame with customer_ids.

    Args:
        conn: PostgreSQL connection.
        df: DataFrame with customer data.

    Returns:
        DataFrame with customer_id column added.

    Raises:
        psycopg2.Error: If database operation fails.
    """
    logger.info(f"Upserting {len(df)} customer records")

    cursor = conn.cursor()

    try:
        # Get unique customers from the DataFrame
        customers = df[
            [
                "customer_name",
                "customer_email_hash",
                "customer_phone_redacted",
                "customer_address_redacted",
            ]
        ].drop_duplicates(subset=["customer_email_hash"])

        # Upsert each customer
        for _, row in customers.iterrows():
            cursor.execute(
                """
                INSERT INTO dim_customer (customer_name, email_hash, phone_redacted, address_redacted)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (email_hash)
                DO UPDATE SET
                    customer_name = EXCLUDED.customer_name,
                    phone_redacted = EXCLUDED.phone_redacted,
                    address_redacted = EXCLUDED.address_redacted,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING customer_id
                """,
                (
                    row["customer_name"],
                    row["customer_email_hash"],
                    row["customer_phone_redacted"],
                    row["customer_address_redacted"],
                ),
            )
            customer_id = cursor.fetchone()[0]

            # Add customer_id to original DataFrame
            df.loc[
                df["customer_email_hash"] == row["customer_email_hash"],
                "customer_id",
            ] = customer_id

        conn.commit()
        logger.info(f"Successfully upserted {len(customers)} unique customers")
        return df

    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Error upserting customers: {str(e)}")
        raise
    finally:
        cursor.close()


def upsert_dimension_product(
    conn: PgConnection,
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Upsert product dimension data and return DataFrame with product_ids.

    Args:
        conn: PostgreSQL connection.
        df: DataFrame with product data.

    Returns:
        DataFrame with product_id column added.

    Raises:
        psycopg2.Error: If database operation fails.
    """
    logger.info("Upserting product records")

    cursor = conn.cursor()

    try:
        # Get unique products
        products = df[
            ["product_title", "product_rating", "product_category", "is_best_seller"]
        ].drop_duplicates(subset=["product_title", "product_category"])

        for _, row in products.iterrows():
            cursor.execute(
                """
                INSERT INTO dim_product
                    (product_title, product_rating, product_category, is_best_seller)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (product_title, product_category)
                DO UPDATE SET
                    product_rating = EXCLUDED.product_rating,
                    is_best_seller = EXCLUDED.is_best_seller,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING product_id
                """,
                (
                    row["product_title"],
                    row["product_rating"],
                    row["product_category"],
                    row["is_best_seller"],
                ),
            )
            product_id = cursor.fetchone()[0]

            # Add product_id to DataFrame
            mask = (df["product_title"] == row["product_title"]) & (
                df["product_category"] == row["product_category"]
            )
            df.loc[mask, "product_id"] = product_id

        conn.commit()
        logger.info(f"Successfully upserted {len(products)} unique products")
        return df

    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Error upserting products: {str(e)}")
        raise
    finally:
        cursor.close()


def upsert_dimension_date(
    conn: PgConnection,
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Upsert date dimension data and return DataFrame with date_ids.

    Args:
        conn: PostgreSQL connection.
        df: DataFrame with date columns.

    Returns:
        DataFrame with order_date_id and delivery_date_id columns.

    Raises:
        psycopg2.Error: If database operation fails.
    """
    logger.info("Upserting date records")

    cursor = conn.cursor()

    try:
        # Get unique dates from both order_date and delivery_date
        dates = pd.concat([df["order_date"], df["delivery_date"]]).dropna().unique()

        for date_val in dates:
            date_val = pd.to_datetime(date_val)

            cursor.execute(
                """
                INSERT INTO dim_date
                    (date, year, month, day, quarter, day_of_week, week_of_year, is_weekend)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date) DO NOTHING
                """,
                (
                    date_val.date(),
                    date_val.year,
                    date_val.month,
                    date_val.day,
                    (date_val.month - 1) // 3 + 1,  # Calculate quarter
                    date_val.dayofweek,
                    date_val.isocalendar()[1],  # Week of year
                    date_val.dayofweek >= 5,  # Weekend check
                ),
            )

        conn.commit()

        # Map dates to date_ids
        cursor.execute("SELECT date_id, date FROM dim_date")
        date_mapping = {date: date_id for date_id, date in cursor.fetchall()}

        df["order_date_id"] = df["order_date"].apply(
            lambda x: date_mapping.get(pd.to_datetime(x).date()) if pd.notna(x) else None
        )
        df["delivery_date_id"] = df["delivery_date"].apply(
            lambda x: date_mapping.get(pd.to_datetime(x).date()) if pd.notna(x) else None
        )

        logger.info(f"Successfully upserted {len(dates)} unique dates")
        return df

    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Error upserting dates: {str(e)}")
        raise
    finally:
        cursor.close()


def upsert_fact_sales(
    conn: PgConnection,
    df: pd.DataFrame,
) -> None:
    """Upsert fact sales data.

    Args:
        conn: PostgreSQL connection.
        df: DataFrame with complete sales fact data (including dimension IDs).

    Raises:
        psycopg2.Error: If database operation fails.
    """
    logger.info(f"Upserting {len(df)} sales fact records")

    cursor = conn.cursor()

    try:
        for _, row in df.iterrows():
            cursor.execute(
                """
                INSERT INTO fact_sales (
                    order_id, customer_id, product_id, order_date_id, delivery_date_id,
                    quantity, discounted_price, original_price, discount_percentage,
                    profit, data_collected_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (order_id)
                DO UPDATE SET
                    customer_id = EXCLUDED.customer_id,
                    product_id = EXCLUDED.product_id,
                    order_date_id = EXCLUDED.order_date_id,
                    delivery_date_id = EXCLUDED.delivery_date_id,
                    quantity = EXCLUDED.quantity,
                    discounted_price = EXCLUDED.discounted_price,
                    original_price = EXCLUDED.original_price,
                    discount_percentage = EXCLUDED.discount_percentage,
                    profit = EXCLUDED.profit,
                    data_collected_at = EXCLUDED.data_collected_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    row["order_id"],
                    int(row["customer_id"]),
                    int(row["product_id"]),
                    int(row["order_date_id"]),
                    int(row["delivery_date_id"]) if pd.notna(row["delivery_date_id"]) else None,
                    row["quantity"],
                    row["discounted_price"],
                    row["original_price"],
                    row["discount_percentage"],
                    row["profit"],
                    pd.to_datetime(row["data_collected_at"]).date(),
                ),
            )

        conn.commit()
        logger.info(f"Successfully upserted {len(df)} sales records")

    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Error upserting sales facts: {str(e)}")
        raise
    finally:
        cursor.close()


def upsert_data(
    vault_client: hvac.Client,
    data: pd.DataFrame | Iterator[pd.DataFrame],
) -> None:
    """Upsert data into PostgreSQL star schema.

    Loads dimension tables first (customer, product, date), then fact table.
    Handles both single DataFrames and chunked iterators.

    Args:
        vault_client: Authenticated Vault client.
        data: DataFrame or iterator of DataFrames to upsert.

    Raises:
        psycopg2.Error: If database operations fail.
    """
    conn = None

    try:
        conn = get_postgres_connection(vault_client)

        if isinstance(data, pd.DataFrame):
            _upsert_single_dataframe(conn, data)
        elif isinstance(data, Iterator):
            _upsert_chunked_dataframes(conn, data)
        else:
            raise TypeError(
                f"Data must be pd.DataFrame or Iterator[pd.DataFrame], got {type(data)}"
            )

    finally:
        if conn:
            conn.close()
            logger.info("PostgreSQL connection closed")


def _upsert_single_dataframe(conn: PgConnection, df: pd.DataFrame) -> None:
    """Upsert a single DataFrame into the database.

    Args:
        conn: PostgreSQL connection.
        df: DataFrame to upsert.
    """
    logger.info(f"Upserting single DataFrame with {len(df)} records")

    # Upsert dimensions (in order)
    df = upsert_dimension_customer(conn, df)
    df = upsert_dimension_product(conn, df)
    df = upsert_dimension_date(conn, df)

    # Upsert fact table
    upsert_fact_sales(conn, df)

    logger.info("Single DataFrame upsert complete")


def _upsert_chunked_dataframes(
    conn: PgConnection,
    df_iterator: Iterator[pd.DataFrame],
) -> None:
    """Upsert chunked DataFrames into the database.

    Args:
        conn: PostgreSQL connection.
        df_iterator: Iterator yielding DataFrames.
    """
    logger.info("Starting chunked upsert")
    chunk_num = 0

    for chunk_df in df_iterator:
        chunk_num += 1
        logger.info(f"Upserting chunk {chunk_num} with {len(chunk_df)} records")

        _upsert_single_dataframe(conn, chunk_df)

        logger.info(f"Chunk {chunk_num} upsert complete")

    logger.info(f"Completed upsert of {chunk_num} chunks")
