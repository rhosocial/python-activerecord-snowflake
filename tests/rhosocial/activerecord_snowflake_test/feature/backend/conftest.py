"""Conftest for Snowflake backend tests.

Loads scenario configuration from YAML for integration tests.
Skips integration tests if no configuration is available.
"""
import os
import pytest

try:
    import yaml
except ImportError:
    yaml = None


def _load_scenarios():
    """Load Snowflake scenarios from YAML config."""
    if yaml is None:
        return None

    config_path = os.path.join(
        os.path.dirname(__file__), "config", "snowflake_scenarios.yaml"
    )
    if not os.path.exists(config_path):
        return None

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not data or "scenarios" not in data:
        return None

    return data["scenarios"]


def _skip_if_no_scenarios():
    """Skip test if no Snowflake scenarios are configured."""
    scenarios = _load_scenarios()
    if scenarios is None:
        pytest.skip("No Snowflake scenarios configured (snowflake_scenarios.yaml missing)")
    return scenarios


@pytest.fixture(scope="module")
def snowflake_scenarios():
    """Provide Snowflake scenarios dict, skip if unavailable."""
    return _skip_if_no_scenarios()


@pytest.fixture(scope="module")
def snowflake_config(snowflake_scenarios):
    """Provide the first Snowflake connection config."""
    scenario_name = list(snowflake_scenarios.keys())[0]
    scenario = snowflake_scenarios[scenario_name]

    from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig

    return SnowflakeConnectionConfig(
        account=scenario.get("account"),
        database=scenario.get("database"),
        schema=scenario.get("schema"),
        username=scenario.get("username"),
        password=scenario.get("password"),
        warehouse=scenario.get("warehouse"),
        role=scenario.get("role"),
        autocommit=True,
        client_session_keep_alive=True,
    )


@pytest.fixture(scope="module")
def snowflake_backend(snowflake_config):
    """Provide a connected SnowflakeBackend instance (module-scoped)."""
    from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend

    backend = SnowflakeBackend(connection_config=snowflake_config)
    backend.connect()
    yield backend
    backend.disconnect()
