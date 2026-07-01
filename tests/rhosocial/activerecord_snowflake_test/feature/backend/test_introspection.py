"""Tests for Snowflake introspection system.

Tests cover:
- SnowflakeIntrospectionMixin format_*_query methods
- SnowflakeIntrospectorMixin _parse_* methods
- SyncSnowflakeIntrospector with mock backend
- AsyncSnowflakeIntrospector with mock backend
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Any, Dict, List, Optional

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import SnowflakeIntrospectionMixin
from rhosocial.activerecord.backend.impl.snowflake.introspection import (
    SnowflakeIntrospectorMixin,
    SyncSnowflakeIntrospector,
    AsyncSnowflakeIntrospector,
)
from rhosocial.activerecord.backend.introspection.types import (
    DatabaseInfo,
    TableInfo,
    TableType,
    ColumnInfo,
    ColumnNullable,
    IndexInfo,
    IndexColumnInfo,
    IndexType,
    ForeignKeyInfo,
    ReferentialAction,
    ViewInfo,
    TriggerInfo,
)
from rhosocial.activerecord.backend.introspection.executor import SyncIntrospectorExecutor


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


# ================================================================== #
# Tests for SnowflakeIntrospectionMixin (Dialect layer)
# ================================================================== #

class TestSnowflakeIntrospectionCapabilities:
    """Test Snowflake introspection capability detection."""

    def test_supports_introspection(self, dialect):
        assert dialect.supports_introspection() is True

    def test_supports_database_info(self, dialect):
        assert dialect.supports_database_info() is True

    def test_supports_table_introspection(self, dialect):
        assert dialect.supports_table_introspection() is True

    def test_supports_column_introspection(self, dialect):
        assert dialect.supports_column_introspection() is True

    def test_supports_index_introspection(self, dialect):
        assert dialect.supports_index_introspection() is True

    def test_supports_foreign_key_introspection(self, dialect):
        assert dialect.supports_foreign_key_introspection() is True

    def test_supports_view_introspection(self, dialect):
        assert dialect.supports_view_introspection() is True

    def test_does_not_support_trigger_introspection(self, dialect):
        assert dialect.supports_trigger_introspection() is False


class TestSnowflakeIntrospectionSQLGeneration:
    """Test SQL generation for introspection queries."""

    def test_format_database_info_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import DatabaseInfoExpression
        expr = DatabaseInfoExpression(dialect)
        sql, params = dialect.format_database_info_query(expr)
        assert "CURRENT_DATABASE()" in sql
        assert "CURRENT_VERSION()" in sql
        assert params == ()

    def test_format_table_list_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import TableListExpression
        expr = TableListExpression(dialect)
        expr.schema("MY_SCHEMA")
        sql, params = dialect.format_table_list_query(expr)
        assert "INFORMATION_SCHEMA.TABLES" in sql
        assert "TABLE_SCHEMA = %s" in sql
        assert params == ("MY_SCHEMA",)

    def test_format_table_list_query_no_views(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import TableListExpression
        expr = TableListExpression(dialect)
        expr.schema("MY_SCHEMA")
        # include_views defaults to True
        sql, params = dialect.format_table_list_query(expr)
        # When include_views=True, no TABLE_TYPE filter should be present
        assert "TABLE_TYPE = 'BASE TABLE'" not in sql

    def test_format_column_info_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import ColumnInfoExpression
        expr = ColumnInfoExpression(dialect, table_name="users")
        expr.schema("MY_SCHEMA")
        sql, params = dialect.format_column_info_query(expr)
        assert "INFORMATION_SCHEMA.COLUMNS" in sql
        assert params == ("MY_SCHEMA", "users")

    def test_format_index_info_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import IndexInfoExpression
        expr = IndexInfoExpression(dialect, table_name="users")
        expr.schema("MY_SCHEMA")
        sql, params = dialect.format_index_info_query(expr)
        assert "INFORMATION_SCHEMA.TABLE_CONSTRAINTS" in sql
        assert "INFORMATION_SCHEMA.KEY_COLUMN_USAGE" in sql
        assert "CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE')" in sql
        assert params == ("MY_SCHEMA", "users")

    def test_format_foreign_key_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import ForeignKeyExpression
        expr = ForeignKeyExpression(dialect, table_name="orders")
        expr.schema("MY_SCHEMA")
        sql, params = dialect.format_foreign_key_query(expr)
        assert "INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS" in sql
        assert "INFORMATION_SCHEMA.KEY_COLUMN_USAGE" in sql
        assert "REFERENCED_TABLE_NAME" in sql
        assert "REFERENCED_COLUMN_NAME" in sql
        assert params == ("MY_SCHEMA", "orders")

    def test_format_view_list_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import ViewListExpression
        expr = ViewListExpression(dialect)
        expr.schema("MY_SCHEMA")
        sql, params = dialect.format_view_list_query(expr)
        assert "INFORMATION_SCHEMA.VIEWS" in sql
        assert params == ("MY_SCHEMA",)

    def test_format_view_info_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import ViewInfoExpression
        expr = ViewInfoExpression(dialect, view_name="my_view")
        expr.schema("MY_SCHEMA")
        sql, params = dialect.format_view_info_query(expr)
        assert "INFORMATION_SCHEMA.VIEWS" in sql
        assert "TABLE_NAME = %s" in sql
        assert params == ("MY_SCHEMA", "my_view")

    def test_format_trigger_list_query_returns_empty(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import TriggerListExpression
        expr = TriggerListExpression(dialect)
        expr.schema("MY_SCHEMA")
        sql, params = dialect.format_trigger_list_query(expr)
        assert "1 = 0" in sql


# ================================================================== #
# Tests for SnowflakeIntrospectorMixin (Parse methods)
# ================================================================== #

class TestSnowflakeIntrospectorParsing:
    """Test _parse_* methods for converting raw rows to data structures."""

    @pytest.fixture
    def introspector_mixin(self):
        """Create a minimal introspector mixin with mock backend."""

        class MockBackend:
            _version = (8, 32, 0)
            config = MagicMock()
            config.schema = "PUBLIC"

        mixin = SnowflakeIntrospectorMixin()
        mixin._backend = MockBackend()
        return mixin

    def test_parse_database_info(self, introspector_mixin):
        rows = [
            {"CATALOG_NAME": "MY_DB", "SERVER_VERSION": "8.32.0"},
        ]
        result = introspector_mixin._parse_database_info(rows)
        assert isinstance(result, DatabaseInfo)
        assert result.name == "MY_DB"
        assert result.vendor == "Snowflake"
        assert result.version_tuple == (8, 32, 0)

    def test_parse_database_info_empty_rows(self, introspector_mixin):
        result = introspector_mixin._parse_database_info([])
        assert isinstance(result, DatabaseInfo)
        assert result.vendor == "Snowflake"

    def test_parse_tables(self, introspector_mixin):
        rows = [
            {"TABLE_NAME": "users", "TABLE_TYPE": "BASE TABLE", "COMMENT": None},
            {"TABLE_NAME": "v_users", "TABLE_TYPE": "VIEW", "COMMENT": "user view"},
        ]
        result = introspector_mixin._parse_tables(rows, "PUBLIC")
        assert len(result) == 2
        assert result[0].name == "users"
        assert result[0].table_type == TableType.BASE_TABLE
        assert result[1].name == "v_users"
        assert result[1].table_type == TableType.VIEW
        assert result[1].comment == "user view"

    def test_parse_columns(self, introspector_mixin):
        rows = [
            {
                "COLUMN_NAME": "id",
                "ORDINAL_POSITION": 1,
                "COLUMN_DEFAULT": None,
                "IS_NULLABLE": "NO",
                "DATA_TYPE": "NUMBER",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "NUMERIC_PRECISION": 38,
                "NUMERIC_SCALE": 0,
                "COLLATION_NAME": None,
                "COMMENT": None,
            },
            {
                "COLUMN_NAME": "name",
                "ORDINAL_POSITION": 2,
                "COLUMN_DEFAULT": None,
                "IS_NULLABLE": "YES",
                "DATA_TYPE": "VARCHAR",
                "CHARACTER_MAXIMUM_LENGTH": 16777216,
                "NUMERIC_PRECISION": None,
                "NUMERIC_SCALE": None,
                "COLLATION_NAME": "utf-8",
                "COMMENT": "user name",
            },
        ]
        result = introspector_mixin._parse_columns(rows, "users", "PUBLIC")
        assert len(result) == 2

        assert result[0].name == "id"
        assert result[0].data_type == "number"
        assert result[0].nullable == ColumnNullable.NOT_NULL
        assert result[0].numeric_precision == 38

        assert result[1].name == "name"
        assert result[1].data_type == "varchar"
        assert result[1].nullable == ColumnNullable.NULLABLE
        assert result[1].character_maximum_length == 16777216
        assert result[1].comment == "user name"

    def test_parse_indexes_as_constraints(self, introspector_mixin):
        """Snowflake maps PK/unique constraints to IndexInfo."""
        rows = [
            {"CONSTRAINT_NAME": "PK_USERS", "CONSTRAINT_TYPE": "PRIMARY KEY", "COLUMN_NAME": "id", "ORDINAL_POSITION": 1},
            {"CONSTRAINT_NAME": "UK_USERS_EMAIL", "CONSTRAINT_TYPE": "UNIQUE", "COLUMN_NAME": "email", "ORDINAL_POSITION": 1},
        ]
        result = introspector_mixin._parse_indexes(rows, "users", "PUBLIC")
        assert len(result) == 2

        pk = next(i for i in result if i.is_primary)
        assert pk.name == "PK_USERS"
        assert pk.is_unique is True
        assert len(pk.columns) == 1
        assert pk.columns[0].name == "id"

        uk = next(i for i in result if not i.is_primary)
        assert uk.name == "UK_USERS_EMAIL"
        assert uk.is_unique is True
        assert uk.columns[0].name == "email"

    def test_parse_foreign_keys(self, introspector_mixin):
        rows = [
            {
                "CONSTRAINT_NAME": "FK_ORDERS_USER",
                "UPDATE_RULE": "NO ACTION",
                "DELETE_RULE": "CASCADE",
                "COLUMN_NAME": "user_id",
                "ORDINAL_POSITION": 1,
                "REFERENCED_TABLE_NAME": "users",
                "REFERENCED_COLUMN_NAME": "id",
            },
        ]
        result = introspector_mixin._parse_foreign_keys(rows, "orders", "PUBLIC")
        assert len(result) == 1
        assert result[0].name == "FK_ORDERS_USER"
        assert result[0].columns == ["user_id"]
        assert result[0].referenced_table == "users"
        assert result[0].referenced_columns == ["id"]
        assert result[0].on_delete == ReferentialAction.CASCADE
        assert result[0].on_update == ReferentialAction.NO_ACTION

    def test_parse_composite_foreign_key(self, introspector_mixin):
        rows = [
            {
                "CONSTRAINT_NAME": "FK_ORDER_ITEMS",
                "UPDATE_RULE": "NO ACTION",
                "DELETE_RULE": "RESTRICT",
                "COLUMN_NAME": "order_id",
                "ORDINAL_POSITION": 1,
                "REFERENCED_TABLE_NAME": "orders",
                "REFERENCED_COLUMN_NAME": "id",
            },
            {
                "CONSTRAINT_NAME": "FK_ORDER_ITEMS",
                "UPDATE_RULE": "NO ACTION",
                "DELETE_RULE": "RESTRICT",
                "COLUMN_NAME": "product_id",
                "ORDINAL_POSITION": 2,
                "REFERENCED_TABLE_NAME": "orders",
                "REFERENCED_COLUMN_NAME": "product_id",
            },
        ]
        result = introspector_mixin._parse_foreign_keys(rows, "order_items", "PUBLIC")
        assert len(result) == 1
        assert result[0].columns == ["order_id", "product_id"]
        assert result[0].referenced_columns == ["id", "product_id"]

    def test_parse_views(self, introspector_mixin):
        rows = [
            {
                "TABLE_NAME": "v_active_users",
                "VIEW_DEFINITION": "SELECT * FROM users WHERE active = TRUE",
                "CHECK_OPTION": "NONE",
                "IS_UPDATABLE": "NO",
            },
        ]
        result = introspector_mixin._parse_views(rows, "PUBLIC")
        assert len(result) == 1
        assert result[0].name == "v_active_users"
        assert result[0].definition == "SELECT * FROM users WHERE active = TRUE"
        assert result[0].is_updatable is False

    def test_parse_view_info(self, introspector_mixin):
        rows = [
            {
                "TABLE_NAME": "v_active_users",
                "VIEW_DEFINITION": "SELECT * FROM users WHERE active = TRUE",
                "CHECK_OPTION": "NONE",
                "IS_UPDATABLE": "NO",
            },
        ]
        result = introspector_mixin._parse_view_info(rows, "v_active_users", "PUBLIC")
        assert result is not None
        assert result.name == "v_active_users"

    def test_parse_view_info_not_found(self, introspector_mixin):
        result = introspector_mixin._parse_view_info([], "nonexistent", "PUBLIC")
        assert result is None

    def test_parse_triggers_always_empty(self, introspector_mixin):
        """Snowflake doesn't support triggers."""
        result = introspector_mixin._parse_triggers([], "PUBLIC")
        assert result == []


