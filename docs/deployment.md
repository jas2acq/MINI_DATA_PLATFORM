# Deployment Guide

## Table of Contents
- [Production Deployment](#production-deployment)
- [Environment Configuration](#environment-configuration)
- [Security Hardening](#security-hardening)
- [Backup Strategy](#backup-strategy)
- [Monitoring](#monitoring)
- [Scaling](#scaling)

## Production Deployment

### Pre-Deployment Checklist

- [ ] Use CA-issued certificates (not self-signed)
- [ ] Change all default passwords
- [ ] Enable Vault production mode (not dev mode)
- [ ] Configure proper backup strategy
- [ ] Set up monitoring and alerting
- [ ] Configure log aggregation
- [ ] Test disaster recovery procedures
- [ ] Document runbooks

### Production vs Development Differences

| Component | Development | Production |
|-----------|-------------|------------|
| Vault | Dev mode (in-memory) | Production mode (encrypted storage) |
| Certificates | Self-signed | CA-issued (Let's Encrypt, etc.) |
| Passwords | Default | Strong, rotated |
| Logging | Console | Aggregated (ELK, Splunk) |
| Monitoring | None | Prometheus, Grafana |
| Backups | Manual | Automated daily |

## Environment Configuration

### Production Environment Variables

Create `.env.production`:

```bash
# Vault (Production Mode)
VAULT_ADDR=https://vault.yourdomain.com:8200
VAULT_TOKEN=<use-vault-auth-method>

# Airflow
AIRFLOW__CORE__FERNET_KEY=<rotate-every-90-days>
AIRFLOW_SECRET_KEY=<strong-random-key>
AIRFLOW__WEBSERVER__SECRET_KEY=<strong-random-key>

# Database
POSTGRES_ANALYTICS_PASSWORD=<strong-password>
AIRFLOW_DB_PASSWORD=<strong-password>

# MinIO
MINIO_ROOT_PASSWORD=<strong-password-min-8-chars>

# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@yourdomain.com
SMTP_PASSWORD=<app-specific-password>
```

### Vault Production Configuration

**vault-config.hcl:**
```hcl
storage "consul" {
  address = "consul:8500"
  path    = "vault/"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_cert_file = "/vault/certs/vault.crt"
  tls_key_file  = "/vault/certs/vault.key"
}

seal "awskms" {
  region     = "us-east-1"
  kms_key_id = "your-kms-key-id"
}

ui = true
```

## Security Hardening

### 1. Non-Root Containers

Ensure all containers run as non-root:

```yaml
# docker-compose.yml
services:
  airflow-webserver:
    user: "50000:0"  # Non-root user
```

### 2. Network Segmentation

```yaml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No internet access
```

### 3. Secrets Management

**Never use environment variables for secrets in production:**

```yaml
# BAD
environment:
  DB_PASSWORD: "hardcoded-password"

# GOOD
environment:
  VAULT_ADDR: "https://vault:8200"
# Application retrieves secrets from Vault at runtime
```

### 4. TLS Everywhere

```yaml
# All services must use TLS
- Airflow: HTTPS
- PostgreSQL: sslmode=verify-full
- MinIO: HTTPS
- Vault: HTTPS
- Metabase: HTTPS
```

### 5. Firewall Rules

```bash
# Allow only necessary ports
ufw allow 443/tcp    # HTTPS (reverse proxy)
ufw allow 22/tcp     # SSH (restricted IPs)
ufw deny 8080/tcp    # Block direct Airflow access
ufw deny 9000/tcp    # Block direct MinIO access
ufw deny 5432/tcp    # Block direct PostgreSQL access
```

## Backup Strategy

### PostgreSQL Backups

**Automated daily backups:**

```bash
#!/bin/bash
# scripts/backup-postgres.sh

BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)

docker exec postgres-analytics pg_dump \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  -F c \
  -f /tmp/backup_${DATE}.dump

docker cp postgres-analytics:/tmp/backup_${DATE}.dump \
  ${BACKUP_DIR}/backup_${DATE}.dump

# Compress
gzip ${BACKUP_DIR}/backup_${DATE}.dump

# Upload to S3
aws s3 cp ${BACKUP_DIR}/backup_${DATE}.dump.gz \
  s3://your-bucket/postgres-backups/

# Retain last 30 days
find ${BACKUP_DIR} -name "*.dump.gz" -mtime +30 -delete
```

**Cron schedule:**
```bash
0 2 * * * /path/to/scripts/backup-postgres.sh
```

### MinIO Backups

```bash
#!/bin/bash
# scripts/backup-minio.sh

docker exec minio mc mirror \
  local/data-platform \
  s3/backup-bucket/data-platform-$(date +%Y%m%d)
```

### Vault Backups

```bash
# Snapshot Vault data
docker exec vault vault operator raft snapshot save /tmp/vault-snapshot.snap

# Copy to backup location
docker cp vault:/tmp/vault-snapshot.snap ./backups/
```

## Monitoring

### Metrics Collection

**Prometheus configuration:**

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'airflow'
    static_configs:
      - targets: ['airflow-webserver:8080']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'minio'
    static_configs:
      - targets: ['minio:9000']
```

### Health Checks

**Automated health monitoring:**

```bash
#!/bin/bash
# scripts/health-check.sh

# Check Airflow
if ! curl -f http://localhost:8080/health > /dev/null 2>&1; then
  echo "Airflow health check failed" | mail -s "Alert" admin@example.com
fi

# Check PostgreSQL
if ! docker exec postgres-analytics pg_isready; then
  echo "PostgreSQL health check failed" | mail -s "Alert" admin@example.com
fi

# Check MinIO
if ! curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; then
  echo "MinIO health check failed" | mail -s "Alert" admin@example.com
fi
```

### Log Aggregation

**ELK Stack integration:**

```yaml
# docker-compose.yml
services:
  filebeat:
    image: docker.elastic.co/beats/filebeat:8.0.0
    volumes:
      - ./logs:/logs:ro
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
```

## Scaling

### Horizontal Scaling

**Multiple Airflow workers:**

```yaml
# docker-compose.yml
services:
  airflow-worker-1:
    <<: *airflow-common
    command: celery worker

  airflow-worker-2:
    <<: *airflow-common
    command: celery worker

  airflow-worker-3:
    <<: *airflow-common
    command: celery worker
```

### Database Connection Pooling

```python
# Use connection pooling for PostgreSQL
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    connection_string,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
```

### MinIO Distributed Mode

For high availability and increased storage:

```yaml
# docker-compose.yml
services:
  minio-1:
    command: server http://minio-{1...4}/data{1...2}

  minio-2:
    command: server http://minio-{1...4}/data{1...2}

  minio-3:
    command: server http://minio-{1...4}/data{1...2}

  minio-4:
    command: server http://minio-{1...4}/data{1...2}
```

## Next Steps

- [Security Architecture](security.md) - Security best practices
- [Monitoring](monitoring.md) - Detailed monitoring setup
- [Troubleshooting](troubleshooting.md) - Debug production issues
