#!/bin/bash
# Metabase Entrypoint with Vault Integration
# Fetches database credentials from Vault before starting Metabase

set -e

echo "🔐 Fetching Metabase database credentials from Vault..."

# Install curl if not available
if ! command -v curl &> /dev/null; then
    echo "Installing curl..."
    apt-get update -qq > /dev/null 2>&1 && apt-get install -y curl -qq > /dev/null 2>&1 || \
    apk add --no-cache curl > /dev/null 2>&1
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

# Fetch Metabase database credentials using curl
echo "Fetching Metabase database credentials..."
VAULT_RESPONSE=$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/kv/data/metabase")
MB_DB_USER=$(echo "$VAULT_RESPONSE" | grep -o '"db_user":"[^"]*"' | cut -d'"' -f4)
MB_DB_PASS=$(echo "$VAULT_RESPONSE" | grep -o '"db_password":"[^"]*"' | cut -d'"' -f4)
MB_DB_HOST=$(echo "$VAULT_RESPONSE" | grep -o '"db_host":"[^"]*"' | cut -d'"' -f4)
MB_DB_PORT=$(echo "$VAULT_RESPONSE" | grep -o '"db_port":"[^"]*"' | cut -d'"' -f4)
MB_DB_NAME=$(echo "$VAULT_RESPONSE" | grep -o '"db_name":"[^"]*"' | cut -d'"' -f4)

# Export Metabase environment variables
export MB_DB_TYPE="postgres"
export MB_DB_DBNAME="$MB_DB_NAME"
export MB_DB_PORT="$MB_DB_PORT"
export MB_DB_USER="$MB_DB_USER"
export MB_DB_PASS="$MB_DB_PASS"
export MB_DB_HOST="$MB_DB_HOST"
export MB_DB_CONNECTION_PROPS="sslmode=disable"

echo "✅ Credentials loaded from Vault"
echo "Starting Metabase..."

# Start Metabase with the original entrypoint
exec /app/run_metabase.sh "$@"