# ================================================================== #
# Tests for SyncSnowflakeIntrospector with mock executor
# ================================================================== #

class TestSyncSnowflakeIntrospector:
    """Test SyncSnowflakeIntrospector end-to-end with mock executor."""

    @pytest.fixture
    def mock_backend(self):
        backend = MagicMock()
        backend._version = (8, 32, 0)
        backend.config = MagicMock()
        backend.config.schema = "PUBLIC"
        backend.config.database = "MY_DB"
        backend.dialect = SnowflakeDialect(version=(8, 32, 0))
        return backend

    @pytest.fixture
    def mock_executor(self):
        return MagicMock(spec=SyncIntrospectorExecutor)

    @pytest.fixture
    def introspector(self, mock_backend, mock_executor):
        return SyncSnowflakeIntrospector(mock_backend, mock_executor)

    def test_get_default_schema(self, introspector):
        assert introspector._get_default_schema() == "PUBLIC"

    def test_get_database_info(self, introspector, mock_executor):
        mock_executor.execute.return_value = [
            {"CATALOG_NAME": "MY_DB", "SERVER_VERSION": "8.32.0"},
        ]
        info = introspector.get_database_info()
        assert isinstance(info, DatabaseInfo)
        assert info.vendor == "Snowflake"
        assert info.name == "MY_DB"
        mock_executor.execute.assert_called_once()

    def test_list_tables(self, introspector, mock_executor):
        mock_executor.execute.return_value = [
            {"TABLE_NAME": "users", "TABLE_TYPE": "BASE TABLE", "COMMENT": None},
        ]
        tables = introspector.list_tables()
        assert len(tables) == 1
        assert tables[0].name == "users"

    def test_list_columns(self, introspector, mock_executor):
        mock_executor.execute.return_value = [
            {
                "COLUMN_NAME": "id",
                "ORDINAL_POSITION": 1,
                "COLUMN_DEFAULT": None,
                "IS_NULLABLE": "NO",
                "DATA_TYPE": "NUMBER",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "NUMERIC_PRECISION": 38,
                "NUMERIC_SCALE": 0,
                "COLLATION_NAME": None,
                "COMMENT": None,
            },
        ]
        columns = introspector.list_columns("users")
        assert len(columns) == 1
        assert columns[0].name == "id"

    def test_caching(self, introspector, mock_executor):
        """Test that results are cached and not re-queried."""
        mock_executor.execute.return_value = [
            {"CATALOG_NAME": "MY_DB", "SERVER_VERSION": "8.32.0"},
        ]
        # First call
        introspector.get_database_info()
        # Second call should use cache
        introspector.get_database_info()
        # Executor should only be called once
        assert mock_executor.execute.call_count == 1


