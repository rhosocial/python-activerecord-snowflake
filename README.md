# rhosocial-activerecord-snowflake

[![Python](https://img.shields.io/pypi/pyversions/rhosocial-activerecord-snowflake.svg)](https://pypi.org/project/rhosocial-activerecord-snowflake/)
[![Apache 2.0 License](https://img.shields.io/github/license/rhosocial/python-activerecord-snowflake.svg)](https://github.com/rhosocial/python-activerecord-snowflake/blob/main/LICENSE)
[![Powered by vistart](https://img.shields.io/badge/Powered_by-vistart-blue.svg)](https://github.com/vistart)

<div align="center">
    <img src="https://raw.githubusercontent.com/rhosocial/python-activerecord/main/docs/images/logo.svg" alt="rhosocial ActiveRecord Logo" width="200"/>
    <h3>Snowflake Backend for rhosocial-activerecord</h3>
    <p><b>Cloud Data Warehouse Support · VARIANT & ARRAY Types · Time Travel Queries</b></p>
</div>

> **Note**: This is a backend implementation for [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord). It cannot be used standalone.

## Why This Backend?

### 1. Snowflake-Specific Optimizations

| Feature | This Backend | Generic Solutions |
|---------|-------------|-------------------|
| **VARIANT Type** | Native semi-structured data | JSON serialize/deserialize |
| **Time Travel** | `AT/BEFORE` point-in-time queries | Manual snapshot management |
| **ARRAY Type** | Native array operations | Comma-separated strings |
| **MERGE** | Native upsert with conditions | Manual check-then-insert |

### 2. True Sync-Async Parity

Same API surface for both sync and async operations:

```python
# Sync
users = User.query().where(User.c.age >= 18).all()

# Async - just add await
users = await User.query().where(User.c.age >= 18).all()
```

### 3. Built for Cloud Data Warehouse

- **Warehouse-aware** connection configuration
- **Schema and role** support for multi-tenant environments
- **Time travel** for point-in-time data access
- **VARIANT/ARRAY** type adapters for semi-structured data

## Quick Start

### Installation

```bash
pip install rhosocial-activerecord-snowflake
```

### Basic Usage

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.snowflake import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig
from typing import Optional

class User(ActiveRecord):
    __table_name__ = "users"
    id: Optional[int] = None
    name: str
    email: str

# Configure
config = SnowflakeConnectionConfig(
    account="your-account",
    warehouse="COMPUTE_WH",
    database="myapp",
    schema="public",
    username="user",
    password="password",
    role="SYSADMIN"
)
User.configure(config, SnowflakeBackend)

# Use
user = User(name="Alice", email="alice@example.com")
user.save()
```

## Snowflake-Specific Features

### VARIANT Type (Semi-Structured Data)

Native Snowflake VARIANT support for JSON-like data:

```python
from rhosocial.activerecord.backend.impl.snowflake import SnowflakeVariantAdapter

# Store and query semi-structured data
settings = {"theme": "dark", "notifications": True}
```

### Time Travel Queries

Access historical data using Snowflake's time travel capabilities:

```python
# Query data as of a specific timestamp
results = User.query().where(User.c.age >= 18).all()

# Time travel with AT/BEFORE clauses (via raw SQL)
```

### MERGE (Conditional Upsert)

Efficient conditional insert-or-update operations:

```python
# Snowflake MERGE support for complex upsert scenarios
```

## Requirements

- **Python**: 3.8+ (including 3.14t free-threaded builds; 3.13t is NOT supported due to `cffi` dependency incompatibility)
- **Core**: `rhosocial-activerecord>=0.9.0`
- **Driver**: `snowflake-connector-python>=3.0.0`

## Comparison with Other Backends

| Feature | Snowflake | MySQL | PostgreSQL | SQLite |
|---------|-----------|-------|------------|--------|
| **VARIANT/JSON** | ✅ VARIANT | ✅ JSON | ✅ JSONB | ⚠️ JSON1 |
| **Arrays** | ✅ ARRAY | ❌ | ✅ Native | ❌ |
| **Time Travel** | ✅ Native | ❌ | ❌ | ❌ |
| **MERGE** | ✅ Native | ❌ | ✅ (PG 15+) | ❌ |
| **RETURNING** | ❌ | ❌ | ✅ | ✅ |
| **Cloud-Native** | ✅ | ❌ | ❌ | ❌ |

## Testing

> ⚠️ **CRITICAL**: Tests MUST run serially. Do NOT use `pytest -n auto` or parallel execution.

```bash
# Run all tests
PYTHONPATH=src pytest tests/

# Run specific feature tests
PYTHONPATH=src pytest tests/rhosocial/activerecord_snowflake_test/feature/backend/
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[Apache License 2.0](LICENSE) — Copyright © 2025 [vistart](https://github.com/vistart)

---

<div align="center">
    <p><b>Built with ❤️ by the rhosocial team</b></p>
    <p><a href="https://github.com/rhosocial/python-activerecord-snowflake">GitHub</a> · <a href="https://docs.python-activerecord.dev.rho.social">Documentation</a> · <a href="https://pypi.org/project/rhosocial-activerecord-snowflake/">PyPI</a></p>
</div>
