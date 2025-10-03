# Mini Data Platform

A secure, scalable ETL pipeline for processing sales data from MinIO object storage into a PostgreSQL analytics database, orchestrated with Apache Airflow.

## Architecture Overview

The platform implements a complete ETL (Extract, Transform, Load) workflow with:

- **Data Source**: MinIO object storage (S3-compatible)
- **Data Pipeline**: Python-based ETL with Pydantic validation
- **Orchestration**: Apache Airflow with daily scheduling
- **Data Warehouse**: PostgreSQL with star schema
- **Visualization**: Metabase for analytics dashboards
- **Security**: HashiCorp Vault for secrets management, TLS encryption for all connections

## Features

- ✅ Event-driven architecture using Airflow S3 sensors
- ✅ Robust data validation with Pydantic v2
- ✅ PII anonymization (email hashing, phone/address redaction)
- ✅ Star schema for optimized analytics queries
- ✅ Chunked processing for large files (>1GB)
- ✅ Invalid record quarantine system
- ✅ Email notifications for pipeline success/failure
- ✅ Comprehensive logging and error handling
- ✅ Idempotent upserts (INSERT ... ON CONFLICT)

## Project Structure

```
MINI_DATA_PLATFORM/
├── dags/
│   ├── src/
│   │   ├── ingestion/          # MinIO data retrieval
│   │   │   └── minio_client.py
│   │   ├── validation/         # Schema validation
│   │   │   └── validator.py
│   │   ├── transformation/     # Business logic & PII anonymization
│   │   │   └── transformer.py
│   │   ├── loading/            # PostgreSQL upsert operations
│   │   │   ├── postgres_loader.py
│   │   │   └── sql/
│   │   │       └── create_star_schema.sql
│   │   ├── utils/              # Shared utilities
│   │   │   ├── helpers.py
│   │   │   ├── schemas.py
│   │   │   └── notifications.py
│   │   └── pipeline.py         # Main ETL orchestrator
│   └── process_sales_data_dag.py  # Airflow DAG definition
├── tests/                      # Unit and integration tests
├── logs/                       # Module-specific log files
├── src/data_generator.py       # Mock data generator
├── Docker-compose.yml          # Service definitions
└── pyproject.toml              # Python dependencies and tooling

```

## Prerequisites

- Docker and Docker Compose
- Python 3.12+
- UV package manager
- Git

## Setup Instructions

### 1. Install UV Package Manager

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone Repository and Setup Environment

```bash
cd MINI_DATA_PLATFORM
uv sync  # Create virtual environment and install dependencies
```

### 3. Configure Environment Variables

Ensure `.env` file contains:

```bash
# Vault
VAULT_DEV_ROOT_TOKEN_ID=<your_token>

# MinIO
MINIO_ROOT_USER=shadow
MINIO_ROOT_PASSWORD=shadow123
MINIO_ENDPOINT=minio:9000
MINIO_SECURE=False

# PostgreSQL
POSTGRES_ANALYTICS_DB=shadowpostgresdb

# Airflow
AIRFLOW_DB_NAME=shadowdb
AIRFLOW_DB_USER=shadow
AIRFLOW_DB_PASSWORD=shadow123
AIRFLOW_FERNET_KEY=<generated_key>
AIRFLOW_SECRET_KEY=<generated_key>
```

### 4. Generate TLS Certificates

```bash
./generate-certs.sh
```

This creates certificates for:
- MinIO server
- PostgreSQL connections
- Airflow webserver
- KES (Key Encryption Service)

### 5. Initialize Vault with Secrets

Start Vault service:

```bash
docker-compose up -d vault
```

Store secrets in Vault:

```bash
# Enable KV secrets engine
docker exec -e VAULT_ADDR='http://127.0.0.1:8200' \
  -e VAULT_TOKEN='your_vault_token' \
  vault secrets enable -path=kv kv-v2

# Store MinIO credentials
docker exec -e VAULT_ADDR='http://127.0.0.1:8200' \
  -e VAULT_TOKEN='your_vault_token' \
  vault kv put kv/minio \
    access_key=shadow \
    secret_key=shadow123

# Store PostgreSQL credentials
docker exec -e VAULT_ADDR='http://127.0.0.1:8200' \
  -e VAULT_TOKEN='your_vault_token' \
  vault kv put kv/postgres_analytics \
    user=initial_user \
    password=initial_password \
    host=postgres-analytics \
    port=5432 \
    dbname=shadowpostgresdb
```

### 6. Create Database Schema

```bash
# Start PostgreSQL service
docker-compose up -d postgres-analytics

# Run schema creation script
docker exec -i postgres-analytics psql -U initial_user -d shadowpostgresdb \
  < dags/src/loading/sql/create_star_schema.sql
```

### 7. Configure Airflow Connections

Start Airflow services:

```bash
docker-compose up -d airflow-webserver airflow-scheduler
```

Access Airflow UI at `http://localhost:8080` (admin/admin) and create:

