# src/rhosocial/activerecord/backend/impl/snowflake/cli/introspect.py
"""introspect subcommand - Database introspection."""

import argparse
import asyncio
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.backend.async_backend import AsyncSnowflakeBackend
from rhosocial.activerecord.backend.errors import ConnectionError, QueryError

from .connection import add_connection_args, resolve_connection_config_from_args
from .output import create_provider

OUTPUT_CHOICES = ['table', 'json', 'csv', 'tsv']

INTROSPECT_TYPES = [
    "tables", "views", "columns",
    "indexes", "foreign-keys", "database",
    "databases", "schemas", "warehouses",
]
# Note: "triggers" is intentionally excluded because Snowflake does not support triggers.


def create_parser(subparsers):
    """Create the introspect subcommand parser."""
    parser = subparsers.add_parser(
        'introspect',
        help='Database introspection',
        epilog="""Examples:
  # List all tables in schema
  %(prog)s tables --account myaccount --database mydb

  # List all views
  %(prog)s views --account myaccount --database mydb

  # Get column details, indexes and foreign keys for a table
  %(prog)s columns users --account myaccount --database mydb
  %(prog)s indexes users --account myaccount --database mydb
  %(prog)s foreign-keys users --account myaccount --database mydb

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
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '-o', '--output',
        choices=OUTPUT_CHOICES,
        default='table',
        help='Output format (default: table)',
    )

    add_connection_args(parser)

    parser.add_argument(
        '--rich-ascii',
        action='store_true',
        help='Use ASCII characters for rich table borders.',
    )

    parser.add_argument(
        "type",
        choices=INTROSPECT_TYPES,
        help=(
            "Introspection type: tables, views, columns, indexes, "
            "foreign-keys, database, databases, schemas, warehouses"
        ),
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
    if hasattr(obj, 'model_dump'):
        try:
            result = obj.model_dump(mode='json')
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

        introspector = backend.introspector

        if args.type == "tables":
            tables = introspector.list_tables(
                schema=None,
                include_system=args.include_system
            )
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
                print("Error: Table name is required for 'foreign-keys' introspection", file=sys.stderr)
                sys.exit(1)
            fks = introspector.list_foreign_keys(args.name, schema=None)
            data = _serialize_for_output(fks)
            provider.display_results(data, title=f"Foreign Keys of {args.name}")

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
            tables = await introspector.list_tables(
                schema=None,
                include_system=args.include_system
            )
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
                print("Error: Table name is required for 'foreign-keys' introspection", file=sys.stderr)
                sys.exit(1)
            fks = await introspector.list_foreign_keys(args.name, schema=None)
            data = _serialize_for_output(fks)
            provider.display_results(data, title=f"Foreign Keys of {args.name}")

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
