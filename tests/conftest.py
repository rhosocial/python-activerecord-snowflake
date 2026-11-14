# tests/conftest.py
"""Root configuration for the Snowflake backend's test tree.

The backend knows its own classes and how a scenario maps to a connection, so
no declaration table is needed here: the scenario is exposed as a parameterized
pytest fixture that the testsuite environment consumes.  Without a real account
and without the emulator the parameter set is empty, and the tests that need a
database are skipped.
"""

import os

import pytest

import support.snowflake

_SCENARIOS = [support.snowflake.scenario(name) for name in support.snowflake.SCENARIOS]


@pytest.fixture(scope="session", params=_SCENARIOS, ids=lambda scenario: scenario.name)
def backend_scenario(request):
    """Return the scenario the tests run against; its id is the scenario name."""
    return request.param


def pytest_configure(config):
    """Register custom markers to avoid PytestUnknownMarkWarning."""
    config.addinivalue_line("markers", "unit: Pure unit tests, no DB dependency")
    config.addinivalue_line("markers", "mock: Uses unittest.mock to simulate DB")
    config.addinivalue_line("markers", "fakesnow: Requires fakesnow package (DuckDB emulator)")
    config.addinivalue_line("markers", "integration: Requires a real Snowflake account")
    config.addinivalue_line("markers", "slow: Test takes longer than 10 seconds")


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests when Snowflake credentials are missing.

    Without a real account the only scenario ``support.snowflake`` can offer is
    the DuckDB emulator, whose limits are the emulator's, not the backend's:

    * its DB-API cursor is synchronous, so ``AsyncSnowflakeBackend`` cannot
      await it at all -- every async contract would fail at connect;
    * ``INSERT ... RETURNING`` with more than one column breaks its
      affected-count path (``too many values to unpack``), which is every
      contract on a composite-primary-key model.

    Skipping them here keeps the run honest: a skipped test says "the
    emulator cannot answer this", where a failure would say "the backend is
    wrong".  The real-account path is not touched.
    """
    has_credentials = bool(os.getenv("SNOWFLAKE_ACCOUNT"))
    if not has_credentials:
        skip_integration = pytest.mark.skip(
            reason="Requires SNOWFLAKE_ACCOUNT and related env vars"
        )
        skip_emulator_async = pytest.mark.skip(
            reason="fakesnow's cursor is synchronous; async contracts need a real account"
        )
        skip_emulator_composite_returning = pytest.mark.skip(
            reason="fakesnow cannot RETURNING more than one column (composite primary key)"
        )
        skip_emulator_transaction = pytest.mark.skip(
            reason="fakesnow does not implement Snowflake's transaction semantics"
        )
        skip_emulator_info_schema = pytest.mark.skip(
            reason="fakesnow's INFORMATION_SCHEMA lacks KIND/EXPRESSION"
        )
        composite_returning_tests = (
            "test_natural_key_on_composite_pk_model",
            "test_conflict_without_matching_lookup_reraises",
        )
        transaction_tests = (
            "test_optimistic_lock",
            "test_stale_record_error_is_database_error",
            "test_combined_concurrent_update",
            "test_bulk_create_update_delete",
        )
        for item in items:
            if "integration" in str(item.fspath):
                item.add_marker(skip_integration)
            if "_async" in item.nodeid:
                item.add_marker(skip_emulator_async)
            if any(name in item.nodeid for name in composite_returning_tests):
                item.add_marker(skip_emulator_composite_returning)
            if any(name in item.nodeid for name in transaction_tests):
                item.add_marker(skip_emulator_transaction)
            if "test_introspection_data_profile.py" in item.nodeid:
                item.add_marker(skip_emulator_info_schema)
