# tests/rhosocial/activerecord_snowflake_test/feature/backend/conftest.py
"""Fixtures for the backend-owned tests.

These tests talk to a Snowflake account (real, or the fakesnow emulator
``support.snowflake`` enables) rather than to testsuite fixtures, so this
directory carries its own fixtures instead of a suite contract.  The scenario
supplies the account parameters; the database name is derived from the
directory that owns the test, so two directories never share tables.
"""
import pytest

import support.snowflake

from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend

#: (scenario, database) pairs whose database has already been reset.
_PREPARED_DATABASES = set()


def _database_for(request) -> str:
    """Derive the logical database the directory owning the test runs in."""
    parts = list(request.node.path.parts)
    try:
        index = max(i for i, part in enumerate(parts) if part == "backend")
    except ValueError:
        return "test_backend"
    names = [part for part in parts[index + 1 : -1] if part]
    return "test_backend" + "".join("_" + name for name in names)


def _prepare_database(scenario_name: str, database: str) -> None:
    """Create the directory's database once per scenario."""
    key = (scenario_name, database)
    if key in _PREPARED_DATABASES:
        return
    support.snowflake.scenario(scenario_name).reset_database(database)
    _PREPARED_DATABASES.add(key)


def pytest_collection_modifyitems(config, items):
    """Pin a backend directory's tests to one worker.

    These directories create and drop tables in the directory's own database.
    The suite plugin pins every *contract* directory already; backend-owned
    directories resolve their database here instead of through a contract, so
    two workers resetting the same database at once would race exactly the
    same way.  Grouping by directory, not by module, is what keeps them apart.
    """
    for item in items:
        parts = item.path.parts
        if "backend" not in parts:
            continue
        item.add_marker(pytest.mark.xdist_group("snowflake-backend::" + str(item.path.parent)))


@pytest.fixture(scope="module")
def snowflake_scenarios():
    """The scenarios this run enables, or a skip when none is configured."""
    scenarios = support.snowflake.get_enabled_scenarios()
    if not scenarios:
        pytest.skip("No Snowflake scenarios configured")
    return scenarios


@pytest.fixture(scope="module")
def snowflake_config(request, snowflake_scenarios):
    """The first enabled scenario, pointed at this directory's database."""
    scenario_name = next(iter(snowflake_scenarios))
    database = _database_for(request)
    _prepare_database(scenario_name, database)
    return support.snowflake.scenario(scenario_name).make_config(database)


@pytest.fixture(scope="module")
def snowflake_backend(snowflake_config):
    """A connected backend on this directory's database."""
    backend = SnowflakeBackend(connection_config=snowflake_config)
    backend.connect()
    yield backend
    backend.disconnect()
