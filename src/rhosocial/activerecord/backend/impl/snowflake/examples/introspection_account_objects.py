# src/rhosocial/activerecord/backend/impl/snowflake/examples/introspection_account_objects.py
"""Introspect Snowflake account objects: databases, schemas, warehouses.

Run against a real account::

    python -m rhosocial.activerecord.backend.impl.snowflake.examples.introspection_account_objects
    python -m rhosocial.activerecord.backend.impl.snowflake.examples.introspection_account_objects ORDERS

The optional argument is a table name for the storage-metrics section; when
it is omitted the example picks the first table in the configured schema.

Credentials come from the same environment variables the test suite reads
(``tests/integration/conftest.py`` and ``tests/providers/scenarios.py``)::

    SNOWFLAKE_ACCOUNT       required
    SNOWFLAKE_USER          required
    SNOWFLAKE_PASSWORD      required unless SNOWFLAKE_PRIVATE_KEY_PATH is set
    SNOWFLAKE_PRIVATE_KEY_PATH   alternative to a password
    SNOWFLAKE_DATABASE      required (SCHEMATA and TABLE_STORAGE_METRICS are
                            database-level views)
    SNOWFLAKE_WAREHOUSE     required (Information Schema views need a running,
                            in-use warehouse)
    SNOWFLAKE_SCHEMA        optional, default PUBLIC
    SNOWFLAKE_ROLE          optional, passed only when set

With no credentials the example prints exactly which variables are missing,
exits with status 2, and contacts nothing: no connection is opened, no
statement is built, and no row is invented. A partial environment -- an
account and a user but no password and no key, say -- is refused the same way
rather than half-run.

**Nothing in this file was run against a Snowflake account.** The repo has
none. The example is documentation of the intended usage; the mocked tests
cover the SQL, the parsing and this refusal path.

The cache demonstration
-----------------------
Every section runs the same question twice and reports how many statements
actually reached the executor on the cold and the warm call. The cache is
part of the introspector, so the only honest way for an example to observe
it is to wrap the executor: a warm call must ask the account **zero**
questions. ``available`` and other fields are not cached separately --
each method's answer is one cache entry, so "cold=1, warm=0" is the whole
claim.
"""

import os
import sys
from typing import Any, Callable, List, Optional, Tuple, TypeVar

from ..backend import SnowflakeBackend
from ..config import SnowflakeConnectionConfig

_T = TypeVar("_T")

#: Environment variables that have no default and cannot be guessed.
_REQUIRED_SETTINGS = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_WAREHOUSE",
)

_SETUP_HELP = """\
No Snowflake credentials found in this environment; nothing was queried.

Set these environment variables (the same ones the test suite reads):
  SNOWFLAKE_ACCOUNT=your-account
  SNOWFLAKE_USER=your-user
  SNOWFLAKE_PASSWORD=your-password        # or SNOWFLAKE_PRIVATE_KEY_PATH=/path/to/key.p8
  SNOWFLAKE_DATABASE=your-database
  SNOWFLAKE_WAREHOUSE=your-warehouse

Optional:
  SNOWFLAKE_SCHEMA=PUBLIC                 # default: PUBLIC
  SNOWFLAKE_ROLE=SYSADMIN                 # passed only when set

The database is required because SCHEMATA and TABLE_STORAGE_METRICS are
database-level views; the warehouse is required because Information Schema
views must be queried through a running, in-use warehouse.
"""


class _CountingExecutor:
    """The introspector's executor, with a statement counter in front of it.

    Deliberately minimal: it delegates the one method the introspector calls
    and counts it. A warm cache hit must leave :attr:`questions` unchanged,
    which is the property the example prints.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.questions = 0

    def execute(self, sql: str, params: Tuple = ()) -> List[dict]:
        self.questions += 1
        return self._inner.execute(sql, params)


def _missing_settings() -> List[str]:
    """Return the required settings this environment does not provide."""
    missing = [name for name in _REQUIRED_SETTINGS if not os.getenv(name)]
    if not os.getenv("SNOWFLAKE_PASSWORD") and not os.getenv(
        "SNOWFLAKE_PRIVATE_KEY_PATH"
    ):
        missing.append("SNOWFLAKE_PASSWORD (or SNOWFLAKE_PRIVATE_KEY_PATH)")
    return missing


def _config_from_env() -> Optional[SnowflakeConnectionConfig]:
    """Build a connection config from the test suite's environment variables."""
    missing = _missing_settings()
    if missing:
        print(_SETUP_HELP, file=sys.stderr)
        print("Missing here: " + ", ".join(missing), file=sys.stderr)
        return None

    return SnowflakeConnectionConfig(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        username=os.environ["SNOWFLAKE_USER"],
        password=os.getenv("SNOWFLAKE_PASSWORD", ""),
        private_key_path=os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH"),
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.getenv("SNOWFLAKE_ROLE"),
    )


def _wrap(executor: Any) -> Tuple["_CountingExecutor", Optional[Any]]:
    """Put a counter in front of *executor*, keeping the original.

    Returns the counting wrapper and the executor it stands in for, so the
    caller can restore the real one afterwards. Both are ``None`` only if
    *executor* is missing, which would mean there is no driver to count.
    """
    counter = _CountingExecutor(executor)
    return counter, executor


