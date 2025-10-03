#!/bin/bash
# Airflow Webserver Entrypoint with Vault Integration
# Fetches credentials from Vault before starting the webserver

set -e

echo "🔐 Fetching Airflow credentials from Vault..."

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

# Fetch Airflow application secrets
echo "Fetching Airflow application secrets..."
AIRFLOW_RESPONSE=$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/kv/data/airflow")
export AIRFLOW__CORE__FERNET_KEY=$(echo "$AIRFLOW_RESPONSE" | sed -n 's/.*"fernet_key":"\([^"]*\)".*/\1/p')
export AIRFLOW__WEBSERVER__SECRET_KEY=$(echo "$AIRFLOW_RESPONSE" | sed -n 's/.*"webserver_secret_key":"\([^"]*\)".*/\1/p')

# Fetch PostgreSQL Airflow DB credentials
echo "Fetching Airflow database credentials..."
DB_RESPONSE=$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/kv/data/postgres_airflow")
DB_USER=$(echo "$DB_RESPONSE" | sed -n 's/.*"user":"\([^"]*\)".*/\1/p')
DB_PASS=$(echo "$DB_RESPONSE" | sed -n 's/.*"password":"\([^"]*\)".*/\1/p')
DB_HOST=$(echo "$DB_RESPONSE" | sed -n 's/.*"host":"\([^"]*\)".*/\1/p')
DB_PORT=$(echo "$DB_RESPONSE" | sed -n 's/.*"port":"\([^"]*\)".*/\1/p')
DB_NAME=$(echo "$DB_RESPONSE" | sed -n 's/.*"dbname":"\([^"]*\)".*/\1/p')

export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME?sslmode=require"

echo "✅ Credentials loaded from Vault"
echo "Starting Airflow webserver..."

# Start airflow webserver
exec airflow webserver
