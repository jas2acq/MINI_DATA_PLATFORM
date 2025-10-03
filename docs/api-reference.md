# API Reference

## Table of Contents
- [Utils Module](#utils-module)
- [Ingestion Module](#ingestion-module)
- [Validation Module](#validation-module)
- [Transformation Module](#transformation-module)
- [Loading Module](#loading-module)
- [Pipeline Module](#pipeline-module)

## Utils Module

### helpers.py

#### `setup_logger(name: str, log_file: str) -> logging.Logger`
Configure module-specific logger with file and console handlers.

**Parameters:**
- `name`: Logger name (e.g., 'ingestion')
- `log_file`: Path to log file (e.g., 'logs/ingestion.log')

**Returns:**
- Configured Logger instance

**Example:**
```python
logger = setup_logger('ingestion', 'logs/ingestion.log')
logger.info("Starting ingestion process")
```

#### `get_vault_client() -> hvac.Client`
Initialize HashiCorp Vault client with authentication.

**Returns:**
- Authenticated Vault client

**Raises:**
- `VaultError`: If authentication fails

**Example:**
```python
vault_client = get_vault_client()
secret = vault_client.secrets.kv.v2.read_secret_version(path='minio')
```

### schemas.py

#### `SalesRecord(BaseModel)`
Pydantic model for sales data validation.

**Fields:**
- `order_id`: str
- `customer_email`: EmailStr
- `customer_phone`: str
- `customer_name`: str
- `customer_address`: str
- `product_title`: str
- `product_category`: str
- `product_rating`: float (1.0-5.0)
- `is_best_seller`: bool
- `quantity`: int (≥1)
- `original_price`: float (>0, max 2 decimal places)
- `discounted_price`: float (>0, max 2 decimal places)
- `discount_percentage`: int (0-100)
- `order_date`: date
- `delivery_date`: date (must be ≥ order_date)
- `data_collected_at`: date

**Validators:**
- Email format validation
- Positive quantity check
- Price range validation

### notifications.py

#### `send_success_notification(context: dict[str, Any]) -> None`
Send email notification on DAG task success.

**Parameters:**
- `context`: Airflow context dictionary

#### `send_failure_notification(context: dict[str, Any]) -> None`
Send email notification on DAG task failure.

**Parameters:**
- `context`: Airflow context dictionary

## Ingestion Module

### minio_client.py

#### `get_minio_credentials(vault_client: hvac.Client) -> dict`
Retrieve MinIO credentials from Vault.

**Parameters:**
- `vault_client`: Authenticated Vault client

**Returns:**
- Dict with `access_key` and `secret_key`

#### `get_minio_client(vault_client: hvac.Client) -> Minio`
Create MinIO client with Vault credentials.

**Parameters:**
- `vault_client`: Authenticated Vault client

**Returns:**
- Configured MinIO client

#### `get_object_size(minio_client: Minio, object_key: str) -> int`
Get object size in bytes.

**Parameters:**
- `minio_client`: MinIO client
- `object_key`: S3 object key

**Returns:**
- Object size in bytes

#### `get_raw_data(minio_client: Minio, object_key: str, use_chunking: bool | None = None, chunk_size: int = 10000) -> pd.DataFrame | Iterator[pd.DataFrame]`
Download CSV from MinIO as DataFrame or chunked iterator.

**Parameters:**
- `minio_client`: MinIO client
- `object_key`: S3 object key
- `use_chunking`: Force chunking mode (None=auto-detect based on size)
- `chunk_size`: Number of rows per chunk (default: 10000)

**Returns:**
- DataFrame if <1GB (or use_chunking=False), Iterator of DataFrames if >1GB (or use_chunking=True)

**Notes:**
- Automatically parses date columns (order_date, delivery_date, data_collected_at) to datetime64
- Only parses columns that exist in the CSV to avoid errors
- Uses chunking for files >1GB to manage memory efficiently

## Validation Module

### validator.py

#### `validate_data(data: pd.DataFrame | Iterator[pd.DataFrame], schema: Type[BaseModel]) -> tuple | Iterator[tuple]`
Validate DataFrame against Pydantic schema.

**Parameters:**
- `data`: DataFrame or iterator of DataFrames (for chunked processing)
- `schema`: Pydantic model class

**Returns:**
- Tuple of (valid_df, invalid_df) or iterator of tuples for chunked data

**Notes:**
- Preserves pandas datetime64 types after validation
- Converts Pydantic date objects back to datetime64 for compatibility
- Invalid records include `validation_error` column with failure details

## Transformation Module

### transformer.py

#### `transform_sales_data(df: pd.DataFrame) -> pd.DataFrame`
Apply all transformations to sales data.

**Parameters:**
- `df`: Input DataFrame

**Returns:**
- Transformed DataFrame

#### `_hash_email(email: str) -> str`
Hash email address using SHA-256.

**Returns:**
- 64-character hexadecimal hash (case-insensitive)

#### `_redact_phone(phone: str) -> str`
Redact phone number, keeping last 4 digits.

**Returns:**
- Format: `***-***-XXXX` where XXXX is last 4 digits

#### `_redact_address(address: str) -> str`
Redact address with asterisk pattern.

**Returns:**
- Redacted pattern: `*** **** **`

## Loading Module

### postgres_loader.py

#### `get_postgres_credentials(vault_client: hvac.Client) -> dict`
Retrieve PostgreSQL credentials from Vault.

#### `get_postgres_connection(vault_client: hvac.Client) -> connection`
Create PostgreSQL connection with SSL.

#### `upsert_data(vault_client: hvac.Client, df: pd.DataFrame) -> None`
Upsert data to PostgreSQL star schema.

**Parameters:**
- `vault_client`: Authenticated Vault client
- `df`: Transformed DataFrame

## Pipeline Module

### pipeline.py

#### `run_pipeline(file_key: str) -> None`
Execute complete ETL pipeline for a single file.

**Parameters:**
- `file_key`: MinIO object key (e.g., 'raw/batch_1.csv')

**Raises:**
- `ValueError`: If all records fail validation

#### `save_invalid_data_to_quarantine(minio_client, invalid_df, original_file_key: str) -> None`
Save invalid records to quarantine prefix.

**Parameters:**
- `minio_client`: MinIO client
- `invalid_df`: DataFrame with invalid records
- `original_file_key`: Original file key
