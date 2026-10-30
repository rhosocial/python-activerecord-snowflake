# src/rhosocial/activerecord/backend/impl/snowflake/cli/introspect.py
"""introspect subcommand - Database introspection."""

import argparse
import asyncio
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError

from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.backend.async_backend import (
    AsyncSnowflakeBackend,
)

from .connection import add_connection_args, resolve_connection_config_from_args
from .output import create_provider

OUTPUT_CHOICES = ["table", "json", "csv", "tsv"]

#: CLI type -> the dialect capability switch that answers for it.
#:
#: The advertised list is derived from this mapping, so a family cannot be
#: answerable and unaskable at the same time -- adding a type here without
#: naming its switch is the only way to get a type, and the tests refuse one
#: whose switch the dialect does not have. Every switch here is a constant on
#: this dialect (Snowflake's introspection answers do not vary by server
#: version), so the mapping constrains what can be asked rather than refusing
#: at runtime; it is still consulted, so that a dialect declaring a family
#: unsupported is answered with "not supported here" instead of an empty list.
_TYPE_CAPABILITIES = {
    "tables": "supports_table_introspection",
    "views": "supports_view_introspection",
    "columns": "supports_column_introspection",
    "indexes": "supports_index_introspection",
    "foreign-keys": "supports_foreign_key_introspection",
    "database": "supports_database_info",
    "databases": "supports_database_introspection",
    "schemas": "supports_schema_introspection",
    "warehouses": "supports_warehouse_introspection",
    "table-storage-metrics": "supports_table_storage_metrics",
}

INTROSPECT_TYPES = list(_TYPE_CAPABILITIES)

# Note: "triggers" is intentionally excluded because Snowflake does not
# support triggers -- the engine has no such object, so there is no question
# to ask. "partition-metadata" is excluded for a different reason: the dialect
# has a formatter for it, but no introspector method reads it, so there is no
# answer behind the type.


def _require_capability(backend, args) -> None:
    """Refuse a type the connected dialect says it cannot answer.

    Exit code 2, not 1: the request is well formed and the connection is
    fine -- this server simply has no answer to it. Every Snowflake switch
    is a constant today, so this refuses nothing in practice; it is the
    runtime half of :data:`_TYPE_CAPABILITIES`, and what keeps a future
    switch that starts answering ``False`` from being ignored.
    """
    switch = _TYPE_CAPABILITIES.get(args.type)
    if switch is None:
        return
    dialect = getattr(backend, "dialect", None)
    if dialect is None:
        # A stub standing in for the backend (the offline CLI tests) has no
        # dialect to ask; a real one always does.
        return
    supported = getattr(dialect, switch, None)
    if supported is None or supported():
        return
    print(
        f"Error: {args.type} introspection is not supported by this server",
        file=sys.stderr,
    )
    sys.exit(2)


