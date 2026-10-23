# tests/rhosocial/activerecord_snowflake_test/feature/backend/cli/test_introspect_account_objects.py
"""CLI dispatch for ``databases`` / ``schemas`` / ``warehouses``.

The backend is mocked: these tests assert that the parsed subcommand reaches
the right introspector method with the right argument and that the serialized
rows reach the output provider. No connection is opened and no SQL is run.
"""
import argparse
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhosocial.activerecord.backend.impl.snowflake.cli import introspect
from rhosocial.activerecord.backend.impl.snowflake.introspection import (
    SnowflakeDatabaseInfo,
    SnowflakeSchemaInfo,
    SnowflakeWarehouseInfo,
)


def parse(argv):
    """Parse *argv* through the real introspect subparser."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    introspect.create_parser(subparsers)
    return parser.parse_args(argv)


# ================================================================== #
# Argument parsing
# ================================================================== #

class TestIntrospectAccountObjectArguments:
    @pytest.mark.parametrize(
        "type_name", ["databases", "schemas", "warehouses"]
    )
    def test_account_object_types_are_accepted(self, type_name):
        assert type_name in introspect.INTROSPECT_TYPES
        args = parse(["introspect", type_name, "--account", "acct"])
        assert args.type == type_name
        assert args.use_async is False

    def test_schemas_takes_database_from_the_connection_flag(self):
        args = parse(
            [
                "introspect",
                "schemas",
                "--account",
                "acct",
                "--database",
                "ANALYTICS",
                "-o",
                "json",
            ]
        )
        assert args.database == "ANALYTICS"
        assert args.output == "json"
        assert args.name is None

    def test_databases_does_not_require_a_name(self):
        args = parse(["introspect", "databases", "--account", "acct"])
        assert args.name is None


# ================================================================== #
# Synchronous dispatch
# ================================================================== #

class TestSyncIntrospectDispatch:
    def run_handle(self, argv, introspector):
        args = parse(argv)
        with patch.object(
            introspect,
            "resolve_connection_config_from_args",
            return_value=MagicMock(),
        ), patch.object(introspect, "SnowflakeBackend") as backend_cls, \
                patch.object(introspect, "create_provider") as provider_factory:
            backend = backend_cls.return_value
            backend.introspector = introspector
            provider = provider_factory.return_value
            introspect.handle(args)
        return backend, provider

    def test_databases_reaches_list_databases(self):
        introspector = MagicMock()
        introspector.list_databases.return_value = [
            SnowflakeDatabaseInfo(
                name="ANALYTICS",
                owner="SYSADMIN",
                is_transient=False,
                retention_time=1,
                database_type="STANDARD",
                owner_role_type="ROLE",
                created=datetime(2026, 1, 2, 3, 4, 5),
            )
        ]
        backend, provider = self.run_handle(
            ["introspect", "databases", "--account", "acct"], introspector
        )

        backend.connect.assert_called_once_with()
        introspector.list_databases.assert_called_once_with()
        provider.display_results.assert_called_once_with(
            [
                {
                    "name": "ANALYTICS",
                    "owner": "SYSADMIN",
                    "is_transient": False,
                    "comment": None,
                    "created": "2026-01-02 03:04:05",
                    "last_altered": None,
                    "retention_time": 1,
                    "database_type": "STANDARD",
                    "owner_role_type": "ROLE",
                }
            ],
            title="Databases",
        )

    def test_schemas_reaches_list_schemas_with_database(self):
        introspector = MagicMock()
        introspector.list_schemas.return_value = [
            SnowflakeSchemaInfo(
                name="PUBLIC",
                catalog_name="ANALYTICS",
                is_managed_access=True,
            )
        ]
        _, provider = self.run_handle(
            [
                "introspect",
                "schemas",
                "--account",
                "acct",
                "--database",
                "ANALYTICS",
            ],
            introspector,
        )

        introspector.list_schemas.assert_called_once_with(
            database="ANALYTICS"
        )
        [payload] = provider.display_results.call_args.args[0]
        assert payload["name"] == "PUBLIC"
        assert payload["catalog_name"] == "ANALYTICS"
        assert payload["is_managed_access"] is True
        assert provider.display_results.call_args.kwargs == {"title": "Schemas"}

    def test_warehouses_reaches_list_warehouses(self):
        introspector = MagicMock()
        introspector.list_warehouses.return_value = [
            SnowflakeWarehouseInfo(
                name="COMPUTE_WH",
                state="STARTED",
                size="X-Small",
                is_current=True,
            )
        ]
        _, provider = self.run_handle(
            ["introspect", "warehouses", "--account", "acct"], introspector
        )

        introspector.list_warehouses.assert_called_once_with()
        [payload] = provider.display_results.call_args.args[0]
        assert payload["name"] == "COMPUTE_WH"
        assert payload["is_current"] is True
        assert provider.display_results.call_args.kwargs == {
            "title": "Warehouses"
        }


# ================================================================== #
# Asynchronous dispatch
# ================================================================== #

class TestAsyncIntrospectDispatch:
    async def test_async_warehouses_reaches_list_warehouses(self):
        args = parse(
            ["introspect", "warehouses", "--account", "acct", "--use-async"]
        )
        backend = MagicMock()
        backend._connection = None
        backend.connect = AsyncMock()
        backend.introspector.list_warehouses = AsyncMock(
            return_value=[SnowflakeWarehouseInfo(name="COMPUTE_WH")]
        )
        provider = MagicMock()

        await introspect._handle_introspect_async(args, backend, provider)

        backend.connect.assert_awaited_once_with()
        backend.introspector.list_warehouses.assert_awaited_once_with()
        provider.display_results.assert_called_once()
        [payload] = provider.display_results.call_args.args[0]
        assert payload["name"] == "COMPUTE_WH"

    async def test_async_databases_reaches_list_databases(self):
        args = parse(
            ["introspect", "databases", "--account", "acct", "--use-async"]
        )
        backend = MagicMock()
        backend._connection = None
        backend.connect = AsyncMock()
        backend.introspector.list_databases = AsyncMock(
            return_value=[SnowflakeDatabaseInfo(name="ANALYTICS")]
        )
        provider = MagicMock()

        await introspect._handle_introspect_async(args, backend, provider)

        backend.introspector.list_databases.assert_awaited_once_with()
        assert provider.display_results.call_args.kwargs == {
            "title": "Databases"
        }
