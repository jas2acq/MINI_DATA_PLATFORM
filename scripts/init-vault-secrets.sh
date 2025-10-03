#!/bin/bash
# Initialize HashiCorp Vault with all platform secrets
# This script should be run ONCE during initial platform setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔐 Initializing Vault with Platform Secrets${NC}"
echo "================================================"

# Check if Vault is accessible
if ! vault status &>/dev/null; then
    echo -e "${RED}❌ Error: Cannot connect to Vault${NC}"
    echo "Please ensure Vault is running and VAULT_ADDR and VAULT_TOKEN are set"
    exit 1
fi

# Check if KV secrets engine is enabled
if ! vault secrets list | grep -q "kv/"; then
    echo -e "${YELLOW}⚙️  Enabling KV secrets engine v2...${NC}"
    vault secrets enable -path=kv kv-v2
fi

echo ""
echo -e "${GREEN}📝 Storing MinIO Credentials${NC}"
vault kv put kv/minio \
    root_user="shadow" \
    root_password="shadow123" \
    access_key="shadow" \
    secret_key="shadow123" \
    endpoint="minio:9000" \
    secure="true"

echo -e "${GREEN}✓ MinIO credentials stored${NC}"

echo ""
echo -e "${GREEN}📝 Storing PostgreSQL Airflow DB Credentials${NC}"
# Generate strong random password
AIRFLOW_DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
vault kv put kv/postgres_airflow \
    user="shadow_airflow" \
    password="$AIRFLOW_DB_PASSWORD" \
    host="postgres-airflow" \
    port="5432" \
    dbname="shadowdb"

echo -e "${GREEN}✓ PostgreSQL Airflow credentials stored${NC}"

echo ""
echo -e "${GREEN}📝 Storing PostgreSQL Analytics DB Initial Credentials${NC}"
# Generate strong random password
ANALYTICS_DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
vault kv put kv/postgres_analytics_init \
    user="analytics_admin" \
    password="$ANALYTICS_DB_PASSWORD" \
    host="postgres-analytics" \
    port="5432" \
    dbname="shadowpostgresdb"

echo -e "${GREEN}✓ PostgreSQL Analytics initial credentials stored${NC}"

echo ""
echo -e "${GREEN}📝 Storing Metabase Database Credentials${NC}"
# Generate strong random password for Metabase
METABASE_DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
vault kv put kv/metabase \
    db_user="metabase_reader" \
    db_password="$METABASE_DB_PASSWORD" \
    db_host="postgres-analytics" \
    db_port="5432" \
    db_name="shadowpostgresdb"

echo -e "${GREEN}✓ Metabase credentials stored${NC}"

echo ""
echo -e "${GREEN}📝 Storing Airflow Application Secrets${NC}"
# Generate Fernet key for Airflow
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
SECRET_KEY=$(openssl rand -hex 32)
WEBSERVER_SECRET_KEY=$(openssl rand -hex 32)

vault kv put kv/airflow \
    fernet_key="$FERNET_KEY" \
    secret_key="$SECRET_KEY" \
    webserver_secret_key="$WEBSERVER_SECRET_KEY"

echo -e "${GREEN}✓ Airflow application secrets stored${NC}"

echo ""
echo -e "${GREEN}📝 Storing ETL Pipeline Configuration${NC}"
vault kv put kv/etl_config \
    vault_addr="http://vault:8200" \
    log_level="INFO" \
    chunk_size="10000" \
    batch_size="1000"

echo -e "${GREEN}✓ ETL configuration stored${NC}"

echo ""
echo "================================================"
echo -e "${GREEN}✅ All secrets successfully stored in Vault${NC}"
echo ""
echo -e "${YELLOW}📋 Summary of stored secrets:${NC}"
echo "  • kv/minio - MinIO storage credentials"
echo "  • kv/postgres_airflow - Airflow database credentials"
echo "  • kv/postgres_analytics_init - Analytics DB initial credentials"
echo "  • kv/metabase - Metabase application credentials"
echo "  • kv/airflow - Airflow application secrets"
echo "  • kv/etl_config - ETL pipeline configuration"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Update your .env file to remove all hardcoded secrets${NC}"
echo -e "${YELLOW}⚠️  These secrets are now managed by Vault and will be retrieved at runtime${NC}"
echo ""
