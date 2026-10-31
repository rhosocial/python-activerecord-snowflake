# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_account_introspection.py
"""Account-object introspection: SQL text, row parsing, caching, symmetry.

Every test here is offline. Rows are fabricated to match the documented
column names and value domains; no Snowflake account is contacted, and a
passing test pins the statement and the parser, never the account's answer.

The statements are built by the expression classes in
``rhosocial.activerecord.backend.impl.snowflake.expression.introspection`` and
rendered by the dialect mixin, so each SQL expectation below is the output of a
tree of ``Column`` / ``ComparisonPredicate`` / ``Literal`` / ``QueryStatement``
nodes rather than of a text builder. Any statement that stops being built that
way fails here as a text mismatch.

Documentation the expectations were written from:

* https://docs.snowflake.com/en/sql-reference/info-schema/databases
* https://docs.snowflake.com/en/sql-reference/info-schema/schemata
* https://docs.snowflake.com/en/sql-reference/sql/show-warehouses
* https://docs.snowflake.com/en/sql-reference/info-schema/table_storage_metrics
* https://docs.snowflake.com/en/sql-reference/info-schema/tables
"""
import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.introspection import (
    AsyncSnowflakeIntrospector,
    SnowflakeDatabaseInfo,
    SnowflakeIntrospectorMixin,
    SnowflakeSchemaInfo,
    SnowflakeTableStorageMetrics,
    SnowflakeWarehouseInfo,
    SyncSnowflakeIntrospector,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.introspection import (
    SnowflakeDatabaseListQueryStatement,
    SnowflakeSchemaListQueryStatement,
    SnowflakeTableStorageMetricsQueryStatement,
    SnowflakeWarehouseListQueryStatement,
)
from rhosocial.activerecord.backend.introspection.executor import (
    SyncIntrospectorExecutor,
)

DATABASES_SQL = (
    "SELECT DATABASE_NAME, DATABASE_OWNER, IS_TRANSIENT, COMMENT, "
    "CREATED, LAST_ALTERED, RETENTION_TIME, TYPE, OWNER_ROLE_TYPE "
    "FROM SNOWFLAKE.INFORMATION_SCHEMA.DATABASES "
    "ORDER BY DATABASE_NAME"
)

SCHEMAS_SQL = (
    "SELECT CATALOG_NAME, SCHEMA_NAME, SCHEMA_OWNER, IS_TRANSIENT, "
    "IS_MANAGED_ACCESS, RETENTION_TIME, CREATED, LAST_ALTERED, COMMENT "
    "FROM INFORMATION_SCHEMA.SCHEMATA ORDER BY SCHEMA_NAME"
)

SCHEMAS_IN_DATABASE_SQL = (
    "SELECT CATALOG_NAME, SCHEMA_NAME, SCHEMA_OWNER, IS_TRANSIENT, "
    "IS_MANAGED_ACCESS, RETENTION_TIME, CREATED, LAST_ALTERED, COMMENT "
    'FROM "ANALYTICS".INFORMATION_SCHEMA.SCHEMATA ORDER BY SCHEMA_NAME'
)

STORAGE_SQL = (
    "SELECT m.TABLE_CATALOG, m.TABLE_SCHEMA, m.TABLE_NAME, m.ID, "
    "m.CLONE_GROUP_ID, m.IS_TRANSIENT, m.ACTIVE_BYTES, "
    "m.TIME_TRAVEL_BYTES, m.FAILSAFE_BYTES, m.RETAINED_FOR_CLONE_BYTES, "
    "m.TABLE_CREATED, m.TABLE_DROPPED, m.TABLE_ENTERED_FAILSAFE, "
    "m.COMMENT, t.TABLE_TYPE, t.ROW_COUNT, t.CLUSTERING_KEY, "
    "t.AUTO_CLUSTERING_ON "
    "FROM INFORMATION_SCHEMA.TABLE_STORAGE_METRICS AS m "
    "LEFT JOIN INFORMATION_SCHEMA.TABLES AS t "
    "ON t.TABLE_CATALOG = m.TABLE_CATALOG "
    "AND t.TABLE_SCHEMA = m.TABLE_SCHEMA "
    "AND t.TABLE_NAME = m.TABLE_NAME "
    "WHERE m.TABLE_NAME = %s AND m.TABLE_DROPPED IS NULL "
    "AND m.TABLE_SCHEMA = %s ORDER BY m.TABLE_CREATED DESC"
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 32, 0))


