# Architecture Overview

## Table of Contents
- [System Architecture](#system-architecture)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)
- [Security Model](#security-model)
- [Star Schema Design](#star-schema-design)

## System Architecture

The Mini Data Platform is a secure, scalable ETL pipeline designed to process sales data from MinIO object storage into a PostgreSQL analytics database, orchestrated with Apache Airflow.

### High-Level Components

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│  Data       │─────▶│   MinIO      │─────▶│   Airflow       │
│  Generator  │      │   (S3)       │      │   DAG           │
└─────────────┘      │              │      │                 │
                     │  ┌────────┐  │      │  ┌───────────┐  │
                     │  │  raw/  │  │      │  │  Sensor   │  │
                     │  ├────────┤  │      │  ├───────────┤  │
                     │  │process/│  │      │  │  ETL      │  │
                     │  ├────────┤  │      │  └───────────┘  │
                     │  │quarant/│  │      └─────────────────┘
                     └──┴────────┴──┘               │
                                                    │
                     ┌──────────────┐               │
                     │  HashiCorp   │◀──────────────┘
                     │  Vault       │  (Secrets)
                     └──────────────┘
                            │
           ┌────────────────┼────────────────┐
           ▼                ▼                ▼
    ┌──────────┐     ┌──────────┐    ┌──────────┐
    │PostgreSQL│     │PostgreSQL│    │   KES    │
    │ Airflow  │     │Analytics │    │(Encrypt) │
    └──────────┘     └──────────┘    └──────────┘
                            │                │
                            │                ▼
                            │         ┌──────────┐
                            │         │  MinIO   │
                            │         │ (Encrypt)│
                            │         └──────────┘
                            ▼
                     ┌──────────────┐
                     │   Metabase   │
                     │  (Visualize) │
                     └──────────────┘
```

### Component Responsibilities

#### 1. **Data Source - MinIO Object Storage**
- S3-compatible object storage
- Bucket: `data-platform`
- Prefixes:
  - `raw/`: Incoming CSV files
  - `processed/`: Successfully processed files
  - `quarantine/`: Invalid records

#### 2. **Orchestration - Apache Airflow**
- **Scheduler**: Runs DAG at 2 AM daily
- **S3KeySensor**: Polls MinIO for new files
- **PythonOperator**: Executes ETL pipeline
- **Email Notifications**: Success/failure callbacks

#### 3. **ETL Pipeline - Python Modules**
- **Ingestion** (`dags/src/ingestion/`): MinIO file retrieval with chunking
- **Validation** (`dags/src/validation/`): Pydantic schema validation
- **Transformation** (`dags/src/transformation/`): PII anonymization, profit calculation
- **Loading** (`dags/src/loading/`): PostgreSQL star schema upserts

#### 4. **Data Warehouse - PostgreSQL**
- **Star Schema**: Optimized for analytics queries
- **Idempotent Upserts**: INSERT ... ON CONFLICT
- **SSL Connections**: TLS encryption required

#### 5. **Secrets Management - HashiCorp Vault**
- **KV v2 Engine**: Versioned secret storage
- **Secret Paths**:
  - `kv/data/minio`: MinIO credentials
  - `kv/data/postgres_analytics`: Database credentials

#### 6. **Visualization - Metabase**
- **Dashboards**: Sales trends, product performance
- **Read-Only Access**: Dedicated database user
- **Charts**: Time-series, category analysis

#### 7. **Encryption - MinIO KES**
- **Server-Side Encryption**: Objects encrypted at rest
- **Vault Integration**: Keys managed in Vault Transit engine
- **TLS Required**: All KES communication encrypted

## Data Flow

### End-to-End Pipeline

```
1. DATA GENERATION
   └─▶ Data generator creates CSV
       └─▶ Uploads to MinIO raw/ prefix

2. EVENT DETECTION
   └─▶ Airflow S3KeySensor polls raw/
       └─▶ New file detected
           └─▶ File key pushed to XCom

3. INGESTION
   └─▶ Download CSV from MinIO
       ├─▶ Check file size
       ├─▶ If >1GB: Use chunked processing
       └─▶ If <1GB: Load full DataFrame

4. VALIDATION
   └─▶ Validate each row against Pydantic schema
       ├─▶ Valid records → Continue
       └─▶ Invalid records → Quarantine

5. QUARANTINE (if invalid data)
   └─▶ Save invalid DataFrame to MinIO quarantine/
       └─▶ Log validation errors

6. TRANSFORMATION
   └─▶ Anonymize PII (email hash, phone/address redaction)
   ├─▶ Calculate profit column
   ├─▶ Convert dates to datetime
   └─▶ Round monetary values

7. LOADING
   └─▶ Upsert to PostgreSQL star schema
       ├─▶ dim_customer
       ├─▶ dim_product
       ├─▶ dim_date
       └─▶ fact_sales

8. ARCHIVAL
   └─▶ Move file from raw/ to processed/
       └─▶ Log success

9. NOTIFICATION
   └─▶ Send email notification
       ├─▶ Success: Summary stats
       └─▶ Failure: Exception details
```

### File State Transitions

```
raw/batch_1.csv
    │
    ├─▶ [VALID DATA] ─────────▶ processed/batch_1.csv
    │
    └─▶ [INVALID DATA] ───────▶ quarantine/batch_1.csv
                                (copy of invalid rows only)
```

## Technology Stack

### Core Technologies (2025 Versions)

| Technology | Version | Purpose | Justification |
|------------|---------|---------|---------------|
| **Python** | 3.12 | ETL Logic | Latest stable, type hints, performance |
| **Apache Airflow** | 2.8.1 | Orchestration | Industry standard, mature ecosystem |
| **PostgreSQL** | 13 | Data Warehouse | ACID compliance, JSON support |
| **MinIO** | Latest | Object Storage | S3-compatible, self-hosted |
| **HashiCorp Vault** | Latest | Secrets Management | KV v2, versioning, audit logs |
| **Metabase** | Latest | Visualization | Open-source, user-friendly |
| **Docker** | Latest | Containerization | Consistent environments |

### Python Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| **pydantic** | v2 | Data validation with BaseModel |
| **pandas** | Latest | DataFrame operations |
| **hvac** | Latest | Vault client (KV v2 API) |
| **minio** | Latest | MinIO client (S3 operations) |
| **psycopg2** | Latest | PostgreSQL driver |
| **pytest** | Latest | Unit testing framework |
| **ruff** | Latest | Linting and formatting |
| **mypy** | Latest | Static type checking |

### Development Tools

- **UV**: Python package manager (faster than pip)
- **GitHub CLI** (`gh`): Repository management
- **Docker Compose**: Multi-container orchestration

## Security Model

### Encryption in Transit (TLS 1.2+)

All network communication is encrypted:

```
┌─────────────────────────────────────────────────┐
│  TLS ENCRYPTION IN TRANSIT                      │
├─────────────────────────────────────────────────┤
│  ✓ Airflow Web Server  → HTTPS (port 8080)     │
│  ✓ PostgreSQL          → SSL (sslmode=verify-full) │
│  ✓ MinIO               → HTTPS (port 9000/9001) │
│  ✓ Vault API           → HTTPS (port 8200)      │
│  ✓ KES                 → HTTPS (port 7373)      │
│  ✓ Metabase            → HTTPS (port 3000)      │
└─────────────────────────────────────────────────┘
```

### Encryption at Rest

Data is encrypted when stored:

```
┌─────────────────────────────────────────────────┐
│  ENCRYPTION AT REST                             │
├─────────────────────────────────────────────────┤
│  ✓ Airflow Metadata    → Fernet Key            │
│  ✓ MinIO Objects       → KES (Vault Transit)   │
│  ✓ PostgreSQL Data     → OS-level disk encrypt │
│  ✓ Vault Storage       → Encrypted backend     │
└─────────────────────────────────────────────────┘
```

### Secrets Management Flow

```
1. Service starts
   └─▶ Reads VAULT_TOKEN from environment
       └─▶ Connects to Vault API

2. Retrieve credentials
   └─▶ hvac.Client().secrets.kv.v2.read_secret_version(path='minio')
       └─▶ Returns: {access_key, secret_key}

3. Use credentials
   └─▶ Initialize MinIO client
       └─▶ Credentials never logged or stored

4. Credential rotation
   └─▶ Update secret in Vault
       └─▶ Services reconnect with new credentials
```

### PII Anonymization

```
┌──────────────────────────────────────────────────┐
│  PII FIELD          │  ANONYMIZATION METHOD      │
├─────────────────────┼────────────────────────────┤
│  customer_email     │  SHA-256 hash              │
│  customer_phone     │  Redacted (***-***-1234)   │
│  customer_address   │  Redacted (*** Street)     │
│  order_id           │  Preserved (business key)  │
│  product_title      │  Preserved (not PII)       │
└──────────────────────────────────────────────────┘
```

## Star Schema Design

### Dimensional Model

```
                    ┌─────────────────┐
                    │   dim_customer  │
                    ├─────────────────┤
                    │ customer_id (PK)│
                    │ name            │
                    │ email_hash      │
                    │ phone_redacted  │
                    │ address_redacted│
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            │                ▼                │
            │       ┌─────────────────┐       │
            │       │   fact_sales    │       │
            │       ├─────────────────┤       │
            │       │ sales_id (PK)   │       │
            │       │ order_id        │       │
            └──────▶│ customer_id (FK)│       │
                    │ product_id (FK) │◀──────┤
                    │ order_date_id(FK)│      │
                    │ delivery_date_id│       │
                    │ quantity        │       │
                    │ discounted_price│       │
                    │ original_price  │       │
                    │ profit          │       │
                    └────────┬────────┘       │
                             │                │
                    ┌────────┴────────┐       │
                    │                 │       │
           ┌────────▼──────┐   ┌──────▼────────┐
           │  dim_date     │   │  dim_product  │
           ├───────────────┤   ├───────────────┤
           │ date_id (PK)  │   │ product_id(PK)│
           │ date          │   │ title         │
           │ year          │   │ rating        │
           │ month         │   │ category      │
           │ day           │   │ is_best_seller│
           │ quarter       │   └───────────────┘
           │ day_of_week   │
           └───────────────┘
```

### Query Optimization

**Indexes:**
- Primary keys on all `*_id` columns
- Foreign keys indexed automatically
- Composite index on `dim_date(year, month, day)`

**Benefits:**
- Fast aggregations by time period
- Efficient joins via indexed foreign keys
- Denormalized for read performance
- Easy to understand for business users

### Example Analytics Queries

```sql
-- Monthly Revenue Trend
SELECT
    d.year,
    d.month,
    SUM(f.discounted_price * f.quantity) AS revenue,
    SUM(f.profit) AS profit
FROM fact_sales f
JOIN dim_date d ON f.order_date_id = d.date_id
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- Top Products by Category
SELECT
    p.product_category,
    p.product_title,
    SUM(f.quantity) AS total_sold,
    SUM(f.profit) AS total_profit
FROM fact_sales f
JOIN dim_product p ON f.product_id = p.product_id
GROUP BY p.product_category, p.product_title
ORDER BY total_profit DESC
LIMIT 10;

-- Customer Purchase Patterns
SELECT
    c.customer_id,
    COUNT(DISTINCT f.order_id) AS total_orders,
    SUM(f.quantity) AS total_items,
    AVG(f.profit) AS avg_profit_per_sale
FROM fact_sales f
JOIN dim_customer c ON f.customer_id = c.customer_id
GROUP BY c.customer_id
HAVING COUNT(DISTINCT f.order_id) > 5
ORDER BY total_orders DESC;
```

## Next Steps

- [Setup Guide](setup.md) - Install and configure the platform
- [Security Architecture](security.md) - Detailed security implementation
- [Development Guide](development.md) - Contribute to the project
