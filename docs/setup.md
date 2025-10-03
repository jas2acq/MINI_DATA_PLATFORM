# Setup Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation Steps](#installation-steps)
  - [1. Clone Repository](#1-clone-repository)
  - [2. Install UV Package Manager](#2-install-uv-package-manager)
  - [3. Setup Python Environment](#3-setup-python-environment)
  - [4. Generate Fernet Key](#4-generate-fernet-key)
  - [5. Configure Environment Variables](#5-configure-environment-variables)
  - [6. Generate TLS Certificates](#6-generate-tls-certificates)
  - [7. Initialize HashiCorp Vault](#7-initialize-hashicorp-vault)
  - [8. Create Database Schema](#8-create-database-schema)
  - [9. Configure Airflow Connections](#9-configure-airflow-connections)
  - [10. Start All Services](#10-start-all-services)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before starting, ensure you have the following installed:

- **Docker** (v20.10+) and **Docker Compose** (v2.0+)
- **Git** (v2.30+)
- **Python** 3.12+
- **curl** or **wget** for downloading UV
- **OpenSSL** for certificate generation
- **4GB RAM** minimum (8GB recommended)
- **20GB disk space** minimum

### Platform Support

- Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+)
- macOS (11.0+)
- Windows (via WSL2)

## Installation Steps

### 1. Clone Repository

```bash
git clone https://github.com/your-org/mini-data-platform.git
cd mini-data-platform
```

### 2. Install UV Package Manager

UV is a fast Python package manager that replaces pip and virtualenv.

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Verify installation:**
```bash
uv --version
# Should output: uv 0.x.x
```

### 3. Setup Python Environment

Create virtual environment and install dependencies:

```bash
# Create and activate virtual environment
uv venv

# Activate virtual environment
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Sync dependencies (installs from pyproject.toml and uv.lock)
uv sync
```

**Verify Python packages:**
```bash
uv run python -c "import pydantic, pandas, hvac, minio, psycopg2; print('All packages installed')"
```

### 4. Generate Fernet Key

Airflow requires a Fernet key to encrypt connections, variables, and passwords in the metadata database.

**Generate Fernet Key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Example output:**
```
X5z9mK2nQ7wP4dR8aF3jL6tY1vB5cH9eN2sG8pU0xM4=
```

**Save this key** - you'll need it in the next step.

### 5. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

**Edit `.env` file with your values:**

```bash
# ============================================
# VAULT CONFIGURATION
# ============================================
VAULT_DEV_ROOT_TOKEN_ID=dev-root-token-12345

# ============================================
# AIRFLOW CONFIGURATION
# ============================================
# Use the Fernet key generated in step 4
AIRFLOW__CORE__FERNET_KEY=X5z9mK2nQ7wP4dR8aF3jL6tY1vB5cH9eN2sG8pU0xM4=

# Secret key for Flask app (generate with: openssl rand -hex 32)
AIRFLOW_SECRET_KEY=your_generated_secret_key_here

# Airflow database (PostgreSQL)
AIRFLOW_DB_NAME=shadowdb
AIRFLOW_DB_USER=shadow
AIRFLOW_DB_PASSWORD=shadow123

# Airflow UID (for file permissions in Docker)
AIRFLOW_UID=50000

# ============================================
# MINIO CONFIGURATION
# ============================================
MINIO_ROOT_USER=shadow
MINIO_ROOT_PASSWORD=shadow123
MINIO_ENDPOINT=minio:9000
MINIO_SECURE=True

# ============================================
# POSTGRESQL ANALYTICS DATABASE
# ============================================
POSTGRES_ANALYTICS_DB=shadowpostgresdb
POSTGRES_ANALYTICS_USER=initial_user
POSTGRES_ANALYTICS_PASSWORD=initial_password

# ============================================
# METABASE CONFIGURATION
# ============================================
MB_DB_TYPE=postgres
MB_DB_DBNAME=shadowpostgresdb
MB_DB_PORT=5432
MB_DB_USER=metabase_reader
MB_DB_PASS=metabase_read_secret
```

**Security Notes:**
- Change all default passwords before production use
- Never commit the `.env` file to version control
- Use strong, randomly generated passwords
- Rotate credentials regularly

### 6. Generate TLS Certificates

Generate self-signed certificates for all services:

```bash
chmod +x generate-certs.sh
./generate-certs.sh
```

**This script creates certificates for:**
- MinIO server (`certs/minio/`)
- PostgreSQL Analytics (`certs/postgres/`)
- PostgreSQL Airflow (`certs/postgres-airflow/`)
- Airflow Web Server (`certs/airflow/`)
- KES Server (`certs/kes/`)
- CA certificate (`certs/ca.crt`)

**Verify certificates:**
```bash
ls -R certs/
# Should show .crt and .key files for each service
```

**Certificate Details:**
- **Validity**: 365 days
- **Algorithm**: RSA 2048-bit
- **Type**: Self-signed (for development)

**Production Recommendation:**
Use CA-issued certificates from Let's Encrypt or your organization's PKI.

### 7. Initialize HashiCorp Vault

Start Vault service and populate with secrets:

#### Step 7.1: Start Vault

```bash
docker-compose up -d vault
```

**Wait for Vault to be ready:**
```bash
docker-compose logs -f vault
# Wait for: "Development mode. DO NOT run in production!"
```

#### Step 7.2: Enable KV Secrets Engine

```bash
docker exec -e VAULT_ADDR='http://127.0.0.1:8200' \
  -e VAULT_TOKEN='dev-root-token-12345' \
  vault secrets enable -path=kv kv-v2
```

**Expected output:**
```
Success! Enabled the kv-v2 secrets engine at: kv/
```

#### Step 7.3: Store MinIO Credentials

```bash
docker exec -e VAULT_ADDR='http://127.0.0.1:8200' \
  -e VAULT_TOKEN='dev-root-token-12345' \
  vault kv put kv/minio \
    access_key=shadow \
    secret_key=shadow123
```

**Verify:**
```bash
docker exec -e VAULT_ADDR='http://127.0.0.1:8200' \
  -e VAULT_TOKEN='dev-root-token-12345' \
  vault kv get kv/minio
```

#### Step 7.4: Store PostgreSQL Analytics Credentials

```bash
docker exec -e VAULT_ADDR='http://127.0.0.1:8200' \
  -e VAULT_TOKEN='dev-root-token-12345' \
  vault kv put kv/postgres_analytics \
    user=initial_user \
    password=initial_password \
    host=postgres-analytics \
    port=5432 \
    dbname=shadowpostgresdb
```

**Verify:**
```bash
docker exec -e VAULT_ADDR='http://127.0.0.1:8200' \
  -e VAULT_TOKEN='dev-root-token-12345' \
  vault kv get kv/postgres_analytics
```

### 8. Create Database Schema

#### Step 8.1: Start PostgreSQL

```bash
docker-compose up -d postgres-analytics
```

**Wait for PostgreSQL to be ready:**
```bash
docker-compose logs -f postgres-analytics
# Wait for: "database system is ready to accept connections"
```

#### Step 8.2: Create Star Schema

```bash
docker exec -i postgres-analytics psql \
  -U initial_user \
  -d shadowpostgresdb \
  < dags/src/loading/sql/create_star_schema.sql
```

**Expected output:**
```
CREATE TABLE
CREATE INDEX
CREATE TABLE
...
```

#### Step 8.3: Verify Schema

```bash
docker exec -it postgres-analytics psql \
  -U initial_user \
  -d shadowpostgresdb \
  -c "\dt"
```

**Expected tables:**
- `dim_customer`
- `dim_product`
- `dim_date`
- `fact_sales`

### 9. Configure Airflow Connections

#### Step 9.1: Start Airflow Services

```bash
docker-compose up -d airflow-init
docker-compose up -d airflow-webserver airflow-scheduler
```

**Wait for webserver to start:**
```bash
docker-compose logs -f airflow-webserver
# Wait for: "Listening at: http://0.0.0.0:8080"
```

#### Step 9.2: Access Airflow UI

Open browser: `http://localhost:8080`

**Default credentials:**
- Username: `admin`
- Password: `admin`

#### Step 9.3: Create MinIO Connection

**Via Airflow UI:**
1. Navigate to **Admin → Connections**
2. Click **+** to add new connection
3. Fill in:
   - **Connection ID**: `minio_conn`
   - **Connection Type**: `Amazon S3`
   - **Extra**:
     ```json
     {
       "aws_access_key_id": "shadow",
       "aws_secret_access_key": "shadow123",
       "endpoint_url": "http://minio:9000"
     }
     ```
4. Click **Save**

**Via CLI:**
```bash
docker exec airflow-webserver airflow connections add 'minio_conn' \
  --conn-type 'aws' \
  --conn-extra '{"aws_access_key_id":"shadow","aws_secret_access_key":"shadow123","endpoint_url":"http://minio:9000"}'
```

#### Step 9.4: Create SMTP Connection (Optional)

For email notifications:

1. Navigate to **Admin → Connections**
2. Click **+** to add new connection
3. Fill in:
   - **Connection ID**: `smtp_default`
   - **Connection Type**: `SMTP`
   - **Host**: `smtp.gmail.com` (or your SMTP server)
   - **Port**: `587`
   - **Login**: `your-email@gmail.com`
   - **Password**: `your-app-password`
4. Click **Save**

**Gmail Setup:**
1. Enable 2-factor authentication
2. Generate app-specific password
3. Use app password in connection

### 10. Start All Services

Start all remaining services:

```bash
docker-compose up -d
```

**Verify all services running:**
```bash
docker-compose ps
```

**Expected output:**
All services should show `Up` status:
- `vault`
- `kes`
- `minio`
- `postgres-airflow`
- `postgres-analytics`
- `airflow-webserver`
- `airflow-scheduler`
- `metabase`

## Verification

### Health Checks

**1. Vault:**
```bash
curl http://localhost:8200/v1/sys/health
```
Expected: `{"initialized":true,"sealed":false}`

**2. MinIO:**
```bash
curl http://localhost:9000/minio/health/live
```
Expected: 200 OK

**3. PostgreSQL Analytics:**
```bash
docker exec postgres-analytics pg_isready -U initial_user
```
Expected: `accepting connections`

**4. Airflow Web Server:**
```bash
curl http://localhost:8080/health
```
Expected: `{"metadatabase":{"status":"healthy"}}`

**5. Metabase:**
```bash
curl http://localhost:3000/api/health
```
Expected: `{"status":"ok"}`

### Service Access

| Service | URL | Credentials |
|---------|-----|-------------|
| **Airflow** | http://localhost:8080 | admin / admin |
| **MinIO Console** | http://localhost:9001 | shadow / shadow123 |
| **Metabase** | http://localhost:3000 | Set on first visit |
| **Vault UI** | http://localhost:8200/ui | Token: dev-root-token-12345 |

### Test Data Generation

Run the data generator to create sample CSV files:

```bash
uv run python src/data_generator.py
```

**Expected behavior:**
- Generates CSV every 5 seconds
- Uploads to MinIO `data-platform` bucket, `raw/` prefix
- Logs: `Batch X uploaded to MinIO: raw/batch_X_TIMESTAMP.csv`

**Verify in MinIO Console:**
1. Open http://localhost:9001
2. Login: shadow / shadow123
3. Navigate to `data-platform` bucket
4. Check `raw/` prefix for CSV files

### Test ETL Pipeline

**1. Enable DAG in Airflow:**
1. Open http://localhost:8080
2. Find `process_sales_data` DAG
3. Toggle switch to **ON**

**2. Manually trigger DAG:**
1. Click on DAG name
2. Click **Trigger DAG** button (play icon)

**3. Monitor execution:**
1. Click on running DAG run
2. View task logs for each step:
   - `sense_new_file`
   - `process_file`

**4. Verify data in PostgreSQL:**
```bash
docker exec -it postgres-analytics psql -U initial_user -d shadowpostgresdb
```

```sql
-- Check row counts
SELECT COUNT(*) FROM dim_customer;
SELECT COUNT(*) FROM dim_product;
SELECT COUNT(*) FROM dim_date;
SELECT COUNT(*) FROM fact_sales;

-- View sample data
SELECT * FROM fact_sales LIMIT 5;
```

## Troubleshooting

### Common Issues

#### Issue: Vault authentication fails

**Symptoms:**
```
Error: permission denied
```

**Solution:**
1. Verify `VAULT_DEV_ROOT_TOKEN_ID` in `.env` matches Vault token
2. Restart Vault:
   ```bash
   docker-compose restart vault
   ```

#### Issue: MinIO connection refused

**Symptoms:**
```
urllib3.exceptions.MaxRetryError: Max retries exceeded
```

**Solution:**
1. Check MinIO is running:
   ```bash
   docker-compose ps minio
   ```
2. Verify network connectivity:
   ```bash
   docker exec airflow-webserver ping -c 3 minio
   ```

#### Issue: PostgreSQL SSL error

**Symptoms:**
```
psycopg2.OperationalError: SSL error: certificate verify failed
```

**Solution:**
1. Verify certificates exist:
   ```bash
   ls -la certs/postgres/
   ```
2. Regenerate certificates:
   ```bash
   ./generate-certs.sh
   docker-compose restart postgres-analytics
   ```

#### Issue: Airflow DAG not appearing

**Symptoms:**
DAG not visible in Airflow UI

**Solution:**
1. Check scheduler logs:
   ```bash
   docker-compose logs airflow-scheduler
   ```
2. Verify DAG file syntax:
   ```bash
   uv run python dags/process_sales_data_dag.py
   ```
3. Restart scheduler:
   ```bash
   docker-compose restart airflow-scheduler
   ```

#### Issue: Permission denied in Docker volumes

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied
```

**Solution:**
1. Fix ownership of volumes:
   ```bash
   sudo chown -R $(id -u):$(id -g) logs/ dags/
   ```
2. Set proper AIRFLOW_UID:
   ```bash
   echo "AIRFLOW_UID=$(id -u)" >> .env
   docker-compose down
   docker-compose up -d
   ```

### Reset Everything

If you need to start fresh:

```bash
# Stop all services
docker-compose down -v

# Remove generated data
rm -rf logs/* data/* certs/

# Regenerate certificates
./generate-certs.sh

# Restart from step 7
docker-compose up -d vault
# ... continue setup
```

## Next Steps

- [Architecture Overview](overview.md) - Understand the system design
- [Security Architecture](security.md) - Learn about encryption and secrets
- [Development Guide](development.md) - Start contributing
- [Metabase Guide](metabase.md) - Create dashboards
