# tests/rhosocial/activerecord_snowflake_test/feature/basic/conftest.py
"""Pytest configuration for basic feature tests.

Imports fixtures from the testsuite, making them available
to tests in this directory.

Adds skip markers for tests that cannot run under fakesnow
(the DuckDB-based Snowflake emulator used when no real
Snowflake credentials are available).
"""
import os
import pytest

from rhosocial.activerecord.testsuite.feature.basic.conftest import *

_FAKESNOW_ONLY = not bool(os.getenv("SNOWFLAKE_ACCOUNT"))


def _should_skip_with_fakesnow(item):
    """Return (True, reason) if *item* cannot run under fakesnow."""
    nodeid = item.nodeid

    # --- AsyncSnowflakeBackend incompatible with fakesnow ---
    # fakesnow only patches the sync snowflake.connector; the async
    # backend wraps sync ops in run_in_executor producing non-awaitable
    # cursor objects.
    if "async" in nodeid.lower() and "fakesnow" in nodeid:
        return True, "AsyncSnowflakeBackend incompatible with fakesnow"

    # --- Transaction tests ---
    # fakesnow/DuckDB does not support Snowflake's BEGIN/COMMIT/ROLLBACK
    # semantics.  Skip any test whose node ID contains "transaction" or
    # that lives in the connection context test module (all tests there
    # exercise transaction/connection contexts).
    if "fakesnow" not in nodeid:
        return False, ""
    if "transaction" in nodeid.lower():
        return True, "Snowflake transaction semantics not supported by fakesnow"
    if "test_active_record_context" in nodeid:
        return True, "Connection/transaction contexts not supported by fakesnow"
    if "test_active_record_crud" in nodeid:
        return True, "Transaction-based CRUD not supported by fakesnow"

    # --- UUID PK tests ---
    # fakesnow's RETURNING generates broken SQL for UUID values (hyphens
    # interpreted as subtraction).  The following tests all use models
    # with UUID primary keys (TypeTestModel, TypeCase).
    if "TestSyncFields" in nodeid or "TestAsyncFields" in nodeid:
        return True, "TypeTestModel uses UUID PK — not supported by fakesnow RETURNING"
    if "type_case" in nodeid.lower():
        return True, "TypeCase uses UUID PK — not supported by fakesnow RETURNING"
    if "type_test" in nodeid.lower():
        return True, "TypeTestModel uses UUID PK — not supported by fakesnow RETURNING"
    if "uuid" in nodeid.lower():
        return True, "UUID primary keys not supported by fakesnow RETURNING"

    return False, ""


def pytest_collection_modifyitems(config, items):
    if not _FAKESNOW_ONLY:
        return
    for item in items:
        should_skip, reason = _should_skip_with_fakesnow(item)
        if should_skip:
            item.add_marker(pytest.mark.skip(reason=reason))
