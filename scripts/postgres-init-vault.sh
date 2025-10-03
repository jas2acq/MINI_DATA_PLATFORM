#!/bin/bash
# PostgreSQL initialization script with Vault integration
# Fetches credentials from Vault and initializes database

set -e

echo "🔐 Fetching PostgreSQL credentials from Vault..."

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

# Fetch PostgreSQL Analytics initial credentials using curl
echo "Fetching PostgreSQL Analytics credentials..."
VAULT_RESPONSE=$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/kv/data/postgres_analytics_init")
PGUSER=$(echo "$VAULT_RESPONSE" | grep -o '"user":"[^"]*"' | cut -d'"' -f4)
PGPASSWORD=$(echo "$VAULT_RESPONSE" | grep -o '"password":"[^"]*"' | cut -d'"' -f4)
PGDATABASE=$(echo "$VAULT_RESPONSE" | grep -o '"dbname":"[^"]*"' | cut -d'"' -f4)

# Fetch Metabase user password
echo "Fetching Metabase credentials..."
METABASE_RESPONSE=$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/kv/data/metabase")
METABASE_PASSWORD=$(echo "$METABASE_RESPONSE" | grep -o '"db_password":"[^"]*"' | cut -d'"' -f4)

# Export PostgreSQL environment variables
export POSTGRES_USER="$PGUSER"
export POSTGRES_PASSWORD="$PGPASSWORD"
export POSTGRES_DB="$PGDATABASE"

echo "✅ Credentials loaded from Vault"

# Fix SSL certificate permissions
if [ -f "/var/lib/postgresql/server.key" ]; then
    chmod 600 /var/lib/postgresql/server.key
    chown postgres:postgres /var/lib/postgresql/server.key
fi
if [ -f "/var/lib/postgresql/server.crt" ]; then
    chmod 600 /var/lib/postgresql/server.crt
    chown postgres:postgres /var/lib/postgresql/server.crt
fi

# Initialize PostgreSQL with standard entrypoint
# Then run schema creation with Metabase password
echo "Initializing PostgreSQL..."

# Call the original docker-entrypoint
exec docker-entrypoint.sh "$@"
