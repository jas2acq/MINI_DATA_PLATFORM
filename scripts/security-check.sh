#!/bin/bash
# Security validation script
# Checks for hardcoded secrets in configuration files

set -e

echo "🔍 Running Security Audit..."
echo "=============================="

ERRORS=0

# Check Docker Compose for hardcoded passwords
echo ""
echo "Checking docker-compose.yml for hardcoded secrets..."
# Check for actual credential environment variables, excluding file paths and config names
if grep -E "(ROOT_USER|ROOT_PASSWORD|DB_USER|DB_PASSWORD|API_KEY|ACCESS_KEY|SECRET_KEY|FERNET_KEY)\s*=" Docker-compose.yml | \
   grep -v "\${" | \
   grep -v "#" | \
   grep -v "/" | \
   grep -v "KEY_FILE=" | \
   grep -v "KEY_NAME=" | \
   grep -v "SECRET_ENGINE=" | \
   grep -v "SSL_KEY=" | \
   grep -v "SSL_CERT=" ; then
    echo "❌ FAIL: Found hardcoded secrets in docker-compose.yml"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ PASS: No hardcoded secrets in docker-compose.yml"
fi

# Check SQL files for hardcoded passwords
echo ""
echo "Checking SQL files for hardcoded passwords..."
if grep -r -i "PASSWORD\s*['\"]" dags/src/loading/sql/*.sql 2>/dev/null | grep -v "METABASE_PASSWORD" ; then
    echo "❌ FAIL: Found hardcoded passwords in SQL files"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ PASS: No hardcoded passwords in SQL files"
fi

# Check .env file (should have warning if it contains secrets)
echo ""
echo "Checking .env file..."
if grep -E "^(MINIO_ROOT_PASSWORD|AIRFLOW_DB_PASSWORD|AIRFLOW_FERNET_KEY)=" .env 2>/dev/null | grep -v "^#"; then
    echo "⚠️  WARNING: .env file contains secrets (should be in Vault)"
    echo "    These secrets should be removed and managed by Vault"
else
    echo "✅ PASS: .env file does not contain sensitive secrets"
fi

# Check for exposed secrets in Python files
echo ""
echo "Checking Python files for hardcoded secrets..."
if grep -r -E "(password|secret|key)\s*=\s*['\"][^'\"]+['\"]" dags/src/*.py 2>/dev/null | grep -v "field=" | grep -v "description="; then
    echo "❌ FAIL: Found potential hardcoded secrets in Python files"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ PASS: No hardcoded secrets in Python files"
fi

# Check for SSL/TLS configuration
echo ""
echo "Checking SSL/TLS configuration..."
if ! grep -q "ssl=on" Docker-compose.yml; then
    echo "⚠️  WARNING: postgres-airflow may not have SSL enabled"
fi

if grep -q "MINIO_SECURE=False" .env 2>/dev/null; then
    echo "⚠️  WARNING: MinIO running in insecure mode (MINIO_SECURE=False)"
fi

# Summary
echo ""
echo "=============================="
if [ $ERRORS -eq 0 ]; then
    echo "✅ Security audit passed!"
    echo "   All critical security checks passed"
    exit 0
else
    echo "❌ Security audit failed with $ERRORS error(s)"
    echo "   Please fix the issues above before deploying"
    exit 1
fi
