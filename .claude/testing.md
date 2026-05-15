# Snowflake Backend Testing Guide

| Item | Value |
|------|-------|
| **Python Version** | 3.8+ |
| **Database Driver** | snowflake-connector-python >= 3.0.0 |
| **Free-Threading Support** | Not tested (driver may not support it) |

## Dependencies

```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.10.0",
    "pytest-cov>=4.0.0",
    "rhosocial-activerecord[test]>=0.9.0,<2.0.0",
]
```

## Quick Test Commands

```bash
# Activate virtual environment
source .venv3.12/bin/activate

# Run unit tests only (no Snowflake connection required)
PYTHONPATH=src pytest tests/ -v -k "not integration"

# Run integration tests (requires snowflake_scenarios.yaml)
PYTHONPATH=src pytest tests/ -v -k "integration"

# Run all tests
PYTHONPATH=src pytest tests/ -v
```

## Test Architecture

### Tier 1: Unit Tests (No Database Required)

- `test_dialect.py` — Dialect formatting and capability detection
- `test_types.py` — SnowflakeVariant, SnowflakeArray
- `test_adapters.py` — Type adapter round-trip conversions
- `test_config.py` — SnowflakeConnectionConfig

### Tier 2: Protocol Conformance (No Database Required)

- `test_protocol_conformance.py` — 5 mandatory protocol test classes

### Tier 3: Mock Tests (No Database Required)

- `test_backend_mock.py` — Mocked snowflake.connector

### Tier 4: Integration Tests (Requires Snowflake)

- `test_backend_integration.py` — Real Snowflake connection
- Requires `tests/config/snowflake_scenarios.yaml`
- Tests skip automatically if no configuration found

## Integration Test Setup

Create `tests/config/snowflake_scenarios.yaml`:

```yaml
scenarios:
  spider2:
    account: "YOUR_ACCOUNT"
    username: "YOUR_USER"
    password: "YOUR_PAT_TOKEN"
    warehouse: "COMPUTE_WH_PARTICIPANT"
    role: "PARTICIPANT"
    database: "IOWA_LIQUOR_SALES"
    schema: "IOWA_LIQUOR_SALES"
```

## Backend-Specific Test Markers

- `@pytest.mark.requires_protocol` — Requires specific protocol support
- `@pytest.mark.snowflake_variant` — Snowflake VARIANT type tests
- `@pytest.mark.snowflake_time_travel` — Time travel query tests

## Key Differences from Core

- No local database available — integration tests require cloud access
- Use PAT (Programmatic Access Token) for CI authentication
- Snowflake warehouse costs apply during integration test runs
- Three-part naming (`database.schema.table`) required in queries
