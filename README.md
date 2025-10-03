# Mini Data Platform

A secure, scalable ETL pipeline for processing sales data from MinIO object storage into a PostgreSQL analytics database, orchestrated with Apache Airflow.

## Quick Links

### Getting Started
- **[Architecture Overview](docs/overview.md)** - System design and data flow
- **[Setup Guide](docs/setup.md)** - Step-by-step installation
- **[Security Architecture](docs/security.md)** - Encryption and secrets management

### Development
- **[Development Guide](docs/development.md)** - Development workflow and coding standards
- **[Testing Guide](docs/testing.md)** - Unit, integration, and E2E testing
- **[API Reference](docs/api-reference.md)** - Function documentation

### Operations
- **[Deployment Guide](docs/deployment.md)** - Production deployment
- **[Metabase Guide](docs/metabase.md)** - Dashboard creation
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions

## Features

- **Event-Driven Architecture** - Airflow S3 sensors for MinIO polling
- **Robust Data Validation** - Pydantic v2 schema validation
- **PII Anonymization** - Email hashing, phone/address redaction
- **Star Schema** - Optimized for analytics queries
- **Chunked Processing** - Handles large files (>1GB)
- **Invalid Record Quarantine** - Separate invalid data
- **Email Notifications** - Success/failure alerts
- **Comprehensive Logging** - Module-specific log files
- **Idempotent Upserts** - INSERT ... ON CONFLICT

## Security

- **Encryption in Transit** - TLS 1.2+ for all services
- **Encryption at Rest** - Fernet (Airflow), KES (MinIO), OS-level (PostgreSQL)
- **Secrets Management** - HashiCorp Vault KV v2
- **Certificate Verification** - sslmode=verify-full for PostgreSQL
- **Non-Root Containers** - All services run as non-root
- **PII Protection** - Email hashing, phone/address redaction

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- UV package manager
- 4GB RAM (8GB recommended)
- 20GB disk space

### Installation

```bash
# 1. Clone repository
git clone https://github.com/your-org/mini-data-platform.git
cd mini-data-platform

# 2. Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Setup Python environment
uv venv && source .venv/bin/activate
uv sync

# 4. Generate Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 5. Configure environment (.env file)
cp .env.example .env
# Edit .env with your Fernet key and credentials

# 6. Generate certificates
./generate-certs.sh

# 7. Start services
docker-compose up -d

# 8. Initialize Vault
docker-compose exec vault vault secrets enable -path=kv kv-v2
./scripts/init-vault-secrets.sh

# 9. Create database schema
docker exec -i postgres-analytics psql -U user -d db \
  < dags/src/loading/sql/create_star_schema.sql
```

### Verify Installation

```bash
# Check all services running
docker-compose ps

# Access UIs
open http://localhost:8080  # Airflow (admin/admin)
open http://localhost:9001  # MinIO (shadow/shadow123)
open http://localhost:3000  # Metabase
```

## Project Structure

```
MINI_DATA_PLATFORM/
├── dags/                       # Airflow DAGs and ETL logic
│   ├── src/
│   │   ├── ingestion/          # MinIO data retrieval
│   │   ├── validation/         # Schema validation
│   │   ├── transformation/     # Business logic & PII
│   │   ├── loading/            # PostgreSQL upserts
│   │   ├── utils/              # Shared utilities
│   │   └── pipeline.py         # Main ETL orchestrator
│   └── process_sales_data_dag.py
├── docs/                       # Comprehensive documentation
│   ├── overview.md
│   ├── setup.md
│   ├── security.md
│   ├── development.md
│   ├── testing.md
│   ├── api-reference.md
│   ├── deployment.md
│   ├── troubleshooting.md
│   └── metabase.md
├── tests/                      # Unit, integration, E2E tests
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/                    # Infrastructure scripts
├── src/                        # Data generator
├── Docker-compose.yml          # Service orchestration
├── Dockerfile                  # Data generator image
├── generate-certs.sh           # TLS certificate generation
└── pyproject.toml              # Python dependencies

```

## Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12 | ETL logic |
| Apache Airflow | 2.8.1 | Orchestration |
| PostgreSQL | 13 | Data warehouse |
| MinIO | Latest | Object storage (S3-compatible) |
| HashiCorp Vault | Latest | Secrets management |
| Metabase | Latest | Data visualization |
| Docker | Latest | Containerization |

## Development

### Run Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=dags/src --cov-report=html

# Specific test file
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
```

## ETL Pipeline

### Workflow

```
1. S3KeySensor polls MinIO raw/ prefix
2. New CSV file detected → Download
3. Validate against Pydantic schema
4. Invalid records → Quarantine
5. Valid records → Transform (PII anonymization)
6. Upsert to PostgreSQL star schema
7. Move file to processed/ prefix
8. Send email notification
```

### Star Schema

**Dimension Tables:**
- `dim_customer` - Customer data (PII anonymized)
- `dim_product` - Product catalog
- `dim_date` - Time dimension

**Fact Table:**
- `fact_sales` - Sales transactions

## Service Access

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Airflow | http://localhost:8080 | admin / admin |
| MinIO Console | http://localhost:9001 | shadow / shadow123 |
| Metabase | http://localhost:3000 | Setup on first visit |
| Vault UI | http://localhost:8200/ui | Token: dev-root-token-12345 |

## Contributing

1. Create feature branch: `git checkout -b feature/new-feature`
2. Make changes and add tests
3. Run quality checks: `uv run ruff check . && uv run pytest`
4. Commit: `git commit -m "feat(scope): description"`
5. Push and create PR

See [Development Guide](docs/development.md) for details.

## License

Proprietary - All Rights Reserved

## Support

For issues or questions:
- GitHub Issues: https://github.com/your-org/mini-data-platform/issues
- Email: admin@example.com
- Documentation: [docs/](docs/)

## Acknowledgments

Built with:
- Apache Airflow
- PostgreSQL
- MinIO
- HashiCorp Vault
- Metabase
- Docker
