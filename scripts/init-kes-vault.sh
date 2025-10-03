#!/bin/bash
# Initialize Vault AppRole for KES Authentication
# This script configures Vault's transit engine and creates AppRole credentials for KES

set -e

echo "🔐 Configuring Vault for KES Integration..."
echo "=============================================="

# Ensure Vault environment is set
export VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
export VAULT_TOKEN="${VAULT_TOKEN:-${VAULT_DEV_ROOT_TOKEN_ID}}"

if [ -z "$VAULT_TOKEN" ]; then
    echo "❌ Error: VAULT_TOKEN not set"
    exit 1
fi

# Check if Vault is accessible
if ! vault status &>/dev/null; then
    echo "❌ Error: Cannot connect to Vault"
    exit 1
fi

echo ""
echo "📝 Enabling Vault Transit Engine..."
# Enable transit secrets engine if not already enabled
if ! vault secrets list | grep -q "transit/"; then
    vault secrets enable transit
    echo "✅ Transit engine enabled"
else
    echo "✅ Transit engine already enabled"
fi

echo ""
echo "📝 Creating encryption key for MinIO..."
# Create encryption key for MinIO
if ! vault read transit/keys/minio-sse-key &>/dev/null; then
    vault write -f transit/keys/minio-sse-key
    echo "✅ Encryption key 'minio-sse-key' created"
else
    echo "✅ Encryption key 'minio-sse-key' already exists"
fi

echo ""
echo "📝 Enabling AppRole authentication..."
# Enable AppRole auth method if not already enabled
if ! vault auth list | grep -q "approle/"; then
    vault auth enable approle
    echo "✅ AppRole enabled"
else
    echo "✅ AppRole already enabled"
fi

echo ""
echo "📝 Creating KES policy in Vault..."
# Create policy for KES to access transit engine
vault policy write kes-policy - <<EOF
path "transit/encrypt/minio-sse-key" {
   capabilities = [ "update" ]
}
path "transit/decrypt/minio-sse-key" {
   capabilities = [ "update" ]
}
path "transit/keys/minio-sse-key" {
   capabilities = [ "read" ]
}
EOF
echo "✅ KES policy created"

echo ""
echo "📝 Creating AppRole for KES..."
# Create AppRole role for KES
vault write auth/approle/role/kes-role \
    token_num_uses=0 \
    token_ttl=0 \
    token_max_ttl=0 \
    secret_id_num_uses=0 \
    secret_id_ttl=0 \
    policies="kes-policy"
echo "✅ AppRole 'kes-role' created"

echo ""
echo "📝 Generating AppRole credentials..."
# Get Role ID
ROLE_ID=$(vault read -field=role_id auth/approle/role/kes-role/role-id)
echo "Role ID: $ROLE_ID"

# Generate Secret ID
SECRET_ID=$(vault write -field=secret_id -f auth/approle/role/kes-role/secret-id)
echo "Secret ID: $SECRET_ID"

# Store credentials in .env file
echo ""
echo "📝 Updating .env file with KES credentials..."
sed -i "s|^KES_VAULT_APPROLE_ID=.*|KES_VAULT_APPROLE_ID=$ROLE_ID|" .env
sed -i "s|^KES_VAULT_APPROLE_SECRET_ID=.*|KES_VAULT_APPROLE_SECRET_ID=$SECRET_ID|" .env

echo ""
echo "=============================================="
echo "✅ KES Vault configuration complete!"
echo ""
echo "📋 Configuration Summary:"
echo "  • Transit engine enabled at: transit/"
echo "  • Encryption key created: minio-sse-key"
echo "  • AppRole enabled for KES authentication"
echo "  • KES policy created with transit permissions"
echo "  • AppRole credentials stored in .env"
echo ""
echo "⚠️  IMPORTANT: Restart KES and MinIO containers for changes to take effect"
echo "   Run: docker compose restart kes minio"
echo ""