def create_parser(subparsers):
    """Create the introspect subcommand parser."""
    parser = subparsers.add_parser(
        "introspect",
        help="Database introspection",
        epilog="""Examples:
  # List all tables in schema
  %(prog)s tables --account myaccount --database mydb

  # List all views
  %(prog)s views --account myaccount --database mydb

  # Get column details, indexes and foreign keys for a table
  %(prog)s columns users --account myaccount --database mydb
  %(prog)s indexes users --account myaccount --database mydb
  %(prog)s foreign-keys users --account myaccount --database mydb

  # One table's billed storage: active, time travel, failsafe and
  # clone-retained bytes, with its row count and clustering key
  %(prog)s table-storage-metrics users --account myaccount --database mydb

  # List the databases visible to the role, the schemas of a database,
  # and the virtual warehouses
  %(prog)s databases --account myaccount
  %(prog)s schemas --account myaccount --database mydb
  %(prog)s warehouses --account myaccount

  # Output as JSON
  %(prog)s tables --account myaccount --database mydb -o json

  # Using environment variables for connection
  export SNOWFLAKE_ACCOUNT=myaccount SNOWFLAKE_DATABASE=mydb SNOWFLAKE_USER=admin SNOWFLAKE_PASSWORD=secret
  %(prog)s tables

An empty table-storage-metrics answer is not a missing table. The view behind
it returns no rows for roles other than ACCOUNTADMIN, and the introspector
cannot tell "the table is gone" from "your role cannot see its metrics", so
both exit 1 with the same message.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-o",
        "--output",
        choices=OUTPUT_CHOICES,
        default="table",
        help="Output format (default: table)",
    )

    add_connection_args(parser)

    parser.add_argument(
        "--rich-ascii",
        action="store_true",
        help="Use ASCII characters for rich table borders.",
    )

    parser.add_argument(
        "type",
        choices=INTROSPECT_TYPES,
        help="Introspection type: " + ", ".join(INTROSPECT_TYPES),
    )
    parser.add_argument(
        "name",
        nargs="?",
        default=None,
        help="Table/view name (required for some types)",
    )
    parser.add_argument(
        "--include-system",
        action="store_true",
        help="Include system tables in output",
    )

    return parser


def handle(args):
    """Handle the introspect subcommand."""
    provider = create_provider(args.output, ascii_borders=args.rich_ascii)

    if not args.account and not args.database:
        print("Error: --account and/or --database is required for introspection", file=sys.stderr)
        sys.exit(1)

    config = resolve_connection_config_from_args(args)

    if args.use_async:
        backend = AsyncSnowflakeBackend(connection_config=config)
        asyncio.run(_handle_introspect_async(args, backend, provider))
    else:
        backend = SnowflakeBackend(connection_config=config)
        _handle_introspect_sync(args, backend, provider)


# ---------------------------------------------------------------------------
# Internal helper functions
# ---------------------------------------------------------------------------


def _serialize_for_output(obj: Any) -> Any:
    """Serialize object for JSON output, handling non-serializable types."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        try:
            result = obj.model_dump(mode="json")
            return _serialize_for_output(result)
        except TypeError:
            result = obj.model_dump()
            return _serialize_for_output(result)
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize_for_output(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _serialize_for_output(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_output(item) for item in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def _handle_introspect_sync(args, backend: SnowflakeBackend, provider):
    """Handle introspect subcommand synchronously."""
    try:
        backend.connect()

        _require_capability(backend, args)

        introspector = backend.introspector

        if args.type == "tables":
            tables = introspector.list_tables(schema=None, include_system=args.include_system)
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
            views = introspector.list_views(schema=None)
            data = _serialize_for_output(views)
            provider.display_results(data, title="Views")

        elif args.type == "columns":
            if not args.name:
                print("Error: Table name is required for 'columns' introspection", file=sys.stderr)
                sys.exit(1)
            columns = introspector.list_columns(args.name, schema=None)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")

        elif args.type == "indexes":
            if not args.name:
                print("Error: Table name is required for 'indexes' introspection", file=sys.stderr)
                sys.exit(1)
            indexes = introspector.list_indexes(args.name, schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title=f"Indexes of {args.name}")

        elif args.type == "foreign-keys":
            if not args.name:
                print(
                    "Error: Table name is required for 'foreign-keys' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            fks = introspector.list_foreign_keys(args.name, schema=None)
            data = _serialize_for_output(fks)
            provider.display_results(data, title=f"Foreign Keys of {args.name}")

        elif args.type == "table-storage-metrics":
            if not args.name:
                print(
                    "Error: Table name is required for 'table-storage-metrics' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            metrics = introspector.get_table_storage_metrics(args.name, schema=None)
            if metrics is None:
                # None means "no metrics row", which is not "no table": the
                # view returns no rows for roles other than ACCOUNTADMIN, so
                # an absent answer cannot be read as a missing object.
                print(
                    f"Error: Table '{args.name}' has no storage metrics",
                    file=sys.stderr,
                )
                sys.exit(1)
            provider.display_results(
                _serialize_for_output([metrics]),
                title=f"Storage Metrics of {args.name}",
            )

        elif args.type == "database":
            info = introspector.get_database_info()
            data = _serialize_for_output(info)
            provider.display_results([data], title="Database Info")

        elif args.type == "databases":
            databases = introspector.list_databases()
            data = _serialize_for_output(databases)
            provider.display_results(data, title="Databases")

        elif args.type == "schemas":
            # SCHEMATA is a database-level view: --database names the
            # database to enumerate, or None for the session's current one.
            schemas = introspector.list_schemas(database=args.database)
            data = _serialize_for_output(schemas)
            provider.display_results(data, title="Schemas")

        elif args.type == "warehouses":
            warehouses = introspector.list_warehouses()
            data = _serialize_for_output(warehouses)
            provider.display_results(data, title="Warehouses")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during introspection: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:
            backend.disconnect()


async def _handle_introspect_async(args, backend: AsyncSnowflakeBackend, provider):
    """Handle introspect subcommand asynchronously."""
    try:
        await backend.connect()

        introspector = backend.introspector

        if args.type == "tables":
            tables = await introspector.list_tables(schema=None, include_system=args.include_system)
            data = _serialize_for_output(tables)
            provider.display_results(data, title="Tables")

        elif args.type == "views":
            views = await introspector.list_views(schema=None)
            data = _serialize_for_output(views)
            provider.display_results(data, title="Views")

        elif args.type == "columns":
            if not args.name:
                print("Error: Table name is required for 'columns' introspection", file=sys.stderr)
                sys.exit(1)
            columns = await introspector.list_columns(args.name, schema=None)
            data = _serialize_for_output(columns)
            provider.display_results(data, title=f"Columns of {args.name}")

        elif args.type == "indexes":
            if not args.name:
                print("Error: Table name is required for 'indexes' introspection", file=sys.stderr)
                sys.exit(1)
            indexes = await introspector.list_indexes(args.name, schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title=f"Indexes of {args.name}")

        elif args.type == "foreign-keys":
            if not args.name:
                print(
                    "Error: Table name is required for 'foreign-keys' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            fks = await introspector.list_foreign_keys(args.name, schema=None)
            data = _serialize_for_output(fks)
            provider.display_results(data, title=f"Foreign Keys of {args.name}")

        elif args.type == "table-storage-metrics":
            if not args.name:
                print(
                    "Error: Table name is required for 'table-storage-metrics' introspection",
                    file=sys.stderr,
                )
                sys.exit(1)
            metrics = await introspector.get_table_storage_metrics(args.name, schema=None)
            if metrics is None:
                # Same reading as the sync handler: an absent row is "no
                # metrics for this role", not "no such table".
                print(
                    f"Error: Table '{args.name}' has no storage metrics",
                    file=sys.stderr,
                )
                sys.exit(1)
            provider.display_results(
                _serialize_for_output([metrics]),
                title=f"Storage Metrics of {args.name}",
            )

        elif args.type == "database":
            info = await introspector.get_database_info()
            data = _serialize_for_output(info)
            provider.display_results([data], title="Database Info")

        elif args.type == "databases":
            databases = await introspector.list_databases()
            data = _serialize_for_output(databases)
            provider.display_results(data, title="Databases")

        elif args.type == "schemas":
            # SCHEMATA is a database-level view: --database names the
            # database to enumerate, or None for the session's current one.
            schemas = await introspector.list_schemas(database=args.database)
            data = _serialize_for_output(schemas)
            provider.display_results(data, title="Schemas")

        elif args.type == "warehouses":
            warehouses = await introspector.list_warehouses()
            data = _serialize_for_output(warehouses)
            provider.display_results(data, title="Warehouses")

    except ConnectionError as e:
        provider.display_connection_error(e)
        sys.exit(1)
    except QueryError as e:
        provider.display_query_error(e)
        sys.exit(1)
    except Exception as e:
        print(f"Error during introspection: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend._connection:
            await backend.disconnect()
