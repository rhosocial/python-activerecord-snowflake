# tests/rhosocial/activerecord_snowflake_test/feature/backend/cli/test_cli_introspect.py
"""Offline black-box tests for the ``introspect`` CLI subcommand.

The real subparser is exercised first: every type ``INTROSPECT_TYPES``
lists must parse, and a type it does not list must be refused. Then each
dispatch branch runs against a fake backend and introspector -- no
connection is opened and no SQL is run -- so the accepted type list and the
implemented branches cannot drift apart.

Output serialisation is checked through the real providers for ``json``,
``csv`` and ``table``; the table path is pinned to its no-``rich`` fallback
so the assertion does not depend on whether the optional dependency is
installed.
"""

import argparse
import csv
import io
import json
from datetime import datetime
from typing import Any, List, Optional

import pytest
from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.introspection.types import IntrospectionViewInfo

from rhosocial.activerecord.backend.impl.snowflake.cli import introspect as cli_introspect
from rhosocial.activerecord.backend.impl.snowflake.cli import output as cli_output
from rhosocial.activerecord.backend.impl.snowflake.introspection import (
    SnowflakeDatabaseInfo,
    SnowflakeTableStorageMetrics,
)

#: The types that act on a named table, so the name is required. ``views``
#: takes an optional view name and is covered separately.
NAME_TYPES = ("columns", "indexes", "foreign-keys", "table-storage-metrics")

#: The types that answer for a whole family (or for the session's context),
#: so a name is refused rather than ignored.
NO_NAME_TYPES = ("tables", "database", "databases", "schemas", "warehouses")


class RecordingProvider:
    """An output provider that records instead of printing."""

    def __init__(self) -> None:
        self.results: List[Any] = []
        self.connection_errors: List[Exception] = []
        self.query_errors: List[Exception] = []

    def display_results(self, data: Any, title: Optional[str] = None) -> None:
        self.results.append((title, data))

    def display_connection_error(self, error: Exception) -> None:
        self.connection_errors.append(error)

    def display_query_error(self, error: Exception) -> None:
        self.query_errors.append(error)


class FakeIntrospector:
    """Every method the CLI branches call, with a recorded call log."""

    def __init__(self) -> None:
        self.calls: List[tuple] = []

    def list_tables(self, schema=None, include_system=False):
        self.calls.append(("tables", schema, include_system))
        return [{"TABLE_NAME": "CUSTOMERS"}]

    def list_views(self, schema=None):
        self.calls.append(("views", schema))
        return [{"TABLE_NAME": "V_CUSTOMERS"}]

    def get_view_info(self, view_name, schema=None):
        self.calls.append(("view-info", view_name, schema))
        if view_name == "missing":
            return None
        return IntrospectionViewInfo(
            name=view_name,
            schema=schema or "PUBLIC",
            definition="SELECT 1",
            is_updatable=True,
        )

    def list_columns(self, name, schema=None):
        self.calls.append(("columns", name, schema))
        return [{"COLUMN_NAME": "ID"}]

    def list_indexes(self, name, schema=None):
        self.calls.append(("indexes", name, schema))
        return [{"CONSTRAINT_NAME": "PK_CUSTOMERS"}]

    def list_foreign_keys(self, name, schema=None):
        self.calls.append(("foreign-keys", name, schema))
        return [{"CONSTRAINT_NAME": "FK_ORDERS"}]

    def get_table_storage_metrics(self, table_name, schema=None):
        self.calls.append(("table-storage-metrics", table_name, schema))
        if table_name == "missing":
            return None
        return SnowflakeTableStorageMetrics(
            table_name=table_name,
            table_catalog="ANALYTICS",
            table_schema=schema or "PUBLIC",
            table_id=1,
            active_bytes=1024,
            time_travel_bytes=16,
            failsafe_bytes=0,
            retained_for_clone_bytes=0,
            row_count=10,
            clustering_key=None,
        )

    def get_database_info(self):
        self.calls.append(("database",))
        return {"name": "ANALYTICS", "version": "8.0.0", "vendor": "Snowflake"}

    def list_databases(self):
        self.calls.append(("databases",))
        return [
            SnowflakeDatabaseInfo(
                name="ANALYTICS",
                created=datetime(2026, 1, 2, 3, 4, 5),
            )
        ]

    def list_schemas(self, database=None):
        self.calls.append(("schemas", database))
        return [{"SCHEMA_NAME": "PUBLIC"}]

    def list_warehouses(self):
        self.calls.append(("warehouses",))
        return [{"name": "COMPUTE_WH"}]


