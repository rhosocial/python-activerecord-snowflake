Run the full test suite for python-activerecord-snowflake.

**Prerequisites:**
```bash
cd /Users/vistart/PycharmProjects/rhosocial/python-activerecord-snowflake
source .venv3.12/bin/activate
export PYTHONPATH=src
```

**Run unit tests only (no Snowflake connection required):**
```bash
pytest tests/ -v -k "not integration"
```

**Run integration tests (requires snowflake_scenarios.yaml):**
```bash
pytest tests/ -v -k "integration"
```

**Run all tests:**
```bash
pytest tests/ -v
```

**Test directories:**
- `tests/rhosocial/activerecord_snowflake_test/feature/backend/` - Backend-specific tests

Show test results and any failures. Focus on failing tests and suggest fixes.
