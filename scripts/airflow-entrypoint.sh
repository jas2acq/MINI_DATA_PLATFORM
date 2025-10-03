#!/bin/bash
# Airflow Entrypoint with Vault Integration
# Fetches secrets from Vault before starting Airflow services

set -e

echo "🔐 Fetching Airflow secrets from Vault..."

# Install curl if not available
if ! command -v curl &> /dev/null; then
    echo "Installing curl..."
    apt-get update -qq > /dev/null 2>&1
    apt-get install -y curl -qq > /dev/null 2>&1
fi

# Ensure Vault environment is set
export VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
export VAULT_TOKEN="${VAULT_TOKEN:-$(cat /vault/token 2>/dev/null)}"

if [ -z "$VAULT_TOKEN" ]; then
    echo "❌ Error: VAULT_TOKEN not set"
    exit 1
fi

# Wait for Vault to be ready
echo "Waiting for Vault to be ready..."
for i in {1..30}; do
    if curl -s -f "${VAULT_ADDR}/v1/sys/health" > /dev/null 2>&1; then
        echo "✅ Vault is ready"
        break
    fi
    echo "Waiting for Vault... ($i/30)"
    sleep 2
done

# Fetch Airflow application secrets using curl
echo "Fetching Airflow application secrets..."
AIRFLOW_RESPONSE=$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/kv/data/airflow")
FERNET_KEY=$(echo "$AIRFLOW_RESPONSE" | grep -o '"fernet_key":"[^"]*"' | cut -d'"' -f4)
SECRET_KEY=$(echo "$AIRFLOW_RESPONSE" | grep -o '"secret_key":"[^"]*"' | cut -d'"' -f4)
WEBSERVER_SECRET_KEY=$(echo "$AIRFLOW_RESPONSE" | grep -o '"webserver_secret_key":"[^"]*"' | cut -d'"' -f4)

# Fetch PostgreSQL Airflow DB credentials using curl
echo "Fetching Airflow database credentials..."
DB_RESPONSE=$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/kv/data/postgres_airflow")
DB_USER=$(echo "$DB_RESPONSE" | grep -o '"user":"[^"]*"' | cut -d'"' -f4)
DB_PASS=$(echo "$DB_RESPONSE" | grep -o '"password":"[^"]*"' | cut -d'"' -f4)
DB_HOST=$(echo "$DB_RESPONSE" | grep -o '"host":"[^"]*"' | cut -d'"' -f4)
DB_PORT=$(echo "$DB_RESPONSE" | grep -o '"port":"[^"]*"' | cut -d'"' -f4)
DB_NAME=$(echo "$DB_RESPONSE" | grep -o '"dbname":"[^"]*"' | cut -d'"' -f4)

# Export Airflow configuration
export AIRFLOW__CORE__FERNET_KEY="$FERNET_KEY"
export AIRFLOW__WEBSERVER__SECRET_KEY="$WEBSERVER_SECRET_KEY"
export AIRFLOW__CORE__SQL_ALCHEMY_CONN="postgresql+psycopg2://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=require"
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=require"

echo "✅ Secrets loaded successfully"
echo "Starting Airflow: $@"

# Execute the original Airflow command
exec airflow "$@"
