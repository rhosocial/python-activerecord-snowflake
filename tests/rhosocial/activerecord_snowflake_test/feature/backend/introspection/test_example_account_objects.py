# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_example_account_objects.py
"""The account-object example: refuses cleanly, and demonstrates the cache.

No test here opens a Snowflake connection. Two paths are covered:

* with no credentials the example prints the variables to set and exits 2,
  having built no connection and no statement;
* with a mocked backend it runs end to end, so the cold/warm executor counts
  it prints -- and the cache behaviour they claim -- really execute.

The second path patches ``SnowflakeBackend`` in the example module, so nothing
in the example is skipped by a marker: the whole body of ``main()`` runs.
Copyright-free by design: no row is invented on the refusal path.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

EXAMPLE = (
    "rhosocial.activerecord.backend.impl.snowflake.examples."
    "introspection_account_objects"
)


def database_row(**overrides):
    row = {
        "DATABASE_NAME": "ANALYTICS",
        "DATABASE_OWNER": "SYSADMIN",
        "IS_TRANSIENT": "NO",
        "COMMENT": "reporting",
        "CREATED": datetime(2026, 1, 2, 3, 4, 5),
        "LAST_ALTERED": datetime(2026, 2, 3, 4, 5, 6),
        "RETENTION_TIME": 1,
        "TYPE": "STANDARD",
        "OWNER_ROLE_TYPE": "ROLE",
    }
    row.update(overrides)
    return row


def warehouse_row(**overrides):
    """A ``SHOW WAREHOUSES`` row, in the documented lowercase shape."""
    row = {
        "name": "COMPUTE_WH",
        "state": "STARTED",
        "type": "STANDARD",
        "size": "X-Small",
        "min_cluster_count": 1,
        "max_cluster_count": 1,
        "started_clusters": 1,
        "running": 0,
        "queued": 0,
        "is_default": "Y",
        "is_current": "Y",
        "is_interactive": "N",
        "auto_suspend": 60,
        "auto_resume": True,
        "created_on": datetime(2026, 1, 1),
        "resumed_on": None,
        "updated_on": datetime(2026, 1, 3),
        "owner": "SYSADMIN",
        "comment": None,
        "scaling_policy": "STANDARD",
        "resource_constraint": None,
        "generation": 1,
        "enable_query_acceleration": False,
        "query_acceleration_max_scale_factor": None,
        "resource_monitor": None,
        "owner_role_type": "ROLE",
    }
    row.update(overrides)
    return row


def schema_row(**overrides):
    row = {
        "CATALOG_NAME": "ANALYTICS",
        "SCHEMA_NAME": "PUBLIC",
        "SCHEMA_OWNER": "SYSADMIN",
        "IS_TRANSIENT": "NO",
        "IS_MANAGED_ACCESS": "NO",
        "RETENTION_TIME": 1,
        "CREATED": datetime(2026, 1, 2, 3, 4, 5),
        "LAST_ALTERED": None,
        "COMMENT": None,
    }
    row.update(overrides)
    return row


def storage_row(**overrides):
    row = {
        "TABLE_CATALOG": "ANALYTICS",
        "TABLE_SCHEMA": "PUBLIC",
        "TABLE_NAME": "ORDERS",
        "ID": 7,
        "CLONE_GROUP_ID": 7,
        "IS_TRANSIENT": "NO",
        "ACTIVE_BYTES": 2048,
        "TIME_TRAVEL_BYTES": 128,
        "FAILSAFE_BYTES": 64,
        "RETAINED_FOR_CLONE_BYTES": 16,
        "TABLE_CREATED": datetime(2026, 1, 2),
        "TABLE_DROPPED": None,
        "TABLE_ENTERED_FAILSAFE": None,
        "COMMENT": None,
        "TABLE_TYPE": "BASE TABLE",
        "ROW_COUNT": 3,
        "CLUSTERING_KEY": None,
        "AUTO_CLUSTERING_ON": False,
    }
    row.update(overrides)
    return row


def clean_env() -> Dict[str, Optional[str]]:
    """Every variable the example reads, set to ``None`` (unset)."""
    return {
        name: None
        for name in (
            "SNOWFLAKE_ACCOUNT",
            "SNOWFLAKE_USER",
            "SNOWFLAKE_PASSWORD",
            "SNOWFLAKE_PRIVATE_KEY_PATH",
            "SNOWFLAKE_DATABASE",
            "SNOWFLAKE_WAREHOUSE",
            "SNOWFLAKE_SCHEMA",
            "SNOWFLAKE_ROLE",
        )
    }


class _RecordingExecutor:
    """A stand-in for the driver-backed executor, per the repo's mock pattern.

    It answers the statements the introspector really sends and counts them,
    which is exactly what the example's own wrapper observes -- so the printed
    cold/warm figures are this object's call counts, not a double mock.

    ``silent`` models the account the role has been granted nothing on: every
    question is answered with no rows. The tables listing is answered with one
    table unless ``silent`` is set, because the example needs a table name to
    measure and a silent account has none.
    """

    def __init__(self, silent: bool = False) -> None:
        self.silent = silent
        self.statements: List[Tuple[str, tuple]] = []

    def execute(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        self.statements.append((sql, params))
        if self.silent:
            return []
        if "SHOW WAREHOUSES" in sql:
            return [warehouse_row()]
        if "INFORMATION_SCHEMA.DATABASES" in sql:
            return [database_row()]
        if "INFORMATION_SCHEMA.SCHEMATA" in sql:
            return [schema_row()]
        if "TABLE_STORAGE_METRICS" in sql:
            return [storage_row()]
        if "INFORMATION_SCHEMA.TABLES" in sql:
            return [
                {"TABLE_NAME": "ORDERS", "TABLE_TYPE": "BASE TABLE", "COMMENT": None}
            ]
        return []

    @property
    def question_count(self) -> int:
        return len(self.statements)


@pytest.fixture
def example_module():
    """The example, imported only when a test needs it.

    Importing it pulls in the backend, which imports the Snowflake connector
    package; that is a real import cost this suite would otherwise pay for
    every test that merely mentions the example's name.
    """
    import importlib

    return importlib.import_module(EXAMPLE)


def make_introspector(executor):
    """A real sync introspector wired to *executor*.

    Deliberately the production class: the example's cache claims are about
    :class:`SyncSnowflakeIntrospector`, so mocking the introspector instead
    would test the mock.
    """
    from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
    from rhosocial.activerecord.backend.impl.snowflake.introspection import (
        SyncSnowflakeIntrospector,
    )

    backend = MagicMock()
    backend._version = (8, 32, 0)
    backend.config = MagicMock()
    backend.config.schema = "PUBLIC"
    backend.config.database = "ANALYTICS"
    backend.dialect = SnowflakeDialect(version=(8, 32, 0))
    return SyncSnowflakeIntrospector(backend, executor)


@pytest.fixture
def introspector():
    instrumented = make_introspector(_RecordingExecutor())
    return instrumented, instrumented._executor


@pytest.fixture
def credentials(monkeypatch):
    """A complete, fake credential environment."""
    unset_all(monkeypatch)
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "example-account")
    monkeypatch.setenv("SNOWFLAKE_USER", "example-user")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "example-password")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "ANALYTICS")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
    monkeypatch.setenv("SNOWFLAKE_SCHEMA", "PUBLIC")


def unset_all(monkeypatch):
    for name in clean_env():
        monkeypatch.delenv(name, raising=False)


# ================================================================== #
# Refusing to invent an answer
# ================================================================== #

class TestExampleRefusesWithoutCredentials:
    """With nothing to connect to, it says so and builds nothing."""

    def test_no_credentials_exits_non_zero_and_names_the_variables(
        self, example_module, monkeypatch, capsys
    ):
        unset_all(monkeypatch)
        exit_code = example_module.main([])

        assert exit_code == 2
        captured = capsys.readouterr()
        # The refusal is actionable: every required variable is named, and the
        # two alternatives for authentication are both offered.
        for name in example_module._REQUIRED_SETTINGS:
            assert name in captured.err, name
        assert "SNOWFLAKE_PASSWORD" in captured.err
        assert "SNOWFLAKE_PRIVATE_KEY_PATH" in captured.err
        assert "nothing was queried" in captured.err
        # Nothing was printed as a result, and nothing contacted the network.
        assert captured.out == ""

    def test_partial_credentials_are_refused_too(
        self, example_module, monkeypatch, capsys
    ):
        """An account and a user without a secret is not a session.

        Building a config from half an environment would fail inside the
        driver with a message about the driver; the example refuses before
        that, on the variable that is actually missing.
        """
        unset_all(monkeypatch)
        monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "example-account")
        monkeypatch.setenv("SNOWFLAKE_USER", "example-user")
        monkeypatch.setenv("SNOWFLAKE_DATABASE", "ANALYTICS")
        monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")

        exit_code = example_module.main([])

        assert exit_code == 2
        assert "SNOWFLAKE_PASSWORD (or SNOWFLAKE_PRIVATE_KEY_PATH)" in (
            capsys.readouterr().err
        )

    def test_password_or_key_either_satisfies_the_secret(
        self, example_module, monkeypatch, capsys
    ):
        """A private key stands in for a password, as the config allows."""
        unset_all(monkeypatch)
        monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "example-account")
        monkeypatch.setenv("SNOWFLAKE_USER", "example-user")
        monkeypatch.setenv("SNOWFLAKE_DATABASE", "ANALYTICS")
        monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
        monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY_PATH", "C:/keys/example.p8")

        config = example_module._config_from_env()

        assert config is not None
        assert config.private_key_path == "C:/keys/example.p8"
        assert capsys.readouterr().err == ""

    def test_no_connection_is_attempted_when_refusing(
        self, example_module, monkeypatch
    ):
        """The refusal must happen before the backend object is built.

        Patching the class is the assertion: if the example had constructed a
        backend to ask it about the environment, the patched class would have
        been called and this test would see it.
        """
        unset_all(monkeypatch)
        with patch.object(example_module, "SnowflakeBackend") as backend_cls:
            exit_code = example_module.main([])
        assert exit_code == 2
        backend_cls.assert_not_called()


# ================================================================== #
# The cache demonstration actually demonstrates something
# ================================================================== #

class TestExampleDemonstratesTheCache:
    def test_each_question_is_asked_once_and_cached_once(
        self, example_module, introspector, credentials, capsys
    ):
        instrumented, executor = introspector
        backend = MagicMock()
        backend._connection = object()  # the example disconnects a live one
        backend.introspector = instrumented

        with patch.object(
            example_module, "SnowflakeBackend", return_value=backend
        ):
            exit_code = example_module.main([])

        assert exit_code == 0
        out = capsys.readouterr().out
        # Four sections, one cold statement each and no warm ones.
        assert out.count("cold=1 warm=0") == 4
        assert "Databases" in out
        assert "ANALYTICS" in out
        assert "COMPUTE_WH" in out
        assert "PUBLIC" in out
        # The whole run asked the account five questions: one per section,
        # plus the table listing that picks a table to measure. The second
        # call of every section was served from the cache, which is the claim.
        assert executor.question_count == 5
        # The real executor was handed back, so the example leaves nothing
        # standing between the introspector and the driver.
        assert instrumented._executor is executor

    def test_a_second_run_reports_the_same_counts(
        self, example_module, credentials, capsys
    ):
        """Repeatability: a fresh introspector and a fresh count.

        The point is that the numbers come from the executor rather than from
        a value printed once and copied.
        """
        instrumented = make_introspector(_RecordingExecutor())
        executor = instrumented._executor
        backend = MagicMock()
        backend._connection = None
        backend.introspector = instrumented

        with patch.object(
            example_module, "SnowflakeBackend", return_value=backend
        ):
            example_module.main([])
        assert capsys.readouterr().out.count("cold=1 warm=0") == 4
        assert executor.question_count == 5

    def test_the_requested_table_reports_no_row_when_the_view_is_empty(
        self, example_module, credentials, capsys
    ):
        """``None`` metrics are reported as ambiguous, not as zero bytes.

        The storage view returns no rows for a role other than ACCOUNTADMIN,
        which the view's documentation says is indistinguishable from a missing
        table. The example must print that ambiguity rather than a number.
        """
        silent = _RecordingExecutor(silent=True)
        instrumented = make_introspector(silent)
        backend = MagicMock()
        backend._connection = None
        backend.introspector = instrumented

        with patch.object(
            example_module, "SnowflakeBackend", return_value=backend
        ):
            exit_code = example_module.main(["ORDERS"])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "no metrics row" in out
        assert "may not see the metrics" in out
        assert "active bytes" not in out
        # ``None`` is not cached, so the warm call asked again: an absent
        # answer may become present after a grant, and caching it would make
        # that invisible.
        assert "cold=1 warm=1" in out

    def test_empty_lists_are_reported_as_zero_rows_not_silently(
        self, example_module, credentials, capsys
    ):
        """An account the role sees nothing of prints a count of zero.

        Hiding the sections would look like the example worked when nothing
        was read.
        """
        instrumented = make_introspector(_RecordingExecutor(silent=True))
        backend = MagicMock()
        backend._connection = None
        backend.introspector = instrumented

        with patch.object(
            example_module, "SnowflakeBackend", return_value=backend
        ):
            exit_code = example_module.main([])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "(0 row(s); executor questions cold=1 warm=0)" in out
        assert "No table to measure" in out
