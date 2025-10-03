# Testing Guide

## Table of Contents
- [Testing Philosophy](#testing-philosophy)
- [Test Organization](#test-organization)
- [Unit Tests](#unit-tests)
- [Integration Tests](#integration-tests)
- [End-to-End Tests](#end-to-end-tests)
- [Mocking Strategies](#mocking-strategies)
- [Coverage Requirements](#coverage-requirements)

## Testing Philosophy

**Test-Driven Development (TDD):**
1. Write test first
2. Run test (should fail)
3. Write minimal code to pass
4. Refactor while keeping tests green
5. Repeat

**Testing Pyramid:**
```
      /\
     /E2E\      ← Few (slow, expensive)
    /──────\
   /  Int   \   ← Some (moderate speed)
  /──────────\
 /    Unit    \ ← Many (fast, cheap)
/______________\
```

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Fast, isolated tests
│   ├── __init__.py
│   ├── test_helpers.py
│   ├── test_ingestion.py
│   ├── test_validation.py
│   ├── test_transformation.py
│   ├── test_loading.py
│   ├── test_pipeline.py
│   └── test_notifications.py
├── integration/             # Component interaction tests
│   ├── __init__.py
│   ├── test_ingestion_validation.py
│   └── test_transformation_loading.py
└── e2e/                     # Full pipeline tests
    ├── __init__.py
    └── test_full_pipeline.py
```

## Unit Tests

**Target:** 80%+ coverage, fast execution (<5 seconds total)

### Shared Fixtures (conftest.py)

```python
"""Shared test fixtures for all tests."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch


@pytest.fixture
def sample_sales_data():
    """Sample sales DataFrame for testing."""
    return pd.DataFrame([
        {
            'order_id': 'ORD-001',
            'customer_email': 'john@example.com',
            'customer_phone': '555-123-4567',
            'quantity': 5,
            'original_price': 99.99,
            'discounted_price': 79.99
        }
    ])


@pytest.fixture
def vault_client_mock():
    """Mock HashiCorp Vault client."""
    mock = Mock()
    mock.secrets.kv.v2.read_secret_version.return_value = {
        'data': {
            'data': {
                'access_key': 'test_key',
                'secret_key': 'test_secret'
            }
        }
    }
    return mock


@pytest.fixture
def minio_client_mock():
    """Mock MinIO client."""
    mock = Mock()
    mock.get_object.return_value = Mock()
    return mock
```

### Example Unit Tests

**test_validation.py:**
```python
"""Unit tests for validation module."""

import pandas as pd
import pytest
from pydantic import ValidationError

from dags.src.utils.schemas import SalesRecord
from dags.src.validation.validator import validate_data


class TestValidateData:
    """Test suite for validate_data function."""

    def test_all_valid_records(self, sample_sales_data):
        """Test with all valid records."""
        valid_df, invalid_df = validate_data(sample_sales_data, SalesRecord)

        assert len(valid_df) == 1
        assert len(invalid_df) == 0
        assert 'order_id' in valid_df.columns

    def test_mixed_valid_invalid(self):
        """Test with mix of valid and invalid records."""
        df = pd.DataFrame([
            {'order_id': 'ORD-001', 'quantity': 5},  # Valid
            {'order_id': 'BAD', 'quantity': -1}       # Invalid
        ])

        valid_df, invalid_df = validate_data(df, SalesRecord)

        assert len(valid_df) == 1
        assert len(invalid_df) == 1
        assert 'validation_error' in invalid_df.columns

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame()

        with pytest.raises(ValueError, match="Cannot validate empty DataFrame"):
            validate_data(df, SalesRecord)

    def test_missing_required_field(self):
        """Test record missing required field."""
        df = pd.DataFrame([{'quantity': 5}])  # Missing order_id

        valid_df, invalid_df = validate_data(df, SalesRecord)

        assert len(valid_df) == 0
        assert len(invalid_df) == 1
```

**test_transformation.py:**
```python
"""Unit tests for transformation module."""

import pandas as pd
import pytest

from dags.src.transformation.transformer import (
    transform_sales_data,
    _hash_email,
    _redact_phone,
    _redact_address
)


class TestEmailHashing:
    """Test email hashing function."""

    def test_hash_consistency(self):
        """Same email produces same hash."""
        email = "test@example.com"
        hash1 = _hash_email(email)
        hash2 = _hash_email(email)

        assert hash1 == hash2

    def test_case_insensitive(self):
        """Hashing is case-insensitive."""
        hash1 = _hash_email("Test@Example.com")
        hash2 = _hash_email("test@example.com")

        assert hash1 == hash2

    def test_different_emails_different_hashes(self):
        """Different emails produce different hashes."""
        hash1 = _hash_email("user1@example.com")
        hash2 = _hash_email("user2@example.com")

        assert hash1 != hash2


class TestPhoneRedaction:
    """Test phone number redaction."""

    def test_standard_format(self):
        """Test standard phone format."""
        result = _redact_phone("555-123-4567")
        assert result == "***-***-4567"

    def test_parentheses_format(self):
        """Test phone with parentheses."""
        result = _redact_phone("(555) 123-4567")
        assert result == "***-***-4567"

    def test_short_number(self):
        """Test phone number too short."""
        result = _redact_phone("123")
        assert result == "***-***-****"
```

### Running Unit Tests

```bash
# All unit tests
uv run pytest tests/unit/

# Specific test file
uv run pytest tests/unit/test_validation.py

# Specific test function
uv run pytest tests/unit/test_validation.py::test_all_valid_records

# With verbose output
uv run pytest tests/unit/ -v

# With coverage
uv run pytest tests/unit/ --cov=dags/src --cov-report=term
```

## Integration Tests

**Target:** Test interactions between 2-3 components

### Example Integration Tests

**test_ingestion_validation.py:**
```python
"""Integration tests for ingestion → validation flow."""

import pandas as pd
import pytest
from io import BytesIO

from dags.src.ingestion.minio_client import get_minio_client, get_raw_data
from dags.src.validation.validator import validate_data
from dags.src.utils.schemas import SalesRecord


@pytest.fixture
def test_csv_data():
    """Create test CSV data."""
    data = "order_id,quantity,price\nORD-001,5,99.99\nORD-002,-1,invalid"
    return BytesIO(data.encode())


class TestIngestionValidationFlow:
    """Test ingestion to validation workflow."""

    def test_ingest_then_validate(self, vault_client_mock, minio_client_mock, test_csv_data):
        """Test complete ingest → validate flow."""
        # Setup MinIO mock
        minio_client_mock.get_object.return_value.read.return_value = test_csv_data.getvalue()

        # Get MinIO client
        client = get_minio_client(vault_client_mock)

        # Ingest data
        df = get_raw_data(client, 'raw/test.csv')

        # Validate data
        valid_df, invalid_df = validate_data(df, SalesRecord)

        # Assertions
        assert len(df) == 2
        assert len(valid_df) == 1  # One valid record
        assert len(invalid_df) == 1  # One invalid record
```

## End-to-End Tests

**Target:** Test complete pipeline workflows

### Example E2E Test

**test_full_pipeline.py:**
```python
"""End-to-end tests for complete ETL pipeline."""

import pytest
import pandas as pd
from unittest.mock import patch, Mock

from dags.src.pipeline import run_pipeline


@pytest.fixture
def mock_all_dependencies(monkeypatch):
    """Mock all external dependencies."""
    # Mock Vault
    vault_mock = Mock()
    vault_mock.secrets.kv.v2.read_secret_version.return_value = {
        'data': {'data': {'user': 'test', 'password': 'test'}}
    }

    # Mock MinIO
    minio_mock = Mock()
    minio_mock.stat_object.return_value = Mock(size=1000)
    minio_mock.get_object.return_value.read.return_value = b"order_id,quantity\nORD-001,5"

    # Mock PostgreSQL
    postgres_mock = Mock()

    return vault_mock, minio_mock, postgres_mock


class TestFullPipeline:
    """Test complete ETL pipeline."""

    @patch('dags.src.pipeline.get_vault_client')
    @patch('dags.src.pipeline.get_minio_client')
    @patch('dags.src.pipeline.get_postgres_connection')
    def test_successful_pipeline_run(
        self,
        postgres_mock,
        minio_mock,
        vault_mock,
        mock_all_dependencies
    ):
        """Test successful pipeline execution."""
        vault_client, minio_client, pg_conn = mock_all_dependencies

        vault_mock.return_value = vault_client
        minio_mock.return_value = minio_client
        postgres_mock.return_value = pg_conn

        # Run pipeline
        run_pipeline('raw/test.csv')

        # Verify all steps called
        assert vault_mock.called
        assert minio_mock.called
        assert postgres_mock.called
```

## Mocking Strategies

### When to Mock

**Mock external dependencies:**
- Vault API calls
- MinIO S3 operations
- PostgreSQL connections
- Email sending
- File system operations

**Don't mock:**
- Pure functions (no side effects)
- Pydantic validation
- Pandas operations

### Mock Examples

**Mock Vault client:**
```python
from unittest.mock import Mock

vault_mock = Mock()
vault_mock.secrets.kv.v2.read_secret_version.return_value = {
    'data': {
        'data': {
            'access_key': 'test_key',
            'secret_key': 'test_secret'
        }
    }
}
```

**Mock MinIO client:**
```python
from unittest.mock import Mock, MagicMock

minio_mock = Mock()
minio_mock.get_object.return_value = MagicMock(
    read=lambda: b"test,data\n1,2"
)
```

**Mock database connection:**
```python
from unittest.mock import Mock

conn_mock = Mock()
cursor_mock = Mock()
conn_mock.cursor.return_value = cursor_mock
cursor_mock.execute.return_value = None
cursor_mock.fetchall.return_value = [(1, 'test')]
```

## Coverage Requirements

### Target Coverage

- **Overall**: 80% minimum
- **Critical paths**: 95% minimum
- **Utils modules**: 90% minimum

### Running Coverage

```bash
# Terminal report
uv run pytest --cov=dags/src --cov-report=term-missing

# HTML report
uv run pytest --cov=dags/src --cov-report=html

# Both
uv run pytest --cov=dags/src --cov-report=html --cov-report=term
```

### Coverage Report Example

```
Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
dags/src/ingestion/minio_client.py    150     10    93%   45-47, 89
dags/src/validation/validator.py     100      5    95%   78-80
dags/src/transformation/transformer   200     30    85%   120-135
dags/src/loading/postgres_loader.py   180     15    92%   200-205
dags/src/pipeline.py                  120      8    93%   150-152
-----------------------------------------------------------------
TOTAL                                 750     68    91%
```

### Improving Coverage

**Find untested code:**
```bash
uv run pytest --cov=dags/src --cov-report=term-missing
# Look at "Missing" column for line numbers
```

**Add tests for missing lines:**
```python
# Previously untested edge case
def test_validate_data_with_none_values():
    """Test validation with None values."""
    df = pd.DataFrame([{'order_id': None, 'quantity': 5}])

    valid_df, invalid_df = validate_data(df, SalesRecord)

    assert len(invalid_df) == 1
```

## Next Steps

- [Development Guide](development.md) - Development workflow
- [API Reference](api-reference.md) - Function documentation
- [Troubleshooting](troubleshooting.md) - Debug test failures