@pytest.fixture
def mock_backend(dialect):
    backend = MagicMock()
    backend._version = (8, 32, 0)
    backend.config = MagicMock()
    backend.config.schema = "PUBLIC"
    backend.config.database = "MY_DB"
    backend.dialect = dialect
    return backend


@pytest.fixture
def sync_executor():
    return MagicMock(spec=SyncIntrospectorExecutor)


@pytest.fixture
def sync_introspector(mock_backend, sync_executor):
    return SyncSnowflakeIntrospector(mock_backend, sync_executor)


@pytest.fixture
def async_executor():
    return AsyncMock()


@pytest.fixture
def async_introspector(mock_backend, async_executor):
    return AsyncSnowflakeIntrospector(mock_backend, async_executor)


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


def schema_row(**overrides):
    row = {
        "CATALOG_NAME": "ANALYTICS",
        "SCHEMA_NAME": "PUBLIC",
        "SCHEMA_OWNER": "SYSADMIN",
        "IS_TRANSIENT": "YES",
        "IS_MANAGED_ACCESS": "NO",
        "RETENTION_TIME": 0,
        "CREATED": datetime(2026, 1, 2, 3, 4, 5),
        "LAST_ALTERED": datetime(2026, 2, 3, 4, 5, 6),
        "COMMENT": None,
    }
    row.update(overrides)
    return row


def warehouse_row(**overrides):
    """A ``SHOW WAREHOUSES`` row, in the lowercase shape the page shows."""
    row = {
        "name": "COMPUTE_WH",
        "state": "STARTED",
        "type": "STANDARD",
        "size": "X-Small",
        "min_cluster_count": 1,
        "max_cluster_count": 2,
        "started_clusters": 1,
        "running": 0,
        "queued": 0,
        "is_default": "Y",
        "is_current": "N",
        "is_interactive": "N",
        "auto_suspend": 60,
        "auto_resume": "Y",
        "created_on": datetime(2026, 1, 1),
        "resumed_on": datetime(2026, 1, 2),
        "updated_on": datetime(2026, 1, 3),
        "owner": "SYSADMIN",
        "comment": "primary",
        "scaling_policy": "STANDARD",
        "resource_constraint": None,
        "generation": 2,
        "enable_query_acceleration": "N",
        "query_acceleration_max_scale_factor": 8,
        "resource_monitor": None,
        "owner_role_type": "ROLE",
    }
    row.update(overrides)
    return row


def storage_row(**overrides):
    row = {
        "TABLE_CATALOG": "ANALYTICS",
        "TABLE_SCHEMA": "PUBLIC",
        "TABLE_NAME": "ORDERS",
        "ID": 42,
        "CLONE_GROUP_ID": 42,
        "IS_TRANSIENT": "NO",
        "ACTIVE_BYTES": 1024,
        "TIME_TRAVEL_BYTES": 200,
        "FAILSAFE_BYTES": 30,
        "RETAINED_FOR_CLONE_BYTES": 5,
        "TABLE_CREATED": datetime(2026, 1, 2),
        "TABLE_DROPPED": None,
        "TABLE_ENTERED_FAILSAFE": None,
        "COMMENT": "orders",
        "TABLE_TYPE": "BASE TABLE",
        "ROW_COUNT": 17,
        "CLUSTERING_KEY": "LINEAR(ORDER_DATE)",
        "AUTO_CLUSTERING_ON": True,
    }
    row.update(overrides)
    return row


