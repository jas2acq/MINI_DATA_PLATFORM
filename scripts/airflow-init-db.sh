#!/bin/bash
# Airflow Database Initialization Script
# Fetches credentials from Vault and initializes Airflow database

set -e

echo "🔐 Fetching Airflow credentials from Vault..."

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

# Fetch Airflow application secrets
echo "Fetching Airflow application secrets..."
AIRFLOW_RESPONSE=$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/kv/data/airflow")
export AIRFLOW__CORE__FERNET_KEY=$(echo "$AIRFLOW_RESPONSE" | grep -o '"fernet_key":"[^"]*"' | cut -d'"' -f4)
export AIRFLOW__WEBSERVER__SECRET_KEY=$(echo "$AIRFLOW_RESPONSE" | grep -o '"webserver_secret_key":"[^"]*"' | cut -d'"' -f4)

# Fetch PostgreSQL Airflow DB credentials
echo "Fetching Airflow database credentials..."
DB_RESPONSE=$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/kv/data/postgres_airflow")
DB_USER=$(echo "$DB_RESPONSE" | grep -o '"user":"[^"]*"' | cut -d'"' -f4)
DB_PASS=$(echo "$DB_RESPONSE" | grep -o '"password":"[^"]*"' | cut -d'"' -f4)
DB_HOST=$(echo "$DB_RESPONSE" | grep -o '"host":"[^"]*"' | cut -d'"' -f4)
DB_PORT=$(echo "$DB_RESPONSE" | grep -o '"port":"[^"]*"' | cut -d'"' -f4)
DB_NAME=$(echo "$DB_RESPONSE" | grep -o '"dbname":"[^"]*"' | cut -d'"' -f4)

export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME?sslmode=require"

echo "✅ Credentials loaded from Vault"

# Note: Skipping pip install - Airflow image already has packages pre-installed
# Installing from requirements.txt causes version conflicts (2.8.1 → 3.1.0)
# echo "Installing Python requirements..."
# pip install --no-cache-dir -r /opt/airflow/requirements.txt > /dev/null 2>&1

# Initialize Airflow database
echo "Initializing Airflow database..."
su airflow -c "airflow db migrate"

# Create admin user
echo "Creating Airflow admin user..."
su airflow -c "airflow users create \
  --username admin \
  --password admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com" || echo "Admin user already exists"

echo "✅ Airflow initialization complete!"
