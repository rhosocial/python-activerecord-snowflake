"""Integration test fixtures for Layer 4 (real Snowflake).

All tests in this directory are automatically skipped when
SNOWFLAKE_ACCOUNT environment variable is not set.
"""
import os
import pytest

from rhosocial.activerecord.backend.impl.snowflake import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig

REQUIRED_ENV_VARS = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_WAREHOUSE",
]

missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
if missing:
    pytest.skip(
        f"Missing Snowflake env vars: {', '.join(missing)}",
        allow_module_level=True,
    )


@pytest.fixture(scope="session")
def integration_config():
    return SnowflakeConnectionConfig(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ.get("SNOWFLAKE_PASSWORD"),
        private_key_path=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH"),
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
    )


@pytest.fixture(scope="session")
def integration_backend(integration_config):
    backend = SnowflakeBackend(connection_config=integration_config)
    backend.connect()
    test_schema = f"AR_TEST_{os.getpid()}"
    backend.execute(f"CREATE SCHEMA IF NOT EXISTS {test_schema}", ())
    backend.execute(f"USE SCHEMA {test_schema}", ())
    yield backend
    backend.execute(f"DROP SCHEMA IF EXISTS {test_schema} CASCADE", ())
    backend.disconnect()