class AsyncFacade:
    """Awaitable twins for the sync introspector methods.

    The async manager keeps the sync method names, so the facade exposes the
    same names and awaits the sync answer.
    """

    def __init__(self, sync: Any) -> None:
        for attr in (
            "list_tables",
            "list_views",
            "get_view_info",
            "list_columns",
            "list_indexes",
            "list_foreign_keys",
            "get_table_storage_metrics",
            "get_database_info",
            "list_databases",
            "list_schemas",
            "list_warehouses",
        ):
            fn = getattr(sync, attr)

            async def call(*a: Any, _fn: Any = fn, **k: Any) -> Any:
                return _fn(*a, **k)

            setattr(self, attr, call)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with the real introspect subparser."""
    top = argparse.ArgumentParser()
    subparsers = top.add_subparsers(dest="command")
    cli_introspect.create_parser(subparsers)
    return top


def patch_sync_backend(
    monkeypatch, introspector: Any, connect_error: Optional[Exception] = None
) -> List[Any]:
    instances: List[Any] = []

    class FakeSyncBackend:
        def __init__(self, connection_config: Any = None) -> None:
            self.connection_config = connection_config
            self.introspector = introspector
            self._connection: Optional[object] = object()
            self.disconnected = False
            instances.append(self)

        def connect(self) -> None:
            if connect_error is not None:
                raise connect_error

        def disconnect(self) -> None:
            self.disconnected = True

    monkeypatch.setattr(cli_introspect, "SnowflakeBackend", FakeSyncBackend)
    monkeypatch.setattr(cli_introspect, "resolve_connection_config_from_args", lambda args: None)
    return instances


def patch_async_backend(monkeypatch, introspector: Any) -> List[Any]:
    instances: List[Any] = []

    class FakeAsyncBackend:
        def __init__(self, connection_config: Any = None) -> None:
            self.connection_config = connection_config
            self.introspector = AsyncFacade(introspector)
            self._connection: Optional[object] = object()
            self.disconnected = False
            instances.append(self)

        async def connect(self) -> None:
            pass

        async def disconnect(self) -> None:
            self.disconnected = True

    monkeypatch.setattr(cli_introspect, "AsyncSnowflakeBackend", FakeAsyncBackend)
    monkeypatch.setattr(cli_introspect, "resolve_connection_config_from_args", lambda args: None)
    return instances


@pytest.fixture
def provider(monkeypatch) -> RecordingProvider:
    rec = RecordingProvider()
    monkeypatch.setattr(cli_introspect, "create_provider", lambda fmt, ascii_borders=False: rec)
    return rec


# ================================================================== #
# Argument parsing
# ================================================================== #


class TestIntrospectParserContract:
    def test_defaults(self):
        args = build_parser().parse_args(["introspect", "tables", "--account", "acct"])
        assert args.type == "tables"
        assert args.name is None
        assert args.include_system is False
        assert args.output == "table"
        assert args.use_async is False

    def test_name_and_flags(self):
        args = build_parser().parse_args(
            [
                "introspect",
                "columns",
                "customers",
                "--include-system",
                "-o",
                "json",
            ]
        )
        assert args.type == "columns"
        assert args.name == "customers"
        assert args.include_system is True
        assert args.output == "json"

    def test_every_listed_type_is_accepted(self):
        for itype in cli_introspect.INTROSPECT_TYPES:
            args = build_parser().parse_args(["introspect", itype, "--account", "acct"])
            assert args.type == itype

    def test_the_advertised_types_are_the_capability_mapping(self):
        """One source for the list: the mapping, not a second hand-written copy.

        The list used to be written out separately from the capability
        switches, so a type could be advertised while its family was not.
        """
        assert list(cli_introspect._TYPE_CAPABILITIES) == cli_introspect.INTROSPECT_TYPES

    def test_every_type_names_a_switch_the_dialect_has(self):
        """A type whose switch does not exist would be un-gated, not gated."""
        from rhosocial.activerecord.backend.impl.snowflake.dialect import (
            SnowflakeDialect,
        )

        dialect = SnowflakeDialect()
        missing = [
            (cli_type, switch)
            for cli_type, switch in cli_introspect._TYPE_CAPABILITIES.items()
            if not hasattr(dialect, switch)
        ]
        assert missing == []

    def test_a_type_that_is_not_listed_is_refused(self):
        """``table`` was the removed aggregate and is not a type anymore."""
        with pytest.raises(SystemExit):
            build_parser().parse_args(["introspect", "table", "customers", "--account", "acct"])

    def test_help_lists_every_type_and_no_removed_aggregate(self, capsys):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["introspect", "--help"])
        out = capsys.readouterr().out
        for itype in cli_introspect.INTROSPECT_TYPES:
            assert itype in out
        assert "table users" not in out

    def test_connection_arguments_flow_through(self):
        args = build_parser().parse_args(
            [
                "introspect",
                "tables",
                "--account",
                "acct",
                "--database",
                "ANALYTICS",
                "--schema",
                "PUBLIC",
                "--warehouse",
                "WH",
                "--role",
                "SYSADMIN",
                "--user",
                "u",
                "--password",
                "p",
            ]
        )
        assert (args.account, args.database) == ("acct", "ANALYTICS")
        assert (args.schema, args.warehouse, args.role) == (
            "PUBLIC",
            "WH",
            "SYSADMIN",
        )
        assert (args.user, args.password) == ("u", "p")


# ================================================================== #
# Synchronous dispatch
# ================================================================== #


class TestIntrospectSyncDispatch:
    @pytest.mark.parametrize(
        "itype,name,title",
        [
            ("tables", None, "Tables"),
            ("views", None, "Views"),
            ("views", "v_customers", "View v_customers"),
            ("columns", "customers", "Columns of customers"),
            ("indexes", "customers", "Indexes of customers"),
            ("foreign-keys", "orders", "Foreign Keys of orders"),
            (
                "table-storage-metrics",
                "orders",
                "Storage Metrics of orders",
            ),
            ("database", None, "Database Info"),
            ("databases", None, "Databases"),
            ("schemas", None, "Schemas"),
            ("warehouses", None, "Warehouses"),
        ],
    )
    def test_every_type_reaches_a_branch(self, provider, monkeypatch, itype, name, title):
        patch_sync_backend(monkeypatch, FakeIntrospector())
        argv = ["introspect", itype, "--account", "acct"]
        if name:
            argv.insert(2, name)
        cli_introspect.handle(build_parser().parse_args(argv))

        assert [t for t, _ in provider.results] == [title]

    def test_tables_passes_include_system(self, provider, monkeypatch):
        insp = FakeIntrospector()
        patch_sync_backend(monkeypatch, insp)
        cli_introspect.handle(
            build_parser().parse_args(
                ["introspect", "tables", "--account", "acct", "--include-system"]
            )
        )
        assert insp.calls[-1] == ("tables", None, True)

    def test_schemas_passes_the_database_flag(self, provider, monkeypatch):
        insp = FakeIntrospector()
        patch_sync_backend(monkeypatch, insp)
        cli_introspect.handle(
            build_parser().parse_args(
                [
                    "introspect",
                    "schemas",
                    "--account",
                    "acct",
                    "--database",
                    "ANALYTICS",
                ]
            )
        )
        assert insp.calls[-1] == ("schemas", "ANALYTICS")

    @pytest.mark.parametrize("itype", NAME_TYPES)
    def test_missing_name_exits_nonzero(self, provider, capsys, monkeypatch, itype):
        patch_sync_backend(monkeypatch, FakeIntrospector())
        with pytest.raises(SystemExit) as excinfo:
            cli_introspect.handle(
                build_parser().parse_args(["introspect", itype, "--account", "acct"])
            )
        assert excinfo.value.code == 1
        assert "Table name is required" in capsys.readouterr().err

    def test_a_named_view_asks_for_that_view(self, provider, monkeypatch):
        insp = FakeIntrospector()
        patch_sync_backend(monkeypatch, insp)
        cli_introspect.handle(
            build_parser().parse_args(["introspect", "views", "v_customers", "--account", "acct"])
        )
        assert insp.calls[-1] == ("view-info", "v_customers", None)
        title, rows = provider.results[0]
        assert title == "View v_customers"
        assert rows[0]["name"] == "v_customers"

    def test_a_named_view_that_is_not_there_exits_one(self, provider, capsys, monkeypatch):
        patch_sync_backend(monkeypatch, FakeIntrospector())
        with pytest.raises(SystemExit) as excinfo:
            cli_introspect.handle(
                build_parser().parse_args(["introspect", "views", "missing", "--account", "acct"])
            )
        assert excinfo.value.code == 1
        assert "View 'missing' not found" in capsys.readouterr().err

    def test_storage_metrics_without_a_row_exits_one(self, provider, capsys, monkeypatch):
        """``None`` is "no metrics row", not "no such table"."""
        patch_sync_backend(monkeypatch, FakeIntrospector())
        with pytest.raises(SystemExit) as excinfo:
            cli_introspect.handle(
                build_parser().parse_args(
                    [
                        "introspect",
                        "table-storage-metrics",
                        "missing",
                        "--account",
                        "acct",
                    ]
                )
            )
        assert excinfo.value.code == 1
        assert "has no storage metrics" in capsys.readouterr().err
        assert provider.results == []

    def test_storage_metrics_answers_with_the_metrics_row(self, provider, monkeypatch):
        patch_sync_backend(monkeypatch, FakeIntrospector())
        cli_introspect.handle(
            build_parser().parse_args(
                ["introspect", "table-storage-metrics", "orders", "--account", "acct"]
            )
        )
        title, rows = provider.results[0]
        assert title == "Storage Metrics of orders"
        assert rows[0]["active_bytes"] == 1024
        assert rows[0]["row_count"] == 10

    @pytest.mark.parametrize("itype", NO_NAME_TYPES)
    def test_a_name_on_a_family_type_is_refused(self, provider, capsys, monkeypatch, itype):
        """Exit 2: the pair does not exist, not a runtime failure."""
        patch_sync_backend(monkeypatch, FakeIntrospector())
        with pytest.raises(SystemExit) as excinfo:
            cli_introspect.handle(
                build_parser().parse_args(["introspect", itype, "analytics", "--account", "acct"])
            )
        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "takes no name" in err
        assert "analytics" in err
        assert provider.results == []

    def test_database_branch_wraps_one_row(self, provider, monkeypatch):
        patch_sync_backend(monkeypatch, FakeIntrospector())
        cli_introspect.handle(
            build_parser().parse_args(["introspect", "database", "--account", "acct"])
        )
        title, rows = provider.results[0]
        assert title == "Database Info"
        assert rows[0]["name"] == "ANALYTICS"
        assert rows[0]["vendor"] == "Snowflake"

    def test_connection_is_required(self, capsys, monkeypatch):
        monkeypatch.delenv("SNOWFLAKE_ACCOUNT", raising=False)
        monkeypatch.delenv("SNOWFLAKE_DATABASE", raising=False)
        patch_sync_backend(monkeypatch, FakeIntrospector())
        with pytest.raises(SystemExit) as excinfo:
            cli_introspect.handle(build_parser().parse_args(["introspect", "tables"]))
        assert excinfo.value.code == 1
        assert "--account and/or --database" in capsys.readouterr().err

    def test_connection_error_exits_nonzero(self, provider, monkeypatch):
        patch_sync_backend(
            monkeypatch,
            FakeIntrospector(),
            connect_error=ConnectionError("390100"),
        )
        with pytest.raises(SystemExit) as excinfo:
            cli_introspect.handle(
                build_parser().parse_args(["introspect", "tables", "--account", "acct"])
            )
        assert excinfo.value.code == 1
        assert provider.connection_errors

    def test_query_error_exits_nonzero(self, provider, monkeypatch):
        class Exploding(FakeIntrospector):
            def list_tables(self, schema=None, include_system=False):
                raise QueryError("002003")

        patch_sync_backend(monkeypatch, Exploding())
        with pytest.raises(SystemExit) as excinfo:
            cli_introspect.handle(
                build_parser().parse_args(["introspect", "tables", "--account", "acct"])
            )
        assert excinfo.value.code == 1
        assert provider.query_errors

    def test_unexpected_error_writes_stderr(self, capsys, provider, monkeypatch):
        class Exploding(FakeIntrospector):
            def list_tables(self, schema=None, include_system=False):
                raise RuntimeError("boom")

        patch_sync_backend(monkeypatch, Exploding())
        with pytest.raises(SystemExit) as excinfo:
            cli_introspect.handle(
                build_parser().parse_args(["introspect", "tables", "--account", "acct"])
            )
        assert excinfo.value.code == 1
        assert "Error during introspection" in capsys.readouterr().err


# ================================================================== #
# Asynchronous dispatch
# ================================================================== #


class TestIntrospectAsyncDispatch:
    @pytest.mark.parametrize(
        "itype,name,title",
        [
            ("tables", None, "Tables"),
            ("views", None, "Views"),
            ("views", "v_customers", "View v_customers"),
            ("columns", "customers", "Columns of customers"),
            ("indexes", "customers", "Indexes of customers"),
            ("foreign-keys", "orders", "Foreign Keys of orders"),
            (
                "table-storage-metrics",
                "orders",
                "Storage Metrics of orders",
            ),
            ("database", None, "Database Info"),
            ("databases", None, "Databases"),
            ("schemas", None, "Schemas"),
            ("warehouses", None, "Warehouses"),
        ],
    )
    def test_every_type_reaches_a_branch(self, provider, monkeypatch, itype, name, title):
        patch_async_backend(monkeypatch, FakeIntrospector())
        argv = ["introspect", itype, "--account", "acct", "--use-async"]
        if name:
            argv.insert(2, name)
        cli_introspect.handle(build_parser().parse_args(argv))

        assert [t for t, _ in provider.results] == [title]


# ================================================================== #
# Output serialisation, through the real providers
# ================================================================== #


class TestIntrospectOutput:
    def run_handle(self, monkeypatch, argv):
        patch_sync_backend(monkeypatch, FakeIntrospector())
        cli_introspect.handle(build_parser().parse_args(argv))

    def test_json_output_is_the_serialised_rows(self, capsys, monkeypatch):
        self.run_handle(
            monkeypatch,
            ["introspect", "databases", "--account", "acct", "-o", "json"],
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["name"] == "ANALYTICS"
        assert payload[0]["created"] == "2026-01-02 03:04:05"

    def test_csv_output_is_the_serialised_rows(self, capsys, monkeypatch):
        self.run_handle(
            monkeypatch,
            ["introspect", "databases", "--account", "acct", "-o", "csv"],
        )
        reader = csv.DictReader(io.StringIO(capsys.readouterr().out))
        [row] = list(reader)
        assert row["name"] == "ANALYTICS"
        assert row["created"] == "2026-01-02 03:04:05"

    def test_table_output_falls_back_to_json_without_rich(self, capsys, monkeypatch):
        monkeypatch.setattr(cli_output, "RICH_AVAILABLE", False)
        self.run_handle(
            monkeypatch,
            ["introspect", "databases", "--account", "acct", "-o", "table"],
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["name"] == "ANALYTICS"