# ================================================================== #
# Tests for AsyncSnowflakeIntrospector with mock executor
# ================================================================== #

class TestAsyncSnowflakeIntrospector:
    """Test AsyncSnowflakeIntrospector with mock async executor."""

    @pytest.fixture
    def mock_backend(self):
        backend = MagicMock()
        backend._version = (8, 32, 0)
        backend.config = MagicMock()
        backend.config.schema = "PUBLIC"
        backend.config.database = "MY_DB"
        backend.dialect = SnowflakeDialect(version=(8, 32, 0))
        return backend

    @pytest.fixture
    def mock_executor(self):
        executor = MagicMock()
        executor.execute = AsyncMock(return_value=[
            {"CATALOG_NAME": "MY_DB", "SERVER_VERSION": "8.32.0"},
        ])
        return executor

    @pytest.fixture
    def introspector(self, mock_backend, mock_executor):
        return AsyncSnowflakeIntrospector(mock_backend, mock_executor)

    @pytest.mark.asyncio
    async def test_get_database_info(self, introspector, mock_executor):
        info = await introspector.get_database_info()
        assert isinstance(info, DatabaseInfo)
        assert info.vendor == "Snowflake"

    @pytest.mark.asyncio
    async def test_list_tables(self, introspector, mock_executor):
        mock_executor.execute.return_value = [
            {"TABLE_NAME": "users", "TABLE_TYPE": "BASE TABLE", "COMMENT": None},
        ]
        tables = await introspector.list_tables()
        assert len(tables) == 1

    @pytest.mark.asyncio
    async def test_caching(self, introspector, mock_executor):
        """Test async caching works the same as sync."""
        await introspector.get_database_info()
        await introspector.get_database_info()
        assert mock_executor.execute.call_count == 1


