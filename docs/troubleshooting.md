# Troubleshooting Guide

## Table of Contents
- [Common Issues](#common-issues)
- [Service-Specific Issues](#service-specific-issues)
- [Debugging Tools](#debugging-tools)
- [Logs Location](#logs-location)

## Common Issues

### Issue: Vault Authentication Fails

**Symptoms:**
```
Error: permission denied
hvac.exceptions.Forbidden: 403 Client Error
```

**Causes:**
- Incorrect `VAULT_DEV_ROOT_TOKEN_ID`
- Vault not started
- Token expired

**Solutions:**
1. Verify token in `.env` matches Vault:
   ```bash
   grep VAULT_DEV_ROOT_TOKEN_ID .env
   docker-compose logs vault | grep "Root Token"
   ```

2. Restart Vault:
   ```bash
   docker-compose restart vault
   docker-compose logs -f vault
   ```

3. Re-initialize secrets:
   ```bash
   ./scripts/init-vault-secrets.sh
   ```

### Issue: MinIO Connection Refused

**Symptoms:**
```
urllib3.exceptions.MaxRetryError
ConnectionRefusedError: [Errno 111] Connection refused
```

**Causes:**
- MinIO not running
- Network connectivity issues
- Incorrect endpoint URL

**Solutions:**
1. Check MinIO status:
   ```bash
   docker-compose ps minio
   docker-compose logs minio
   ```

2. Test network connectivity:
   ```bash
   docker exec airflow-scheduler ping -c 3 minio
   ```

3. Verify MinIO credentials in Vault:
   ```bash
   docker exec -e VAULT_ADDR='http://127.0.0.1:8200' \
     -e VAULT_TOKEN='your-token' \
     vault kv get kv/minio
   ```

### Issue: PostgreSQL SSL Error

**Symptoms:**
```
psycopg2.OperationalError: SSL error: certificate verify failed
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Causes:**
- Missing certificates
- Incorrect certificate permissions
- Certificate expired

**Solutions:**
1. Verify certificates exist:
   ```bash
   ls -la certs/postgres/
   # Should show server.crt and server.key
   ```

2. Check certificate permissions:
   ```bash
   chmod 600 certs/postgres/server.key
   chmod 644 certs/postgres/server.crt
   ```

3. Regenerate certificates:
   ```bash
   ./generate-certs.sh
   docker-compose restart postgres-analytics
   ```

4. Test SSL connection:
   ```bash
   docker exec postgres-analytics psql -U user -d db \
     -c "SELECT version FROM pg_stat_ssl WHERE pid = pg_backend_pid();"
   ```

### Issue: Airflow DAG Not Appearing

**Symptoms:**
- DAG not visible in Airflow UI
- DAG showing import errors

**Causes:**
- Syntax errors in DAG file
- Missing dependencies
- DAG file not in `dags/` directory

**Solutions:**
1. Check DAG file syntax:
   ```bash
   uv run python dags/process_sales_data_dag.py
   ```

2. Check scheduler logs:
   ```bash
   docker-compose logs airflow-scheduler | grep ERROR
   ```

3. List DAGs via CLI:
   ```bash
   docker exec airflow-scheduler airflow dags list
   ```

4. Manually refresh DAGs:
   ```bash
   docker exec airflow-scheduler airflow dags reserialize
   ```

### Issue: Permission Denied in Docker Volumes

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied: '/opt/airflow/logs/...'
```

**Causes:**
- Incorrect file ownership
- Wrong AIRFLOW_UID

**Solutions:**
1. Set correct AIRFLOW_UID:
   ```bash
   echo "AIRFLOW_UID=$(id -u)" >> .env
   ```

2. Fix ownership:
   ```bash
   sudo chown -R $(id -u):$(id -g) logs/ dags/
   ```

3. Restart services:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Issue: Out of Memory

**Symptoms:**
```
MemoryError: Unable to allocate array
Killed (OOM)
```

**Causes:**
- Processing large files without chunking
- Insufficient Docker memory allocation

**Solutions:**
1. Increase Docker memory limit (Docker Desktop → Settings → Resources)

2. Verify chunking is enabled:
   ```python
   # Check file size before loading
   file_size = get_object_size(minio_client, file_key)
   if file_size > 1_000_000_000:  # 1GB
       # Use chunked processing
   ```

3. Reduce chunk size:
   ```python
   CHUNK_SIZE = 5_000  # Instead of 10_000
   ```

## Service-Specific Issues

### Vault

**Issue: Vault sealed**
```bash
# Check status
docker exec vault vault status

# Unseal (dev mode auto-unseals, production requires manual unseal)
docker exec vault vault operator unseal <unseal-key>
```

**Issue: Secret not found**
```bash
# List secrets
docker exec -e VAULT_ADDR='http://127.0.0.1:8200' \
  -e VAULT_TOKEN='your-token' \
  vault kv list kv/

# Get specific secret
docker exec -e VAULT_ADDR='http://127.0.0.1:8200' \
  -e VAULT_TOKEN='your-token' \
  vault kv get kv/minio
```

### MinIO

**Issue: Bucket not found**
```bash
# List buckets
docker exec minio mc ls local/

# Create bucket
docker exec minio mc mb local/data-platform
```

**Issue: KES connection failed**
```bash
# Check KES status
docker-compose logs kes

# Test KES endpoint
curl -k https://localhost:7373/version
```

### PostgreSQL

**Issue: Database not accepting connections**
```bash
# Check PostgreSQL status
docker exec postgres-analytics pg_isready

# View logs
docker-compose logs postgres-analytics

# Restart PostgreSQL
docker-compose restart postgres-analytics
```

**Issue: Schema not found**
```bash
# Re-run schema creation
docker exec -i postgres-analytics psql -U user -d db \
  < dags/src/loading/sql/create_star_schema.sql
```

### Airflow

**Issue: Webserver not starting**
```bash
# Check logs
docker-compose logs airflow-webserver

# Common causes:
# - Fernet key missing
# - Database not initialized
# - Port 8080 already in use

# Reinitialize database
docker-compose run airflow-init
```

**Issue: Task stuck in running state**
```bash
# Clear task state
docker exec airflow-scheduler airflow tasks clear \
  process_sales_data \
  process_file \
  --yes

# Kill zombie tasks
docker exec airflow-scheduler airflow tasks kill \
  process_sales_data \
  process_file \
  2025-10-01
```

## Debugging Tools

### Docker Commands

**View running containers:**
```bash
docker-compose ps
```

**View logs:**
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs airflow-scheduler

# Follow logs (real-time)
docker-compose logs -f airflow-scheduler

# Last N lines
docker-compose logs --tail=100 airflow-scheduler
```

**Execute commands in container:**
```bash
docker exec -it airflow-scheduler bash
```

**Inspect container:**
```bash
docker inspect airflow-scheduler
```

**View resource usage:**
```bash
docker stats
```

### Network Debugging

**Test connectivity:**
```bash
docker exec airflow-scheduler ping -c 3 postgres-analytics
```

**Check DNS resolution:**
```bash
docker exec airflow-scheduler nslookup vault
```

**View network details:**
```bash
docker network inspect mini_data_platform_secure_network
```

### Database Debugging

**Connect to PostgreSQL:**
```bash
docker exec -it postgres-analytics psql -U user -d db
```

**Useful SQL queries:**
```sql
-- Check tables
\dt

-- Check connections
SELECT * FROM pg_stat_activity;

-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE schemaname = 'public';

-- View recent inserts
SELECT * FROM fact_sales ORDER BY created_at DESC LIMIT 10;
```

### Airflow Debugging

**Test DAG parsing:**
```bash
uv run python dags/process_sales_data_dag.py
```

**List DAGs:**
```bash
docker exec airflow-scheduler airflow dags list
```

**Test task:**
```bash
docker exec airflow-scheduler airflow tasks test \
  process_sales_data \
  process_file \
  2025-10-01
```

**View XCom values:**
```bash
docker exec airflow-scheduler airflow tasks xcom-list \
  process_sales_data \
  2025-10-01
```

## Logs Location

### Application Logs

```
logs/
├── pipeline.log          # Main ETL pipeline logs
├── ingestion.log         # MinIO data retrieval logs
├── validation.log        # Data validation logs
├── transformation.log    # Data transformation logs
└── loading.log          # PostgreSQL loading logs
```

### Airflow Logs

```
logs/airflow/
└── dag_id=process_sales_data/
    └── run_id=scheduled__2025-10-01T02:00:00+00:00/
        └── task_id=process_file/
            └── attempt=1.log
```

### Docker Logs

```bash
# View logs for specific service
docker-compose logs <service_name>

# Services:
# - vault
# - kes
# - minio
# - postgres-airflow
# - postgres-analytics
# - airflow-webserver
# - airflow-scheduler
# - metabase
```

### Log Analysis

**Search for errors:**
```bash
docker-compose logs airflow-scheduler | grep ERROR
```

**Filter by timestamp:**
```bash
docker-compose logs --since 2025-10-01T10:00:00 airflow-scheduler
```

**Save logs to file:**
```bash
docker-compose logs > all-logs.txt
```

## Test Failures

### Issue: S3Error Constructor TypeError

**Symptoms:**
```
TypeError: S3Error.__init__() missing 1 required positional argument: 'host_id'
```

**Cause:**
- Using old S3Error constructor without `response` parameter
- MinIO library updated S3Error to require BaseHTTPResponse object

**Solution:**
```python
from unittest.mock import Mock
from minio.error import S3Error

# Correct way to create S3Error in tests
mock_response = Mock()
mock_response.status = 404
error = S3Error(
    response=mock_response,
    code="NoSuchKey",
    message="The specified key does not exist.",
    resource="raw/file.csv",
    request_id="req123",
    host_id="host456",
)
```

### Issue: Datetime Types Lost After Validation

**Symptoms:**
```
AssertionError: assert False
where False = is_datetime64_any_dtype(valid_df["order_date"])
```

**Cause:**
- Pydantic's `model_dump()` converts datetime objects to strings by default
- DataFrame created from dumped models has object dtype instead of datetime64

**Solution:**
The validator now uses `model_dump(mode='python')` to preserve Python types and explicitly converts date columns back to datetime64:

```python
# In validator.py
valid_records.append(validated_record.model_dump(mode='python'))

# After creating DataFrame
for col in ["order_date", "delivery_date", "data_collected_at"]:
    if col in valid_df.columns:
        valid_df[col] = pd.to_datetime(valid_df[col])
```

### Issue: Date Parsing Fails with Missing Columns

**Symptoms:**
```
ValueError: Missing column provided to 'parse_dates': 'order_date'
```

**Cause:**
- CSV file doesn't have all expected date columns
- `pd.read_csv()` fails when parse_dates specifies non-existent columns

**Solution:**
The ingestion module now checks CSV header before parsing dates:

```python
# Read header to detect available columns
df_header = pd.read_csv(io.BytesIO(data), nrows=0)
available_columns = df_header.columns.tolist()

# Only parse dates for columns that exist
potential_date_columns = ["order_date", "delivery_date", "data_collected_at"]
date_columns = [col for col in potential_date_columns if col in available_columns]

# Parse with filtered column list
df = pd.read_csv(io.BytesIO(data), parse_dates=date_columns)
```

## Next Steps

- [Setup Guide](setup.md) - Initial configuration
- [Development Guide](development.md) - Development workflow
- [Security Architecture](security.md) - Security configuration
