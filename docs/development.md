# Development Guide

## Table of Contents
- [Development Setup](#development-setup)
- [Code Quality Tools](#code-quality-tools)
- [Git Workflow](#git-workflow)
- [Coding Standards](#coding-standards)
- [Testing Strategy](#testing-strategy)
- [Adding New Features](#adding-new-features)
- [Debugging](#debugging)

## Development Setup

### Environment Preparation

```bash
# Clone repository
git checkout https://github.com/your-org/mini-data-platform.git
cd mini-data-platform

# Install UV package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Install dependencies (including dev dependencies)
uv sync
```

### IDE Configuration

**VS Code** (`settings.json`):
```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  },
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"]
}
```

**PyCharm:**
1. Settings → Project → Python Interpreter → Add Interpreter → Existing
2. Select `.venv/bin/python`
3. Settings → Tools → Python Integrated Tools → Testing → pytest
4. Settings → Tools → Ruff → Enable

## Code Quality Tools

### Ruff (Linting & Formatting)

**Check linting:**
```bash
uv run ruff check .
```

**Auto-fix issues:**
```bash
uv run ruff check --fix .
```

**Format code:**
```bash
uv run ruff format .
```

**Configuration** (`pyproject.toml`):
```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "DTZ", "T10", "DJ", "EM", "G", "INP", "PIE", "PYI", "PT", "RSE", "RET", "SIM", "TID", "ARG", "PTH", "PD", "PGH", "PL", "TRY", "NPY", "RUF"]
ignore = ["S101", "PLR0913"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "PLR2004"]
```

### MyPy (Type Checking)

**Run type checking:**
```bash
uv run mypy dags/src/
```

**Configuration** (`pyproject.toml`):
```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
strict_equality = true
```

### Pytest (Testing)

**Run all tests:**
```bash
uv run pytest
```

**Run with coverage:**
```bash
uv run pytest --cov=dags/src --cov-report=html --cov-report=term
```

**Run specific test file:**
```bash
uv run pytest tests/unit/test_validation.py -v
```

**Run tests matching pattern:**
```bash
uv run pytest -k "test_validate" -v
```

### Pre-Commit Hooks

**Install pre-commit:**
```bash
uv add --dev pre-commit
```

**Create `.pre-commit-config.yaml`:**
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

**Install hooks:**
```bash
uv run pre-commit install
```

**Run manually:**
```bash
uv run pre-commit run --all-files
```

## Git Workflow

### Branch Strategy

```
main
 └─ dev
     ├─ feature/add-data-validation
     ├─ fix/postgres-ssl-connection
     ├─ docs/update-readme
     ├─ refactor/split-transformer
     └─ test/add-ingestion-tests
```

**Branch Naming:**
- `feature/*`: New features
- `fix/*`: Bug fixes
- `docs/*`: Documentation updates
- `refactor/*`: Code refactoring
- `test/*`: Test additions

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code restructuring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements

**Examples:**
```bash
feat(validation): add chunked dataframe validation support

Implement chunking for large files >1GB to prevent memory issues.
Uses generators to process data in 10,000 row chunks.

Closes #42

fix(loading): correct ssl certificate verification for postgres

Changed sslmode from 'require' to 'verify-full' for proper
certificate validation in production environments.

test(transformation): add unit tests for pii anonymization

Covers email hashing, phone redaction, and address redaction
with edge cases for empty strings and invalid formats.
```

### Daily Workflow

```bash
# 1. Start of day - sync with main
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/my-new-feature

# 3. Make changes and test
# ... edit files ...
uv run pytest
uv run ruff check --fix .
uv run mypy dags/src/

# 4. Commit changes
git add dags/src/validation/validator.py
git commit -m "feat(validation): add email format validation"

# 5. Push to remote
git push origin feature/my-new-feature

# 6. Create Pull Request (using GitHub CLI)
gh pr create --title "Add email format validation" \
  --body "Implements RFC 5322 email validation" \
  --base main
```

### Pull Request Checklist

Before creating PR:
- [ ] All tests pass (`uv run pytest`)
- [ ] Code formatted (`uv run ruff format .`)
- [ ] Linting clean (`uv run ruff check .`)
- [ ] Type checking passes (`uv run mypy dags/src/`)
- [ ] Coverage >80% for new code
- [ ] Documentation updated
- [ ] CHANGELOG.md updated

## Coding Standards

### File Organization

```python
"""Module docstring explaining purpose.

Detailed description of module functionality,
usage examples, and any important notes.
"""

# Standard library imports
import logging
import os
from typing import Any

# Third-party imports
import pandas as pd
from pydantic import BaseModel

# Local imports
from dags.src.utils.helpers import get_vault_client

# Module-level constants
CHUNK_SIZE = 10_000
DEFAULT_TIMEOUT = 30

# Module-level logger
logger = logging.getLogger(__name__)

# Functions (alphabetically ordered)
def function_a():
    ...

def function_b():
    ...
```

### Function Standards

**Maximum 50 lines per function:**
```python
def validate_data(df: pd.DataFrame, schema: type[BaseModel]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate DataFrame against Pydantic schema.

    Args:
        df: DataFrame to validate.
        schema: Pydantic model class for validation.

    Returns:
        Tuple of (valid_df, invalid_df).

    Raises:
        ValueError: If DataFrame is empty.

    Example:
        >>> valid, invalid = validate_data(sales_df, SalesRecord)
        >>> print(f"Valid: {len(valid)}, Invalid: {len(invalid)}")
    """
    if df.empty:
        raise ValueError("Cannot validate empty DataFrame")

    valid_rows = []
    invalid_rows = []

    for idx, row in df.iterrows():
        try:
            schema(**row.to_dict())
            valid_rows.append(row)
        except ValidationError as e:
            row['validation_error'] = str(e)
            invalid_rows.append(row)

    return pd.DataFrame(valid_rows), pd.DataFrame(invalid_rows)
```

### Type Hints

**Always use type hints:**
```python
from typing import Optional

def get_customer_name(
    first: str,
    last: str,
    middle: Optional[str] = None
) -> str:
    """Combine customer name parts."""
    if middle:
        return f"{first} {middle} {last}"
    return f"{first} {last}"
```

### Error Handling

**Specific exceptions:**
```python
from minio.error import S3Error
import psycopg2

# BAD
try:
    result = risky_operation()
except Exception as e:
    logger.error(f"Error: {e}")

# GOOD
try:
    minio_client.get_object('bucket', 'key')
except S3Error as e:
    logger.error(f"MinIO error: {e.message}")
    raise
except psycopg2.OperationalError as e:
    logger.error(f"Database connection failed: {e}")
    raise
```

### Logging

**Structured logging:**
```python
import logging

logger = logging.getLogger(__name__)

# Log levels
logger.debug("Detailed diagnostic info")
logger.info("General informational messages")
logger.warning("Warning messages for potential issues")
logger.error("Error messages for failures")
logger.critical("Critical system failures")

# Context in logs
logger.info(f"Processing file: {file_key}, size: {file_size} bytes")

# Never log secrets
logger.info("Connected to database")  # GOOD
logger.info(f"Password: {password}")  # BAD
```

## Testing Strategy

### Test Structure

```
tests/
├── unit/              # Test individual functions
├── integration/       # Test component interactions
├── e2e/              # Test complete workflows
└── conftest.py       # Shared fixtures
```

### Unit Test Example

```python
"""Unit tests for validation module."""

import pandas as pd
import pytest
from pydantic import ValidationError

from dags.src.utils.schemas import SalesRecord
from dags.src.validation.validator import validate_data


def test_validate_data_all_valid():
    """Test validation with all valid records."""
    df = pd.DataFrame([
        {'order_id': 'ORD-001', 'quantity': 5, 'price': 99.99},
        {'order_id': 'ORD-002', 'quantity': 2, 'price': 49.99}
    ])

    valid_df, invalid_df = validate_data(df, SalesRecord)

    assert len(valid_df) == 2
    assert len(invalid_df) == 0


def test_validate_data_with_invalid():
    """Test validation with some invalid records."""
    df = pd.DataFrame([
        {'order_id': 'ORD-001', 'quantity': 5, 'price': 99.99},
        {'order_id': 'INVALID', 'quantity': -1, 'price': 'not_a_number'}
    ])

    valid_df, invalid_df = validate_data(df, SalesRecord)

    assert len(valid_df) == 1
    assert len(invalid_df) == 1
    assert 'validation_error' in invalid_df.columns


def test_validate_data_empty_dataframe():
    """Test validation with empty DataFrame."""
    df = pd.DataFrame()

    with pytest.raises(ValueError, match="Cannot validate empty DataFrame"):
        validate_data(df, SalesRecord)
```

### Integration Test Example

```python
"""Integration tests for ingestion → validation flow."""

import pandas as pd
import pytest

from dags.src.ingestion.minio_client import get_minio_client
from dags.src.validation.validator import validate_data
from dags.src.utils.schemas import SalesRecord


@pytest.fixture
def minio_client(vault_client_mock):
    """Mock MinIO client."""
    return get_minio_client(vault_client_mock)


def test_ingest_and_validate_flow(minio_client, sample_csv_data):
    """Test complete ingest → validate workflow."""
    # Upload test data to MinIO
    minio_client.put_object('data-platform', 'raw/test.csv', sample_csv_data)

    # Ingest
    df = get_raw_data(minio_client, 'raw/test.csv')

    # Validate
    valid_df, invalid_df = validate_data(df, SalesRecord)

    assert len(valid_df) > 0
    assert len(invalid_df) == 0
```

### Test Coverage

**Target: 80% coverage minimum**

```bash
uv run pytest --cov=dags/src --cov-report=term-missing
```

**Coverage report shows:**
```
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
dags/src/ingestion/minio_client.py        150     10    93%   45-47, 89
dags/src/validation/validator.py          100      5    95%   78-80
dags/src/transformation/transformer.py     200     30    85%   120-135
---------------------------------------------------------------------
TOTAL                                      450     45    90%
```

## Adding New Features

### Feature Development Workflow

1. **Create issue:**
   ```bash
   gh issue create --title "Add email validation" \
     --body "Implement RFC 5322 email validation in validator"
   ```

2. **Create branch:**
   ```bash
   git checkout -b feature/email-validation
   ```

3. **Write failing test (TDD):**
   ```python
   def test_validate_email_format():
       """Test email format validation."""
       valid_email = "user@example.com"
       invalid_email = "not-an-email"

       assert is_valid_email(valid_email) is True
       assert is_valid_email(invalid_email) is False
   ```

4. **Run test (should fail):**
   ```bash
   uv run pytest tests/unit/test_validation.py::test_validate_email_format
   ```

5. **Implement feature:**
   ```python
   import re

   def is_valid_email(email: str) -> bool:
       """Validate email format per RFC 5322."""
       pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
       return bool(re.match(pattern, email))
   ```

6. **Run test (should pass):**
   ```bash
   uv run pytest tests/unit/test_validation.py::test_validate_email_format
   ```

7. **Refactor & optimize:**
   - Add edge case handling
   - Improve performance
   - Add documentation

8. **Commit:**
   ```bash
   git add dags/src/validation/validator.py tests/unit/test_validation.py
   git commit -m "feat(validation): add RFC 5322 email format validation"
   ```

9. **Push & create PR:**
   ```bash
   git push origin feature/email-validation
   gh pr create
   ```

### Adding New Python Dependencies

**Never edit `pyproject.toml` manually. Always use UV:**

```bash
# Add runtime dependency
uv add requests

# Add dev dependency
uv add --dev pytest-mock

# Remove dependency
uv remove requests

# Update all dependencies
uv sync --upgrade
```

## Debugging

### Local Debugging

**Python debugger (pdb):**
```python
import pdb

def problematic_function(data):
    pdb.set_trace()  # Debugger breakpoint
    result = process_data(data)
    return result
```

**VS Code debugger** (`.vscode/launch.json`):
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Current File",
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "justMyCode": false
    },
    {
      "name": "Pytest: Current File",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["${file}", "-v"],
      "console": "integratedTerminal"
    }
  ]
}
```

### Docker Debugging

**Access running container:**
```bash
docker exec -it airflow-scheduler bash
```

**View logs:**
```bash
# Real-time logs
docker-compose logs -f airflow-scheduler

# Last 100 lines
docker-compose logs --tail=100 airflow-scheduler

# Specific service
docker-compose logs postgres-analytics
```

**Inspect environment:**
```bash
docker exec airflow-scheduler env | grep VAULT
```

### Airflow Debugging

**Test task independently:**
```bash
docker exec airflow-scheduler airflow tasks test \
  process_sales_data \
  process_file \
  2025-10-01
```

**Check DAG parsing:**
```bash
docker exec airflow-scheduler airflow dags list
```

**View task logs:**
```bash
# Via UI: DAG → Run → Task → Logs

# Via CLI:
docker exec airflow-scheduler airflow tasks logs \
  process_sales_data \
  process_file \
  2025-10-01 \
  --try-number 1
```

## Next Steps

- [Testing Guide](testing.md) - Comprehensive testing strategies
- [API Reference](api-reference.md) - Function documentation
- [Troubleshooting](troubleshooting.md) - Debug common issues
