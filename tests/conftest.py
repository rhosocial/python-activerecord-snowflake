"""
Root pytest configuration for the rhosocial-activerecord-snowflake package.

Responsibilities:
1. Set the environment variable for testsuite provider registry discovery.
2. Register custom test markers (unit, mock, fakesnow, integration, slow).
3. Auto-skip integration tests when no Snowflake credentials are available.
"""
import os
import pytest

# Set the environment variable that the testsuite uses to locate the provider registry.
os.environ.setdefault(
    'TESTSUITE_PROVIDER_REGISTRY',
    'providers.registry:provider_registry'
)


def pytest_configure(config):
    """Register custom markers to avoid PytestUnknownMarkWarning."""
    config.addinivalue_line("markers", "unit: Pure unit tests, no DB dependency")
    config.addinivalue_line("markers", "mock: Uses unittest.mock to simulate DB")
    config.addinivalue_line("markers", "fakesnow: Requires fakesnow package (DuckDB emulator)")
    config.addinivalue_line("markers", "integration: Requires a real Snowflake account")
    config.addinivalue_line("markers", "slow: Test takes longer than 10 seconds")


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests when Snowflake credentials are missing."""
    has_credentials = bool(os.getenv("SNOWFLAKE_ACCOUNT"))
    if not has_credentials:
        skip_integration = pytest.mark.skip(
            reason="Requires SNOWFLAKE_ACCOUNT and related env vars"
        )
        for item in items:
            if "integration" in str(item.fspath):
                item.add_marker(skip_integration)
