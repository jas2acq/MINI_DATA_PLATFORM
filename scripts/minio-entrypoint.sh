#!/bin/bash
# MinIO Entrypoint with Vault Integration
# Fetches credentials from Vault before starting MinIO

set -e

echo "🔐 Fetching MinIO credentials from Vault..."

# Install curl if not available (MinIO image is minimal and has no package manager)
if ! command -v curl &> /dev/null; then
    echo "❌ Error: curl not available and cannot be installed"
    exit 1
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

# Fetch MinIO credentials using curl
echo "Fetching MinIO root credentials..."
VAULT_RESPONSE=$(curl -s -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/kv/data/minio")
export MINIO_ROOT_USER=$(echo "$VAULT_RESPONSE" | sed -n 's/.*"root_user":"\([^"]*\)".*/\1/p')
export MINIO_ROOT_PASSWORD=$(echo "$VAULT_RESPONSE" | sed -n 's/.*"root_password":"\([^"]*\)".*/\1/p')

echo "✅ Credentials loaded from Vault"
echo "Starting MinIO server..."

# Start MinIO with the original command
exec /usr/bin/minio server /data --console-address ":9001" "$@"
