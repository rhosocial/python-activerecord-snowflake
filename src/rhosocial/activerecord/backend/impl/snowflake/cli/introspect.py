# src/rhosocial/activerecord/backend/impl/snowflake/cli/introspect.py
"""introspect subcommand - Database introspection.

Every family the dialect declares it can answer is offered here, and the
advertised list is derived from :data:`_TYPE_CAPABILITIES` rather than written
a second time -- so a family cannot be answerable and unaskable at once. The
three families that read the rows themselves (data profiles, value samples,
join coverage) are offered because the dialect answers them by aggregating; the
six that a catalogue or a statistics collector answers elsewhere are offered
too, and the switch that names them is what decides at runtime, because the
*server* in front of us may not have what the switch describes.

A NAME or a flag the type has no question for is refused (exit 2) rather than
dropped, and a required one that is missing exits 1. A probe that answers
``None`` is reported as "cannot be measured", because an empty row would read as
a measured zero.
"""

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

#: How many values ``value-samples`` lists when ``--limit`` is not given. The
#: introspector's own default, restated because the parser has to say what it
#: will send when the flag is absent.
DEFAULT_VALUE_SAMPLE_LIMIT = 100

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
    # ---- the operational families ----
    # Index usage, table counters, runtime facts and the dependency graph are
    # each a listing over the connection's scope, so none takes a NAME --
    # ``dependencies`` may be narrowed to one object but answers the whole graph
    # without one. These read a statistics collector or a catalogue rather than
    # the schema structure, which is why they are separate types and not
    # columns on ``tables``.
    "unused-indexes": "supports_unused_indexes_detection",
    "table-stats": "supports_table_stats",
    "runtime": "supports_runtime_stats",
    "index-stats": "supports_index_stats",
    "dependencies": "supports_object_dependencies",
    # ---- the one-object families ----
    # The DDL that recreates a named table, the profiles of one table and the
    # samples of one of its columns. The dialect answers these by aggregating
    # the rows themselves, so every figure is exact and paid for in time.
    "ddl": "supports_ddl_extraction",
    "column-profiles": "supports_column_data_profile",
    "value-samples": "supports_column_value_sample",
    "join-coverage": "supports_join_coverage",
}

INTROSPECT_TYPES = list(_TYPE_CAPABILITIES)

# Note: "triggers" is intentionally excluded because Snowflake does not
# support triggers -- the engine has no such object, so there is no question
# to ask. "partition-metadata" is excluded for a different reason: the dialect
# has a formatter for it, but no introspector method reads it, so there is no
# answer behind the type.

#: Types that answer for a whole family (or for the session's context), not
#: for one named object. A NAME given to one of them is refused rather than
#: ignored: the parser accepts the positional for the types that need it, so
#: silently dropping it would claim a filtering the command never performed.
_NO_NAME_TYPES = (
    "tables",
    "database",
    "databases",
    "schemas",
    "warehouses",
    # The operational families describe the connection's scope rather than
    # one object, so a NAME is refused for the same reason as ``tables``:
    # ``introspect unused-indexes orders`` would read as a narrowing the
    # question has no way to express. ``dependencies`` is *not* in this
    # tuple -- a name there narrows the graph, which is a real answer.
    "unused-indexes",
    "table-stats",
    "runtime",
    "index-stats",
)

#: Types that ask about one table and cannot be answered without its NAME.
#: A missing NAME is an incomplete invocation (exit 1), while a NAME a type
#: cannot use is a request this command declines (exit 2) -- see
#: :func:`_refuse_name`. Keeping the two apart is what lets a caller tell a
#: typo from a misfiled question.
_TABLE_NAME_TYPES = (
    "columns",
    "indexes",
    "foreign-keys",
    "table-storage-metrics",
    # The one-object families: the DDL that recreates one table, the profiles
    # of its columns, and the samples of one of them.
    "ddl",
    "column-profiles",
    "value-samples",
    # ``join-coverage`` asks about two tables: the left one is NAME, the
    # right one is a flag, so the left is required here too.
    "join-coverage",
)