**MinIO Connection (ID: `minio_conn`)**:
- Connection Type: Amazon S3
- Extra:
  ```json
  {
    "aws_access_key_id": "shadow",
    "aws_secret_access_key": "shadow123",
    "endpoint_url": "http://minio:9000"
  }
  ```

**SMTP Connection (ID: `smtp_default`)**:
- Connection Type: SMTP
- Host: your_smtp_host
- Port: 587
- Login: your_email
- Password: your_password

### 8. Start All Services

```bash
docker-compose up -d
```

Services will be available at:
- Airflow UI: `http://localhost:8080`
- MinIO Console: `http://localhost:9001`
- Metabase: `http://localhost:3000`
- Vault UI: `http://localhost:8200`

### 9. Run Data Generator (Optional)

```bash
uv run python src/data_generator.py
```

This generates mock sales data and uploads to MinIO's `raw/` prefix every 5 seconds.

## Running the ETL Pipeline

### Manual Trigger

1. Access Airflow UI at `http://localhost:8080`
2. Enable the `process_sales_data` DAG
3. Trigger manually or wait for scheduled run (2 AM daily)

### Pipeline Workflow

1. **Sense**: S3KeySensor polls MinIO `raw/` prefix for new CSV files
2. **Ingest**: Download file from MinIO (chunked if >1GB)
3. **Validate**: Check against Pydantic schema
4. **Quarantine**: Move invalid records to `quarantine/` prefix
5. **Transform**: Anonymize PII, calculate profit, normalize data
6. **Load**: Upsert into PostgreSQL star schema (dimensions → fact)
7. **Archive**: Move processed file to `processed/` prefix

## Database Schema

### Star Schema Design

**Dimension Tables**:
- `dim_customer`: Customer data with anonymized PII
- `dim_product`: Product catalog with ratings and categories
- `dim_date`: Time dimension for temporal analysis

**Fact Table**:
- `fact_sales`: Sales transactions with foreign keys to dimensions

### Example Queries

```sql
-- Total sales by category
SELECT
    p.product_category,
    SUM(f.discounted_price * f.quantity) as total_sales
FROM fact_sales f
JOIN dim_product p ON f.product_id = p.product_id
GROUP BY p.product_category;

-- Monthly revenue trend
SELECT
    d.year,
    d.month,
    SUM(f.profit) as monthly_profit
FROM fact_sales f
JOIN dim_date d ON f.order_date_id = d.date_id
GROUP BY d.year, d.month
ORDER BY d.year, d.month;
```

## Metabase Setup

1. Access Metabase at `http://localhost:3000`
2. Complete initial setup wizard
3. Add PostgreSQL database:
   - Host: `postgres-analytics`
   - Port: `5432`
   - Database: `shadowpostgresdb`
   - Username: `metabase_reader`
   - Password: `metabase_read_secret`
   - Use SSL: Yes

4. Create dashboards:
   - Sales trends over time
   - Product performance by category
   - Customer purchase patterns
   - Top-selling products

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=dags/src --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_validation.py -v
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Check linting
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Type checking
uv run mypy dags/src/
```

### Adding Dependencies

```bash
# Add runtime dependency
uv add package-name

# Add dev dependency
uv add --dev package-name

# Remove dependency
uv remove package-name
```

## Troubleshooting

### Common Issues

**Issue**: Vault authentication fails
- **Solution**: Verify `VAULT_DEV_ROOT_TOKEN_ID` in `.env` matches token used in Vault

**Issue**: MinIO connection refused
- **Solution**: Ensure MinIO service is running: `docker-compose ps minio`

**Issue**: PostgreSQL SSL error
- **Solution**: Verify certificates generated: `ls -la certs/postgres/`

**Issue**: Airflow DAG not appearing
- **Solution**: Check logs: `docker-compose logs airflow-scheduler`

### Logs Location

- Application logs: `logs/` directory
- Airflow logs: `logs/airflow/`
- Docker logs: `docker-compose logs <service_name>`

## Security Considerations

- ✅ All secrets stored in Vault (never in code)
- ✅ TLS encryption for all network connections
- ✅ MinIO data encrypted at rest via KES
- ✅ PostgreSQL requires SSL connections
- ✅ PII data anonymized before storage
- ✅ Read-only database role for Metabase

## Monitoring & Maintenance

### Health Checks

```bash
# Check all services
docker-compose ps

# View service logs
docker-compose logs -f <service_name>

# Restart failing service
docker-compose restart <service_name>
```

### Backup Strategy

```bash
# Backup PostgreSQL
docker exec postgres-analytics pg_dump -U initial_user shadowpostgresdb > backup.sql

# Backup MinIO data
docker exec minio mc mirror /data /backup-location
```

## Contributing

1. Create feature branch: `git checkout -b feature/new-feature`
2. Make changes and add tests
3. Run quality checks: `uv run ruff check . && uv run pytest`
4. Commit: `git commit -m "feat(scope): description"`
5. Push and create PR

## License

Proprietary - All Rights Reserved

## Support

For issues or questions, contact: admin@example.com