# ================================================================== #
# SQL text -- the rendered tree, pinned
# ================================================================== #

class TestAccountObjectSQL:
    """Each statement class renders the documented SQL through the dialect.

    The expectations are the output of ``Expression.to_sql()``, so they pin
    the whole path: node construction, the dialect formatter, the placeholder
    spelling and the alias quoting. A statement that falls back to text
    concatenation loses the ``AS m`` / ``AS t`` row-source spellings and fails
    here.
    """

    def test_databases_sql_is_exact(self, dialect):
        assert SnowflakeDatabaseListQueryStatement(dialect).to_sql() == (
            DATABASES_SQL,
            (),
        )

    def test_schemas_sql_without_database_is_exact(self, dialect):
        assert SnowflakeSchemaListQueryStatement(dialect).to_sql() == (
            SCHEMAS_SQL,
            (),
        )

    def test_schemas_sql_qualifies_the_database(self, dialect):
        # A database name is part of the view's name, so it is rendered as a
        # quoted identifier rather than bound.
        assert SnowflakeSchemaListQueryStatement(
            dialect, database="ANALYTICS"
        ).to_sql() == (SCHEMAS_IN_DATABASE_SQL, ())

    def test_warehouses_use_show_not_a_view(self, dialect):
        # There is no INFORMATION_SCHEMA.WAREHOUSES; the documented route is
        # SHOW WAREHOUSES, rendered by the SHOW statement expression.
        assert SnowflakeWarehouseListQueryStatement(dialect).to_sql() == (
            "SHOW WAREHOUSES",
            (),
        )

    def test_storage_sql_is_exact(self, dialect):
        assert SnowflakeTableStorageMetricsQueryStatement(
            dialect, "ORDERS", schema="PUBLIC"
        ).to_sql() == (STORAGE_SQL, ("ORDERS", "PUBLIC"))

    def test_storage_sql_omits_schema_filter_when_absent(self, dialect):
        sql, params = SnowflakeTableStorageMetricsQueryStatement(
            dialect, "ORDERS"
        ).to_sql()
        assert "AND m.TABLE_SCHEMA = %s" not in sql
        assert sql.endswith("ORDER BY m.TABLE_CREATED DESC")
        assert params == ("ORDERS",)

    def test_statements_bind_values_and_never_interpolate_them(self, dialect):
        """A caller-supplied name is a bind parameter, not SQL text.

        The one exception is the database a caller asks for schemas of, which
        is part of the view's name and therefore an identifier. A table name
        is a value compared to a column, so it must travel as a parameter.
        """
        sql, params = SnowflakeTableStorageMetricsQueryStatement(
            dialect, "ORDERS'); DROP TABLE users;--", schema="PUBLIC"
        ).to_sql()
        assert params == ("ORDERS'); DROP TABLE users;--", "PUBLIC")
        assert "DROP TABLE" not in sql
        assert sql.count("%s") == 2


# ================================================================== #
# Row parsing
# ================================================================== #