def _ask(counter: _CountingExecutor, call: Callable[[], _T]) -> Tuple[int, _T]:
    """Run *call* and return how many SQL statements it cost."""
    before = counter.questions
    value = call()
    return counter.questions - before, value


def _print_databases(databases: List[Any]) -> None:
    for database in databases:
        print(
            f"  {database.name}"
            f"  type={database.database_type or '-'}"
            f"  owner={database.owner or '-'}"
            f"  transient={'yes' if database.is_transient else 'no'}"
        )


def _print_schemas(schemas: List[Any]) -> None:
    for schema in schemas:
        print(
            f"  {schema.name}"
            f"  owner={schema.owner or '-'}"
            f"  managed_access={'yes' if schema.is_managed_access else 'no'}"
            f"  transient={'yes' if schema.is_transient else 'no'}"
        )


def _print_warehouses(warehouses: List[Any]) -> None:
    for warehouse in warehouses:
        current = "  <- current" if warehouse.is_current else ""
        print(
            f"  {warehouse.name}"
            f"  state={warehouse.state or '-'}"
            f"  size={warehouse.size or '-'}"
            f"  clusters={warehouse.started_clusters or 0}/"
            f"{warehouse.max_cluster_count or 0}{current}"
        )


def _print_storage_metrics(table_name: str, metrics: Any) -> None:
    if metrics is None:
        print(
            f"  {table_name}: no metrics row. The view is documented to return no\n"
            "  rows for roles other than ACCOUNTADMIN, so this can mean either\n"
            "  'no such table' or 'this role may not see the metrics'."
        )
        return
    print(f"  {metrics.table_name} ({metrics.table_schema or '?'})")
    print(f"    table type       : {metrics.table_type or '-'}")
    print(f"    row count        : {metrics.row_count if metrics.row_count is not None else 'not reported'}")
    print(f"    active bytes     : {metrics.active_bytes}")
    print(f"    time travel bytes: {metrics.time_travel_bytes}")
    print(f"    failsafe bytes   : {metrics.failsafe_bytes}")
    print(f"    clone-retained   : {metrics.retained_for_clone_bytes}")
    print(f"    total billed     : {metrics.total_billed_bytes}")
    print(f"    clustering key   : {metrics.clustering_key or 'none'}")
    print(
        "    auto clustering  : "
        + ("on" if metrics.auto_clustering_on else "off")
    )


def main(argv: Optional[List[str]] = None) -> int:
    """Run the example. Returns a process exit code."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    config = _config_from_env()
    if config is None:
        return 2

    requested_table = arguments[0] if arguments else None
    backend = SnowflakeBackend(connection_config=config)

    introspector = None
    inner: Optional[Any] = None
    try:
        backend.connect()
        introspector = backend.introspector
        counter, inner = _wrap(introspector._executor)
        # Replacing the executor is the example's observation hook; the cache
        # itself is not instrumented, so a warm call reaching it must be
        # visible as one fewer statement. The real executor is put back before
        # the backend is disconnected, so a failed run leaves no observer
        # between the introspector and the driver.
        introspector._executor = counter
        introspector.clear_cache()

        print("Databases")
        cold, databases = _ask(counter, introspector.list_databases)
        warm, _ = _ask(counter, introspector.list_databases)
        _print_databases(databases)
        print(f"  ({len(databases)} row(s); executor questions cold={cold} warm={warm})")

        print("\nSchemas")
        cold, schemas = _ask(counter, introspector.list_schemas)
        warm, _ = _ask(counter, introspector.list_schemas)
        _print_schemas(schemas)
        print(f"  ({len(schemas)} row(s); executor questions cold={cold} warm={warm})")

        print("\nWarehouses")
        cold, warehouses = _ask(counter, introspector.list_warehouses)
        warm, _ = _ask(counter, introspector.list_warehouses)
        _print_warehouses(warehouses)
        print(f"  ({len(warehouses)} row(s); executor questions cold={cold} warm={warm})")

        table_name = requested_table
        if table_name is None:
            tables = introspector.list_tables()
            table_name = tables[0].name if tables else None

        print("\nTable storage metrics")
        if table_name is None:
            print(
                "  No table to measure: the configured schema has no tables.\n"
                "  Pass a table name as the first argument to measure one."
            )
        else:
            cold, metrics = _ask(
                counter,
                lambda: introspector.get_table_storage_metrics(table_name),
            )
            warm, _ = _ask(
                counter,
                lambda: introspector.get_table_storage_metrics(table_name),
            )
            _print_storage_metrics(table_name, metrics)
            print(f"  (executor questions cold={cold} warm={warm})")

    except Exception as exc:  # noqa: BLE001 -- a runnable example reports, not raises
        print(f"Introspection failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        # Restore only what was actually replaced.
        if introspector is not None and inner is not None:
            introspector._executor = inner
        # The backend may never have connected; disconnect only when it did.
        if getattr(backend, "_connection", None):
            backend.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
