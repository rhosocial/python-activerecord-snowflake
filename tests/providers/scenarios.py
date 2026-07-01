"""Test scenario definitions for Snowflake backend.

Registers a "fakesnow" scenario for local testing with the DuckDB-based
Snowflake emulator. Real Snowflake scenarios can be added via environment
variables or config files.
"""
import os
from typing import Dict, Any, Tuple, Type

from rhosocial.activerecord.backend.impl.snowflake import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig

# Scenario name -> configuration dictionary mapping
SCENARIO_MAP: Dict[str, Dict[str, Any]] = {}

# Whether fakesnow patch is active
_fakesnow_patch_active = False
_fakesnow_patch_cm = None  # Keep context manager alive


def register_scenario(name: str, config: Dict[str, Any]):
    """Register a Snowflake test scenario."""
    SCENARIO_MAP[name] = config


def get_scenario(name: str) -> Tuple[Type[SnowflakeBackend], SnowflakeConnectionConfig]:
    """Get backend class and connection config for a scenario."""
    if name not in SCENARIO_MAP:
        if SCENARIO_MAP:
            name = next(iter(SCENARIO_MAP))
        else:
            raise ValueError("No scenarios registered")

    config = SnowflakeConnectionConfig(**SCENARIO_MAP[name])
    return SnowflakeBackend, config


def get_enabled_scenarios() -> Dict[str, Any]:
    """Return all enabled scenarios for parameterization."""
    return SCENARIO_MAP


def _ensure_fakesnow_patch():
    """Apply fakesnow.patch() if not already active and no real credentials."""
    global _fakesnow_patch_active, _fakesnow_patch_cm
    if _fakesnow_patch_active:
        return
    if os.getenv("SNOWFLAKE_ACCOUNT"):
        return
    try:
        import fakesnow
        _fakesnow_patch_cm = fakesnow.patch()
        _fakesnow_patch_cm.__enter__()
        _fakesnow_patch_active = True
    except ImportError:
        pass


def _register_default_scenarios():
    """Register default scenarios based on available credentials."""
    if os.getenv("SNOWFLAKE_ACCOUNT"):
        _register_real_scenarios()
    else:
        _register_fakesnow_scenarios()


def _register_fakesnow_scenarios():
    """Register fakesnow-based scenario for local testing."""
    _ensure_fakesnow_patch()
    register_scenario("fakesnow", {
        "account": "test-account.us-east-1",
        "user": "test_user",
        "password": "test_password",
        "database": "TEST_DB",
        "schema": "PUBLIC",
        "warehouse": "TEST_WH",
        "role": "SYSADMIN",
        "version": (8, 0, 0),  # fakesnow reports (0,0,0); force high version for RETURNING support
    })


def _register_real_scenarios():
    """Register real Snowflake scenario from environment variables."""
    register_scenario("snowflake", {
        "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
        "user": os.getenv("SNOWFLAKE_USER", ""),
        "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
        "database": os.getenv("SNOWFLAKE_DATABASE", ""),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", ""),
        "role": os.getenv("SNOWFLAKE_ROLE", ""),
    })


_register_default_scenarios()