# ================================================================== #
# Tests for _SnowflakeAsyncIntrospectorExecutor
# ================================================================== #

class TestSnowflakeAsyncExecutor:
    """Test the custom async executor that wraps sync cursor operations."""

    @pytest.mark.asyncio
    async def test_execute_returns_rows(self):
        from rhosocial.activerecord.backend.impl.snowflake.introspection.introspector import (
            _SnowflakeAsyncIntrospectorExecutor,
        )

        mock_cursor = MagicMock()
        mock_cursor.description = [("COL1",), ("COL2",)]
        mock_cursor.fetchall.return_value = [(1, "a"), (2, "b")]
        mock_cursor.close = MagicMock()

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_backend = MagicMock()
        mock_backend._connection = mock_connection
        mock_backend._executor = None

        executor = _SnowflakeAsyncIntrospectorExecutor(mock_backend)
        result = await executor.execute("SELECT * FROM t", ())

        assert len(result) == 2
        assert result[0] == {"COL1": 1, "COL2": "a"}
        assert result[1] == {"COL1": 2, "COL2": "b"}
        mock_cursor.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_no_description(self):
        from rhosocial.activerecord.backend.impl.snowflake.introspection.introspector import (
            _SnowflakeAsyncIntrospectorExecutor,
        )

        mock_cursor = MagicMock()
        mock_cursor.description = None
        mock_cursor.close = MagicMock()

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_backend = MagicMock()
        mock_backend._connection = mock_connection
        mock_backend._executor = None

        executor = _SnowflakeAsyncIntrospectorExecutor(mock_backend)
        result = await executor.execute("INSERT INTO t VALUES (1)", ())

        assert result == []
        mock_cursor.close.assert_called_once()