class TestAccountObjectParsing:
    @pytest.fixture
    def parser(self):
        return SnowflakeIntrospectorMixin.__new__(SnowflakeIntrospectorMixin)

    def test_database_row_maps_to_typed_value(self, parser):
        [database] = parser.parse_databases([database_row()])
        assert database == SnowflakeDatabaseInfo(
            name="ANALYTICS",
            owner="SYSADMIN",
            is_transient=False,
            comment="reporting",
            created=datetime(2026, 1, 2, 3, 4, 5),
            last_altered=datetime(2026, 2, 3, 4, 5, 6),
            retention_time=1,
            database_type="STANDARD",
            owner_role_type="ROLE",
        )

    def test_database_transient_flag_reads_yes(self, parser):
        [database] = parser.parse_databases(
            [database_row(IS_TRANSIENT="YES")]
        )
        assert database.is_transient is True

    def test_database_keys_are_case_insensitive(self, parser):
        row = {key.lower(): value for key, value in database_row().items()}
        [database] = parser.parse_databases([row])
        assert database.name == "ANALYTICS"

    def test_database_unreadable_number_becomes_none(self, parser):
        [database] = parser.parse_databases(
            [database_row(RETENTION_TIME="not-a-number")]
        )
        assert database.retention_time is None

    def test_schema_row_maps_to_typed_value(self, parser):
        [schema] = parser.parse_schemas([schema_row()])
        assert schema == SnowflakeSchemaInfo(
            name="PUBLIC",
            catalog_name="ANALYTICS",
            owner="SYSADMIN",
            is_transient=True,
            is_managed_access=False,
            retention_time=0,
            created=datetime(2026, 1, 2, 3, 4, 5),
            last_altered=datetime(2026, 2, 3, 4, 5, 6),
            comment=None,
        )

    def test_schema_managed_access_reads_yes(self, parser):
        [schema] = parser.parse_schemas(
            [schema_row(IS_MANAGED_ACCESS="YES")]
        )
        assert schema.is_managed_access is True

    def test_warehouse_row_maps_lowercase_keys(self, parser):
        [warehouse] = parser.parse_warehouses([warehouse_row()])
        assert warehouse == SnowflakeWarehouseInfo(
            name="COMPUTE_WH",
            state="STARTED",
            warehouse_type="STANDARD",
            size="X-Small",
            min_cluster_count=1,
            max_cluster_count=2,
            started_clusters=1,
            running=0,
            queued=0,
            is_default=True,
            is_current=False,
            is_interactive=False,
            auto_suspend=60,
            auto_resume=True,
            created_on=datetime(2026, 1, 1),
            resumed_on=datetime(2026, 1, 2),
            updated_on=datetime(2026, 1, 3),
            owner="SYSADMIN",
            comment="primary",
            scaling_policy="STANDARD",
            resource_constraint=None,
            generation=2,
            enable_query_acceleration=False,
            query_acceleration_max_scale_factor=8,
            resource_monitor=None,
            owner_role_type="ROLE",
        )

    def test_warehouse_auto_suspend_null_means_never(self, parser):
        [warehouse] = parser.parse_warehouses(
            [warehouse_row(auto_suspend=None, auto_resume=None)]
        )
        assert warehouse.auto_suspend is None
        assert warehouse.auto_resume is None

    def test_storage_row_maps_and_sums_bytes(self, parser):
        metrics = parser.parse_table_storage_metrics(
            [storage_row()], "ORDERS", "PUBLIC"
        )
        assert metrics == SnowflakeTableStorageMetrics(
            table_name="ORDERS",
            table_catalog="ANALYTICS",
            table_schema="PUBLIC",
            table_id=42,
            clone_group_id=42,
            is_transient=False,
            table_type="BASE TABLE",
            active_bytes=1024,
            time_travel_bytes=200,
            failsafe_bytes=30,
            retained_for_clone_bytes=5,
            row_count=17,
            clustering_key="LINEAR(ORDER_DATE)",
            auto_clustering_on=True,
            table_created=datetime(2026, 1, 2),
            table_dropped=None,
            table_entered_failsafe=None,
            comment="orders",
        )
        assert metrics.total_billed_bytes == 1259
        assert metrics.is_dropped is False
        assert metrics.is_clustered is True

    def test_storage_prefers_the_current_version(self, parser):
        dropped = storage_row(
            TABLE_DROPPED=datetime(2026, 2, 1),
            ACTIVE_BYTES=1,
            TABLE_NAME="ORDERS",
        )
        metrics = parser.parse_table_storage_metrics(
            [dropped, storage_row()], "ORDERS", "PUBLIC"
        )
        assert metrics.table_dropped is None
        assert metrics.active_bytes == 1024

    def test_storage_without_rows_is_none(self, parser):
        assert (
            parser.parse_table_storage_metrics([], "ORDERS", "PUBLIC")
            is None
        )

    def test_storage_unclustered_table(self, parser):
        metrics = parser.parse_table_storage_metrics(
            [
                storage_row(
                    CLUSTERING_KEY=None,
                    AUTO_CLUSTERING_ON=False,
                    ROW_COUNT=0,
                )
            ],
            "ORDERS",
            "PUBLIC",
        )
        assert metrics.is_clustered is False
        assert metrics.row_count == 0
        assert metrics.auto_clustering_on is False