#: Options whose meaning depends on the type, and whether they must be given.
#:
#: ``--column`` is read by ``value-samples`` (which column to sample) and by
#: ``join-coverage`` (the left column); the two join flags are read only by
#: ``join-coverage``. A flag supplied to a type that does not read it is
#: refused rather than ignored, for the same reason a NAME nothing reads is:
#: a silently dropped argument produces a successful run that looks like it
#: answered a narrower question.
_TYPE_OPTIONS = {
    "value-samples": (
        ("column", "--column", True),
        ("limit", "--limit", False),
    ),
    "join-coverage": (
        ("column", "--column", True),
        ("right_table", "--right-table", True),
        ("right_column", "--right-column", True),
    ),
}

#: Every option in ``_TYPE_OPTIONS``, by attribute, for the stray-flag check.
_TYPE_OPTION_FLAGS = {
    attribute: flag
    for options in _TYPE_OPTIONS.values()
    for attribute, flag, _required in options
}


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


def _refuse_name(args) -> None:
    """Refuse a NAME on a type that does not take one.

    Exit code 2: the type exists, the name exists, but the pair does not --
    ``introspect databases analytics`` is not a narrower ``databases``, it
    is a request this backend has no method for (there is no
    ``get_database_info`` by name, no ``get_schema_info``, no
    ``get_warehouse_info``). Refusing is the only answer that does not
    pretend the name changed the output.

    ``schemas --database analytics`` is not this check: ``--database`` says
    *which database's* schemas to enumerate, which is a different question
    from naming one schema, and it stays untouched.
    """
    if args.type not in _NO_NAME_TYPES or args.name is None:
        return
    print(
        f"Error: '{args.type}' introspection takes no name (got '{args.name}')",
        file=sys.stderr,
    )
    sys.exit(2)


def _require_name(args) -> None:
    """Refuse a type whose question cannot be asked without a NAME.

    Exit code 1, the same code a missing ``--database`` gets: an incomplete
    invocation, not a request this command declines. Exit 2 is reserved for
    the two things the CLI newly refuses to do -- answer for a family the
    server cannot, and accept a NAME the type has no use for.
    """
    if args.type not in _TABLE_NAME_TYPES or args.name is not None:
        return
    print(f"Error: Table name is required for '{args.type}' introspection", file=sys.stderr)
    sys.exit(1)


def _refuse_unused_arguments(args) -> None:
    """Refuse a flag the type has no question for, or a missing one it needs.

    The same defect as a silently dropped name, one flag over: ``--column``
    beside ``introspect tables`` would be ignored and the listing printed as
    if the column had been part of the question. Only the families whose probe
    takes a column read the flag, so only they may be given it.

    The flags are read with ``getattr`` because the handler is also driven
    with hand-built namespaces (the offline tests), which carry no flags at
    all -- an absent attribute is "not given", not an error.
    """
    options = _TYPE_OPTIONS.get(args.type, ())
    accepted = {attribute for attribute, _flag, _required in options}

    missing = [
        flag
        for attribute, flag, required in options
        if required and not getattr(args, attribute, None)
    ]
    if missing:
        print(
            f"Error: {', '.join(missing)} is required for '{args.type}' introspection",
            file=sys.stderr,
        )
        sys.exit(1)

    for attribute, flag in _TYPE_OPTION_FLAGS.items():
        if attribute in accepted:
            continue
        if getattr(args, attribute, None) not in (None, ""):
            print(
                f"Error: '{args.type}' introspection takes no {flag}",
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

  # One view, by name
  %(prog)s views v_users --account myaccount --database mydb

  # List the databases visible to the role, the schemas of a database,
  # and the virtual warehouses
  %(prog)s databases --account myaccount
  %(prog)s schemas --account myaccount --database mydb
  %(prog)s warehouses --account myaccount

  # Operational readings over the connection's scope: indexes no query has
  # used, per-table and per-index counters, live runtime facts, and the
  # dependency graph (which a NAME narrows to one object's edges)
  %(prog)s unused-indexes --account myaccount
  %(prog)s table-stats --account myaccount
  %(prog)s index-stats --account myaccount
  %(prog)s runtime --account myaccount
  %(prog)s dependencies --account myaccount
  %(prog)s dependencies orders --account myaccount

  # The DDL that recreates one table, the exact per-column profiles, and the
  # values one column holds. The profile reads every row, so it is paid for.
  %(prog)s ddl orders --account myaccount
  %(prog)s column-profiles orders --account myaccount
  %(prog)s value-samples orders --column status --account myaccount

  # How much two columns' value domains overlap
  %(prog)s join-coverage orders --column buyer_id --right-table customers \\
      --right-column id --account myaccount

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
        help=(
            "Object name: a table for columns, indexes, foreign-keys, "
            "table-storage-metrics, ddl, column-profiles, value-samples and "
            "join-coverage (required); the object itself for views and "
            "dependencies (optional); refused for tables, database, "
            "databases, schemas, warehouses, unused-indexes, table-stats, "
            "index-stats and runtime"
        ),
    )
    # The three families that ask about a column or a second table carry the
    # names the probe needs. They stay flags rather than more positionals
    # because ``name`` already means "the table" everywhere else, and
    # ``value-samples orders.email`` would read as a dotted object name.
    parser.add_argument(
        "--column",
        default=None,
        help=(
            "Column name: the column to sample for value-samples, and the "
            "left column for join-coverage"
        ),
    )
    parser.add_argument(
        "--right-table",
        default=None,
        help="Right-hand table for join-coverage",
    )
    parser.add_argument(
        "--right-column",
        default=None,
        help="Right-hand column for join-coverage",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Maximum values to list for value-samples "
            f"(default: {DEFAULT_VALUE_SAMPLE_LIMIT})."
        ),
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

    # The argument rules are applied here, before anything connects: an
    # incomplete invocation or a flag the type does not read is a statement
    # about the command line, not about the server, so it does not need a
    # round trip to say so.
    _refuse_name(args)
    _require_name(args)
    _refuse_unused_arguments(args)

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


