# Security Architecture

## Table of Contents
- [Security Overview](#security-overview)
- [Encryption in Transit](#encryption-in-transit)
- [Encryption at Rest](#encryption-at-rest)
- [Secrets Management](#secrets-management)
- [PII Anonymization](#pii-anonymization)
- [Certificate Management](#certificate-management)
- [Security Best Practices](#security-best-practices)
- [Compliance Considerations](#compliance-considerations)

## Security Overview

The Mini Data Platform implements defense-in-depth security with multiple layers:

```
┌────────────────────────────────────────────────────┐
│  SECURITY LAYERS                                    │
├────────────────────────────────────────────────────┤
│  1. Network Encryption (TLS 1.2+)                  │
│  2. Data Encryption at Rest (Fernet, KES)          │
│  3. Secrets Management (Vault KV v2)               │
│  4. PII Anonymization (Hash, Redaction)            │
│  5. Access Control (Service Isolation)             │
│  6. Audit Logging (Structured Logs)                │
└────────────────────────────────────────────────────┘
```

### Security Principles

1. **Encryption Everywhere**: Data encrypted in transit and at rest
2. **Zero Trust**: No hardcoded credentials, all secrets from Vault
3. **Least Privilege**: Services have minimum required permissions
4. **Fail Secure**: Errors prevent data leakage
5. **Defense in Depth**: Multiple security controls
6. **Auditability**: All operations logged

## Encryption in Transit

All network communication uses TLS 1.2 or higher for encryption.

### TLS Configuration by Service

#### 1. Airflow Web Server (HTTPS)

**Configuration:**
```yaml
# docker-compose.yml
environment:
  AIRFLOW__WEBSERVER__WEB_SERVER_SSL_CERT: /opt/airflow/certs/server.crt
  AIRFLOW__WEBSERVER__WEB_SERVER_SSL_KEY: /opt/airflow/certs/server.key
```

**Python Code:**
```python
# Airflow automatically serves on HTTPS when certificates configured
# No code changes needed
```

**Verification:**
```bash
curl -v https://localhost:8080/health
# Should show: SSL connection using TLSv1.2 or TLSv1.3
```

#### 2. PostgreSQL (SSL Mode)

**Configuration:**
```bash
# docker-compose.yml
command: >
  postgres -c ssl=on
  -c ssl_cert_file=/var/lib/postgresql/server.crt
  -c ssl_key_file=/var/lib/postgresql/server.key
```

**Python Code (psycopg2):**
```python
import psycopg2

conn = psycopg2.connect(
    host='postgres-analytics',
    port=5432,
    database='shadowpostgresdb',
    user='user',
    password='password',
    sslmode='verify-full',  # Strongest SSL verification
    sslrootcert='/opt/airflow/certs/ca.crt'
)
```

**SSL Modes (strongest to weakest):**
1. `verify-full`: Verify certificate + hostname (PRODUCTION RECOMMENDED)
2. `verify-ca`: Verify certificate chain to root CA
3. `require`: Require SSL, but don't verify certificate
4. `prefer`: Try SSL, fallback to non-SSL (DEFAULT, NOT RECOMMENDED)
5. `allow`: Use SSL if available
6. `disable`: No SSL (INSECURE)

**Verification:**
```bash
docker exec postgres-analytics psql -U user -d db -c "SELECT ssl.version FROM pg_stat_ssl ssl JOIN pg_stat_activity act ON ssl.pid = act.pid WHERE act.usename = current_user;"
# Should show: TLSv1.2 or TLSv1.3
```

#### 3. MinIO (HTTPS)

**Configuration:**
```yaml
# docker-compose.yml
environment:
  MINIO_SERVER_CERT: /certs/public.crt
  MINIO_SERVER_KEY: /certs/private.key
```

**Python Code (minio library):**
```python
import urllib3
from minio import Minio

# Custom HTTP client with CA certificate verification
http_client = urllib3.PoolManager(
    cert_reqs='CERT_REQUIRED',
    ca_certs='/opt/airflow/certs/ca.crt'
)

client = Minio(
    endpoint='minio:9000',
    access_key='access_key',
    secret_key='secret_key',
    secure=True,  # Enable HTTPS
    http_client=http_client
)
```

**Verification:**
```bash
curl -v --cacert certs/ca.crt https://localhost:9000/minio/health/live
# Should show: SSL connection using TLSv1.2 or TLSv1.3
```

#### 4. HashiCorp Vault (HTTPS)

**Configuration (Production):**
```hcl
# vault-config.hcl
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_cert_file = "/vault/certs/vault.crt"
  tls_key_file  = "/vault/certs/vault.key"
}
```

**Python Code (hvac library):**
```python
import hvac
import os

client = hvac.Client(
    url='https://vault:8200',
    token=os.environ['VAULT_TOKEN'],
    verify='/opt/airflow/certs/ca.crt'  # CA certificate for verification
)
```

**Note:** Dev mode uses HTTP (not production-ready)

#### 5. MinIO KES (HTTPS)

**Configuration:**
```yaml
# kes-config.yml
address: 0.0.0.0:7373
tls:
  key: /config/kes-server.key
  cert: /config/kes-server.cert
```

**Verification:**
```bash
curl -v --cacert certs/ca.crt https://localhost:7373/version
# Should show: SSL connection using TLSv1.2 or TLSv1.3
```

### TLS Version Support

**Supported:** TLS 1.2, TLS 1.3
**Not Supported:** TLS 1.0, TLS 1.1, SSLv2, SSLv3 (insecure)

### Network Segmentation

Services communicate via Docker's internal network:

```
┌────────────────────────────────────────┐
│  Docker Network: secure_network        │
├────────────────────────────────────────┤
│  ✓ Airflow → PostgreSQL (port 5432)   │
│  ✓ Airflow → MinIO (port 9000)        │
│  ✓ Airflow → Vault (port 8200)        │
│  ✓ MinIO → KES (port 7373)            │
│  ✓ KES → Vault (port 8200)            │
│  ✓ Metabase → PostgreSQL (port 5432)  │
└────────────────────────────────────────┘

External Access (via host ports):
  - Airflow UI: 8080
  - MinIO Console: 9001
  - Metabase UI: 3000
  - Vault UI: 8200
```

## Encryption at Rest

Data is encrypted when stored on disk.

### 1. Airflow Metadata Database (Fernet)

**Purpose:**
Encrypt Airflow connections, variables, and passwords in PostgreSQL.

**How it Works:**
```
Plaintext → Fernet Encryption → Encrypted Data → PostgreSQL
    ↓                                                ↓
  Secret       AIRFLOW__CORE__FERNET_KEY        ab_connection table
```

**Fernet Key Generation:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Output: X5z9mK2nQ7wP4dR8aF3jL6tY1vB5cH9eN2sG8pU0xM4=
```

**Configuration:**
```yaml
# docker-compose.yml
environment:
  AIRFLOW__CORE__FERNET_KEY: ${AIRFLOW__CORE__FERNET_KEY}
```

**Key Rotation:**
```bash
# 1. Generate new key
NEW_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. Prepend to existing key (comma-separated)
AIRFLOW__CORE__FERNET_KEY="$NEW_KEY,$OLD_KEY"

# 3. Run rotation command
docker exec airflow-webserver airflow rotate-fernet-key
```

**Security Notes:**
- Fernet uses AES-128 in CBC mode with HMAC-SHA256
- Keys are 32 bytes (256 bits) Base64-encoded
- Store Fernet key securely (not in code)
- Rotate keys periodically (every 90 days recommended)

### 2. MinIO Objects (KES + Vault Transit)

**Architecture:**
```
MinIO → KES → Vault Transit Engine → Encrypted Data

1. MinIO receives file upload
2. MinIO requests encryption key from KES
3. KES requests key from Vault Transit
4. Vault generates data encryption key (DEK)
5. KES returns encrypted DEK to MinIO
6. MinIO encrypts object with DEK
7. MinIO stores encrypted object + encrypted DEK
```

**KES Configuration:**
```yaml
# kes-config.yml
keystore:
  vault:
    endpoint: http://vault:8200
    approle:
      id: <VAULT_APPROLE_ID>
      secret: <VAULT_APPROLE_SECRET>
    transit:
      engine: transit
      key: minio-sse-key
```

**Vault Transit Setup:**
```bash
# Enable Transit engine
vault secrets enable transit

# Create encryption key
vault write -f transit/keys/minio-sse-key
```

**MinIO Configuration:**
```yaml
# docker-compose.yml
environment:
  MINIO_KMS_KES_ENDPOINT: https://kes:7373
  MINIO_KMS_KES_KEY_NAME: minio-sse-key
  MINIO_KMS_KES_CERT_FILE: /certs/client.crt
  MINIO_KMS_KES_KEY_FILE: /certs/client.key
  MINIO_KMS_KES_CAPATH: /certs/ca.crt
```

**Python Code (Server-Side Encryption):**
```python
from minio import Minio
from minio.commonconfig import ENABLED
from minio.sse import SseKMS

client = Minio(...)

# Upload with server-side encryption
client.fput_object(
    bucket_name='data-platform',
    object_name='raw/batch_1.csv',
    file_path='/tmp/batch_1.csv',
    sse=SseKMS('minio-sse-key', {})
)
```

**Important Note (2025 Update):**
MinIO Community KES is deprecated as of March 2025. For production:
- Migrate to AIStor KES (enterprise)
- Or use client-side encryption
- Or consider alternative S3-compatible storage

### 3. PostgreSQL Data (OS-Level Encryption)

PostgreSQL itself doesn't provide built-in encryption at rest. Options:

**Option 1: Encrypted Filesystem**
```bash
# LUKS encrypted partition (Linux)
cryptsetup luksFormat /dev/sdb
cryptsetup open /dev/sdb pgdata
mkfs.ext4 /dev/mapper/pgdata
mount /dev/mapper/pgdata /var/lib/postgresql/data
```

**Option 2: Docker Volume Encryption**
Use encrypted Docker volumes (plugin-dependent).

**Option 3: Cloud Provider Encryption**
AWS RDS, Google Cloud SQL, Azure Database provide automatic encryption.

**Recommendation for Development:**
Use encrypted host filesystem where Docker volumes reside.

### 4. Vault Storage (Encrypted Backend)

Vault encrypts all data before writing to storage backend.

**Dev Mode:**
In-memory storage (lost on restart, not production-ready).

**Production:**
Use encrypted storage backend:
- **Consul**: Supports encryption at rest
- **Raft (Integrated Storage)**: Encrypts all data
- **Cloud KMS**: AWS KMS, Google Cloud KMS, Azure Key Vault

## Secrets Management

All secrets stored in HashiCorp Vault (never in code or environment variables).

### Vault KV v2 Engine

**Features:**
- Versioning: Keep up to 10 versions of each secret
- Soft delete: Recover accidentally deleted secrets
- Metadata: Track creation/update times
- Check-and-Set: Prevent concurrent updates

**Secret Paths:**
```
kv/
├── data/
│   ├── minio
│   │   ├── access_key: "shadow"
│   │   └── secret_key: "shadow123"
│   └── postgres_analytics
│       ├── user: "initial_user"
│       ├── password: "initial_password"
│       ├── host: "postgres-analytics"
│       ├── port: "5432"
│       └── dbname: "shadowpostgresdb"
└── metadata/
    ├── minio
    └── postgres_analytics
```

### Python Client (hvac)

**Write Secret:**
```python
import hvac
import os

client = hvac.Client(
    url='http://vault:8200',
    token=os.environ['VAULT_TOKEN']
)

# Write to KV v2
client.secrets.kv.v2.create_or_update_secret(
    path='minio',
    secret={
        'access_key': 'shadow',
        'secret_key': 'shadow123'
    }
)
```

**Read Secret:**
```python
# Read from KV v2
response = client.secrets.kv.v2.read_secret_version(path='minio')

# Access secret data
data = response['data']['data']
access_key = data['access_key']
secret_key = data['secret_key']
```

**Important: KV v2 Path Structure**
- Write/Read: `kv/data/<path>`
- Metadata: `kv/metadata/<path>`
- KV v2 automatically adds `/data/` to the path

### Secret Rotation

**Manual Rotation:**
```python
# Update secret (creates new version)
client.secrets.kv.v2.create_or_update_secret(
    path='minio',
    secret={'access_key': 'new_key', 'secret_key': 'new_secret'}
)

# Read specific version
response = client.secrets.kv.v2.read_secret_version(path='minio', version=1)
```

**Automated Rotation:**
Use Vault's dynamic secrets with database engines (advanced).

### Best Practices

1. **Never Log Secrets:**
   ```python
   # BAD
   logger.info(f"Using password: {password}")

   # GOOD
   logger.info("Authenticating with database")
   ```

2. **Minimize Secret Lifetime:**
   ```python
   # Retrieve secret
   creds = get_vault_secret('postgres_analytics')

   # Use immediately
   conn = psycopg2.connect(**creds)

   # Don't store in variables longer than needed
   del creds
   ```

3. **Rotate Regularly:**
   - Database credentials: Every 90 days
   - API keys: Every 30 days
   - Fernet keys: Every 90 days

4. **Audit Access:**
   Enable Vault audit logging to track secret access.

## PII Anonymization

Personally Identifiable Information (PII) is anonymized before storage.

### PII Fields and Methods

| Field | Original Example | Anonymization Method | Stored Value |
|-------|------------------|----------------------|--------------|
| `customer_email` | john.doe@example.com | SHA-256 hash | e3b0c44298fc1c149afbf... |
| `customer_phone` | 555-123-4567 | Redaction | ***-***-4567 |
| `customer_address` | 123 Main Street | Redaction | *** Street |
| `customer_name` | John Doe | Preserved | John Doe |
| `order_id` | ORD-12345 | Preserved | ORD-12345 |

### Implementation

#### Email Hashing (SHA-256)

```python
import hashlib

def _hash_email(email: str) -> str:
    """Hash email address using SHA-256.

    Args:
        email: Email address to hash.

    Returns:
        Hexadecimal SHA-256 hash of lowercase email.
    """
    return hashlib.sha256(email.lower().encode()).hexdigest()

# Example
email = "John.Doe@Example.com"
hashed = _hash_email(email)
# Output: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

**Why SHA-256:**
- One-way function (irreversible without rainbow tables)
- Deterministic (same email always produces same hash)
- Fast computation
- Standard cryptographic hash

**Limitations:**
- Not salted (vulnerable to rainbow table attacks)
- For production: Consider HMAC-SHA256 with secret key

#### Phone Redaction

```python
def _redact_phone(phone: str) -> str:
    """Redact phone number, keeping last 4 digits.

    Args:
        phone: Phone number in any format.

    Returns:
        Redacted phone (e.g., "***-***-1234").
    """
    digits = ''.join(filter(str.isdigit, phone))
    if len(digits) >= 4:
        return f"***-***-{digits[-4:]}"
    return "***-***-****"

# Example
phone = "(555) 123-4567"
redacted = _redact_phone(phone)
# Output: ***-***-4567
```

#### Address Redaction

```python
def _redact_address(address: str) -> str:
    """Redact address, keeping street name.

    Args:
        address: Full street address.

    Returns:
        Redacted address (e.g., "*** Main Street").
    """
    parts = address.split()
    if len(parts) >= 2:
        return f"*** {' '.join(parts[1:])}"
    return "*** Street"

# Example
address = "123 Main Street, Apt 5B"
redacted = _redact_address(address)
# Output: *** Main Street, Apt 5B
```

### Anonymization Workflow

```
Raw Data               Transformation                Stored Data
---------              --------------                -----------
Email: john@ex.com  →  SHA-256 Hash              →  e3b0c442...
Phone: 555-123-4567 →  Keep last 4 digits        →  ***-***-4567
Address: 123 Main   →  Redact number             →  *** Main
Name: John Doe      →  No change (not PII)       →  John Doe
```

### GDPR Compliance Considerations

**Right to Erasure (Article 17):**
- Hashed emails can be "forgotten" by deleting hash
- Cannot reverse hash to original email
- Satisfies pseudonymization requirement

**Data Minimization (Article 5):**
- Only collect necessary fields
- Redact sensitive portions
- Don't store full PII when partial data sufficient

**Pseudonymization (Article 4):**
- Email hashing qualifies as pseudonymization
- Additional safeguards recommended (salting, key management)

## Certificate Management

### Certificate Generation

All certificates generated by `generate-certs.sh`:

```bash
#!/bin/bash
# Generates self-signed certificates for all services

# Create CA certificate
openssl req -x509 -newkey rsa:2048 -days 365 \
  -keyout certs/ca.key -out certs/ca.crt -nodes \
  -subj "/CN=MiniDataPlatform-CA"

# Create service certificates (signed by CA)
for service in minio postgres airflow kes; do
  openssl req -newkey rsa:2048 -nodes \
    -keyout certs/$service/server.key \
    -out certs/$service/server.csr \
    -subj "/CN=$service"

  openssl x509 -req -in certs/$service/server.csr \
    -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
    -out certs/$service/server.crt -days 365
done
```

### Certificate Permissions

**Critical:** Private keys must have restricted permissions:

```bash
chmod 600 certs/*/server.key
chmod 644 certs/*/server.crt
```

**Docker Volume Mounts:**
```yaml
volumes:
  - ./certs/postgres/server.crt:/var/lib/postgresql/server.crt:ro
  - ./certs/postgres/server.key:/var/lib/postgresql/server.key:ro
```

### Certificate Verification

**Verify certificate details:**
```bash
openssl x509 -in certs/postgres/server.crt -text -noout
```

**Check expiration:**
```bash
openssl x509 -in certs/postgres/server.crt -enddate -noout
# Output: notAfter=Oct 2 12:00:00 2026 GMT
```

### Production Recommendations

1. **Use CA-Issued Certificates:**
   - Let's Encrypt (free, automated renewal)
   - Organizational PKI
   - Commercial CA (DigiCert, GlobalSign)

2. **Certificate Rotation:**
   - Rotate certificates before expiration
   - Automate with cert-manager (Kubernetes) or certbot

3. **Certificate Pinning:**
   - Pin CA certificate in client applications
   - Prevents MITM attacks with rogue certificates

## Security Best Practices

### 1. Non-Root Container Users

All Docker services run as non-root users:

```dockerfile
# Create non-root user
RUN groupadd --system --gid 1001 appgroup && \
    useradd --system --uid 1001 --gid appgroup appuser

# Switch to non-root user
USER appuser
```

### 2. Secrets in Environment Variables

**Never hardcode secrets:**
```python
# BAD
password = "mysecretpassword"

# GOOD
import os
password = os.environ.get('DB_PASSWORD')  # From Vault via entrypoint script
```

### 3. Parameterized Queries

**Prevent SQL injection:**
```python
# BAD
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# GOOD
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### 4. Least Privilege Database Roles

```sql
-- Read-only role for Metabase
CREATE ROLE metabase_reader WITH LOGIN PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE shadowpostgresdb TO metabase_reader;
GRANT USAGE ON SCHEMA public TO metabase_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO metabase_reader;

-- Prevent write access
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM metabase_reader;
```

### 5. Network Policies

Restrict service communication to necessary connections only:

```yaml
# docker-compose.yml (example)
networks:
  secure_network:
    driver: bridge
    internal: true  # No external internet access
```

### 6. Regular Security Updates

```bash
# Update Docker images
docker-compose pull

# Restart services with new images
docker-compose up -d

# Update Python packages
uv sync --upgrade
```

## Compliance Considerations

### GDPR (General Data Protection Regulation)

**Implemented Controls:**
- Encryption in transit (Article 32)
- Encryption at rest (Article 32)
- Pseudonymization of PII (Article 4)
- Data minimization (Article 5)
- Right to erasure capability (Article 17)

**Additional Recommendations:**
- Implement data retention policies
- Add audit logging for data access
- Create data processing agreements (DPAs)

### HIPAA (Health Insurance Portability and Accountability Act)

**If handling health data:**
- Add Business Associate Agreements (BAAs)
- Implement access controls and audit logs
- Add data backup and disaster recovery
- Conduct regular security risk assessments

### SOC 2 (Service Organization Control 2)

**Security Principles:**
- Logical access controls (Vault, TLS)
- Change management (Git workflow)
- Risk mitigation (defense-in-depth)
- Monitoring and logging

## Next Steps

- [Setup Guide](setup.md) - Configure security features
- [Development Guide](development.md) - Secure coding practices
- [Troubleshooting](troubleshooting.md) - Debug security issues