# ================================================================== #
# Sync public API: exact statements and warm cache
# ================================================================== #

class TestSyncAccountObjectIntrospection:
    def test_list_databases_executes_documented_sql(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [database_row()]
        databases = sync_introspector.list_databases()
        assert databases == [SnowflakeDatabaseInfo(
            name="ANALYTICS",
            owner="SYSADMIN",
            is_transient=False,
            comment="reporting",
            created=datetime(2026, 1, 2, 3, 4, 5),
            last_altered=datetime(2026, 2, 3, 4, 5, 6),
            retention_time=1,
            database_type="STANDARD",
            owner_role_type="ROLE",
        )]
        sync_executor.execute.assert_called_once_with(DATABASES_SQL, ())

    def test_list_databases_second_call_is_a_cache_hit(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [database_row()]
        first = sync_introspector.list_databases()
        second = sync_introspector.list_databases()
        assert first is second
        assert sync_executor.execute.call_count == 1

    def test_list_schemas_passes_database_as_identifier(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [schema_row()]
        schemas = sync_introspector.list_schemas("ANALYTICS")
        assert schemas == [SnowflakeSchemaInfo(
            name="PUBLIC",
            catalog_name="ANALYTICS",
            owner="SYSADMIN",
            is_transient=True,
            is_managed_access=False,
            retention_time=0,
            created=datetime(2026, 1, 2, 3, 4, 5),
            last_altered=datetime(2026, 2, 3, 4, 5, 6),
            comment=None,
        )]
        sync_executor.execute.assert_called_once_with(
            SCHEMAS_IN_DATABASE_SQL, ()
        )

    def test_list_schemas_does_not_share_between_databases(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [schema_row()]
        sync_introspector.list_schemas()
        sync_introspector.list_schemas("ANALYTICS")
        sync_introspector.list_schemas("ANALYTICS")
        assert sync_executor.execute.call_count == 2

    def test_list_warehouses_executes_show(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [warehouse_row()]
        [warehouse] = sync_introspector.list_warehouses()
        assert warehouse.name == "COMPUTE_WH"
        assert warehouse.is_default is True
        sync_executor.execute.assert_called_once_with("SHOW WAREHOUSES", ())

    def test_list_warehouses_second_call_is_a_cache_hit(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [warehouse_row()]
        sync_introspector.list_warehouses()
        sync_introspector.list_warehouses()
        assert sync_executor.execute.call_count == 1

    def test_storage_metrics_uses_configured_schema(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [storage_row()]
        metrics = sync_introspector.get_table_storage_metrics("ORDERS")
        assert metrics.table_schema == "PUBLIC"
        sync_executor.execute.assert_called_once_with(
            STORAGE_SQL, ("ORDERS", "PUBLIC")
        )

    def test_storage_metrics_second_call_is_a_cache_hit(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [storage_row()]
        first = sync_introspector.get_table_storage_metrics("ORDERS")
        second = sync_introspector.get_table_storage_metrics("ORDERS")
        assert first is second
        assert sync_executor.execute.call_count == 1

    def test_storage_metrics_none_is_not_cached(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.side_effect = [[], [storage_row()]]
        assert sync_introspector.get_table_storage_metrics("ORDERS") is None
        assert sync_introspector.get_table_storage_metrics("ORDERS") is not None
        assert sync_executor.execute.call_count == 2


# ================================================================== #
# Async public API mirrors the sync one
# ================================================================== #

class TestAsyncAccountObjectIntrospection:
    async def test_list_databases_awaits_the_same_sql(
        self, async_introspector, async_executor
    ):
        async_executor.execute.return_value = [database_row()]
        [database] = await async_introspector.list_databases()
        assert database.name == "ANALYTICS"
        async_executor.execute.assert_awaited_once_with(DATABASES_SQL, ())

    async def test_list_databases_second_call_is_a_cache_hit(
        self, async_introspector, async_executor
    ):
        async_executor.execute.return_value = [database_row()]
        first = await async_introspector.list_databases()
        second = await async_introspector.list_databases()
        assert first is second
        assert async_executor.execute.await_count == 1

    async def test_list_schemas_awaits_the_same_sql(
        self, async_introspector, async_executor
    ):
        async_executor.execute.return_value = [schema_row()]
        [schema] = await async_introspector.list_schemas("ANALYTICS")
        assert schema.name == "PUBLIC"
        async_executor.execute.assert_awaited_once_with(
            SCHEMAS_IN_DATABASE_SQL, ()
        )

    async def test_list_warehouses_awaits_show(
        self, async_introspector, async_executor
    ):
        async_executor.execute.return_value = [warehouse_row()]
        [warehouse] = await async_introspector.list_warehouses()
        assert warehouse.is_current is False
        async_executor.execute.assert_awaited_once_with(
            "SHOW WAREHOUSES", ()
        )

    async def test_storage_metrics_awaits_the_same_sql(
        self, async_introspector, async_executor
    ):
        async_executor.execute.return_value = [storage_row()]
        metrics = await async_introspector.get_table_storage_metrics("ORDERS")
        assert metrics.total_billed_bytes == 1259
        async_executor.execute.assert_awaited_once_with(
            STORAGE_SQL, ("ORDERS", "PUBLIC")
        )

    async def test_storage_metrics_none_is_not_cached(
        self, async_introspector, async_executor
    ):
        async_executor.execute.side_effect = [[], [storage_row()]]
        assert (
            await async_introspector.get_table_storage_metrics("ORDERS")
            is None
        )
        assert (
            await async_introspector.get_table_storage_metrics("ORDERS")
            is not None
        )
        assert async_executor.execute.await_count == 2


# ================================================================== #
# Value semantics and sync/async symmetry
# ================================================================== #

class TestAccountObjectValues:
    def test_values_are_frozen(self):
        database = SnowflakeDatabaseInfo(name="ANALYTICS")
        with pytest.raises(FrozenInstanceError):
            database.name = "OTHER"  # type: ignore[misc]

    def test_sync_and_async_methods_have_identical_signatures(self):
        for name in (
            "list_databases",
            "list_schemas",
            "list_warehouses",
            "get_table_storage_metrics",
        ):
            sync_signature = inspect.signature(
                getattr(SyncSnowflakeIntrospector, name)
            )
            async_signature = inspect.signature(
                getattr(AsyncSnowflakeIntrospector, name)
            )
            assert sync_signature == async_signature, name

    def test_every_statement_names_a_dialect_formatter(self, dialect):
        """The tree dispatches through the dialect; no node renders itself.

        Each statement's ``format_method`` must be a ``format_*_query_statement``
        method this backend's dialect mixin actually implements, or ``to_sql()``
        raises at render time rather than producing wrong SQL.
        """
        statements = (
            (SnowflakeDatabaseListQueryStatement, {}),
            (SnowflakeSchemaListQueryStatement, {}),
            (SnowflakeWarehouseListQueryStatement, {}),
            (SnowflakeTableStorageMetricsQueryStatement, {"table_name": "T"}),
        )
        for statement, kwargs in statements:
            method = statement(dialect, **kwargs).format_method
            assert method.endswith("_query_statement"), statement.__name__
            assert callable(getattr(dialect, method)), (
                f"{statement.__name__} renders through {method}, "
                "which the dialect does not implement"
            )