def _display_ddl(provider, statement, args) -> None:
    """Show a DDL statement in the form that stays readable.

    A ``CREATE TABLE`` is text: a one-row table folds it into a cell that
    wraps at the terminal width and interleaves with the other columns. Table
    output therefore prints the statement itself, while the structured
    formats keep the whole row so JSON and CSV still carry ``object_type``
    and ``native`` beside the text.
    """
    if args.output == "table":
        print(statement.ddl or "")
        return
    data = _serialize_for_output([statement])
    provider.display_results(data, title=f"DDL of {statement.object_name}")


#: Said before a data-profile listing. It goes to stderr so the machine
#: formats stay parseable; each row carries ``source='aggregate'`` itself, and
#: this is the sentence that keeps a reader from taking an exact full-table
#: count for a cheap catalogue reading.
_AGGREGATE_PROFILE_NOTE = (
    "Note: column profiles are aggregated from the rows themselves "
    "(source='aggregate') -- exact, and paid for with a full scan per column."
)


def _value_sample_limit(args) -> int:
    """The row limit ``value-samples`` sends, given the parsed argument."""
    limit = getattr(args, "limit", None)
    return DEFAULT_VALUE_SAMPLE_LIMIT if limit is None else limit


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
            if args.name:
                view = introspector.get_view_info(args.name, schema=None)
                if view is None:
                    print(f"Error: View '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(_serialize_for_output([view]), title=f"View {args.name}")
            else:
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

        # ---- the operational families -------------------------------------
        # These read a statistics collector or the catalogue rather than the
        # schema structure: each one is a listing of the whole connection's
        # scope, so none takes a name (the dependency graph may be narrowed
        # to one object, and answers the whole graph without it).

        elif args.type == "unused-indexes":
            indexes = introspector.list_unused_indexes(schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title="Unused Indexes")

        elif args.type == "table-stats":
            stats = introspector.list_table_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Table Usage Stats")

        elif args.type == "runtime":
            metrics = introspector.list_runtime_metrics(schema=None)
            data = _serialize_for_output(metrics)
            provider.display_results(data, title="Runtime Metrics")

        elif args.type == "index-stats":
            stats = introspector.list_index_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Index Usage Stats")

        elif args.type == "dependencies":
            # A name narrows the graph to the edges that object carries --
            # "what breaks if I drop this" -- rather than asking a different
            # family, so it is optional here the way a trigger's table is.
            dependencies = introspector.list_object_dependencies(
                object_name=args.name, schema=None
            )
            data = _serialize_for_output(dependencies)
            title = f"Dependencies of {args.name}" if args.name else "Object Dependencies"
            provider.display_results(data, title=title)

        # ---- the one-object families --------------------------------------
        # The DDL that recreates a table, and the profiles of one table or one
        # column of it: the name is the table and the column is named on its
        # own flag.

        elif args.type == "ddl":
            statement = introspector.get_ddl_statement(args.name, object_type=None, schema=None)
            if statement is None:
                # Not "no such table": the object exists, and Snowflake
                # answers with no text rather than an assembled fragment that
                # would read as authoritative. The two are worth telling
                # apart, so this exits without printing an empty row.
                print(f"Error: no DDL available for '{args.name}'", file=sys.stderr)
                sys.exit(1)
            _display_ddl(provider, statement, args)

        elif args.type == "column-profiles":
            # The note goes to stderr so the machine formats stay parseable,
            # and each row carries ``source='aggregate'`` itself.
            print(_AGGREGATE_PROFILE_NOTE, file=sys.stderr)
            profiles = introspector.list_column_data_profiles(args.name, schema=None)
            data = _serialize_for_output(profiles)
            provider.display_results(data, title=f"Column profiles of {args.name}")

        elif args.type == "value-samples":
            samples = introspector.sample_column_values(
                args.name, args.column, limit=_value_sample_limit(args), schema=None
            )
            data = _serialize_for_output(samples)
            provider.display_results(data, title=f"Values of {args.name}.{args.column}")

        elif args.type == "join-coverage":
            coverage = introspector.estimate_join_coverage(
                args.name, args.column, args.right_table, args.right_column, schema=None
            )
            if coverage is None:
                # A column with nothing to match answers "no measurement",
                # which is not zero overlap; printing a row of nulls would
                # read as a measured zero.
                print(
                    f"Error: no coverage could be measured for {args.name}.{args.column} "
                    f"and {args.right_table}.{args.right_column}",
                    file=sys.stderr,
                )
                sys.exit(1)
            data = _serialize_for_output([coverage])
            provider.display_results(data, title="Join Coverage")

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
            if args.name:
                view = await introspector.get_view_info(args.name, schema=None)
                if view is None:
                    print(f"Error: View '{args.name}' not found", file=sys.stderr)
                    sys.exit(1)
                provider.display_results(_serialize_for_output([view]), title=f"View {args.name}")
            else:
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

        # The async twins of the nine branches above: same method, same
        # argument and same title, awaited. They are written out rather than
        # shared with the sync chain because the executor is the only thing
        # that differs, and a shared body would have to carry an ``await``
        # flag that reads worse than the duplicate.

        elif args.type == "unused-indexes":
            indexes = await introspector.list_unused_indexes(schema=None)
            data = _serialize_for_output(indexes)
            provider.display_results(data, title="Unused Indexes")

        elif args.type == "table-stats":
            stats = await introspector.list_table_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Table Usage Stats")

        elif args.type == "runtime":
            metrics = await introspector.list_runtime_metrics(schema=None)
            data = _serialize_for_output(metrics)
            provider.display_results(data, title="Runtime Metrics")

        elif args.type == "index-stats":
            stats = await introspector.list_index_usage_stats(schema=None)
            data = _serialize_for_output(stats)
            provider.display_results(data, title="Index Usage Stats")

        elif args.type == "dependencies":
            dependencies = await introspector.list_object_dependencies(
                object_name=args.name, schema=None
            )
            data = _serialize_for_output(dependencies)
            title = f"Dependencies of {args.name}" if args.name else "Object Dependencies"
            provider.display_results(data, title=title)

        elif args.type == "ddl":
            statement = await introspector.get_ddl_statement(
                args.name, object_type=None, schema=None
            )
            if statement is None:
                print(f"Error: no DDL available for '{args.name}'", file=sys.stderr)
                sys.exit(1)
            _display_ddl(provider, statement, args)

        elif args.type == "column-profiles":
            print(_AGGREGATE_PROFILE_NOTE, file=sys.stderr)
            profiles = await introspector.list_column_data_profiles(args.name, schema=None)
            data = _serialize_for_output(profiles)
            provider.display_results(data, title=f"Column profiles of {args.name}")

        elif args.type == "value-samples":
            samples = await introspector.sample_column_values(
                args.name, args.column, limit=_value_sample_limit(args), schema=None
            )
            data = _serialize_for_output(samples)
            provider.display_results(data, title=f"Values of {args.name}.{args.column}")

        elif args.type == "join-coverage":
            coverage = await introspector.estimate_join_coverage(
                args.name, args.column, args.right_table, args.right_column, schema=None
            )
            if coverage is None:
                print(
                    f"Error: no coverage could be measured for {args.name}.{args.column} "
                    f"and {args.right_table}.{args.right_column}",
                    file=sys.stderr,
                )
                sys.exit(1)
            data = _serialize_for_output([coverage])
            provider.display_results(data, title="Join Coverage")

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
