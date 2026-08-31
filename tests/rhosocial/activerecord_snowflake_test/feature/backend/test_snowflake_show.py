"""Tests for Snowflake SHOW statement support.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeShowSupport,
)
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeShowExpression,
    SnowflakeShowObjectType,
    SnowflakeShowScope,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeShowProtocol:
    """Dialect satisfies isinstance checks for the show protocol."""

    def test_dialect_is_show_support(self, dialect):
        assert isinstance(dialect, SnowflakeShowSupport)

    def test_supports_show(self, dialect):
        assert dialect.supports_show() is True


class TestSnowflakeShowBasic:
    """SHOW statement generation for every object type."""

    @pytest.mark.parametrize(
        "object_type, expected",
        [
            (SnowflakeShowObjectType.TABLES, "SHOW TABLES"),
            (SnowflakeShowObjectType.VIEWS, "SHOW VIEWS"),
            (SnowflakeShowObjectType.SCHEMAS, "SHOW SCHEMAS"),
            (SnowflakeShowObjectType.DATABASES, "SHOW DATABASES"),
            (SnowflakeShowObjectType.WAREHOUSES, "SHOW WAREHOUSES"),
            (SnowflakeShowObjectType.STAGES, "SHOW STAGES"),
            (SnowflakeShowObjectType.TASKS, "SHOW TASKS"),
            (SnowflakeShowObjectType.PIPES, "SHOW PIPES"),
            (SnowflakeShowObjectType.STREAMS, "SHOW STREAMS"),
            (SnowflakeShowObjectType.FILE_FORMATS, "SHOW FILE FORMATS"),
            (SnowflakeShowObjectType.SEQUENCES, "SHOW SEQUENCES"),
            (SnowflakeShowObjectType.USERS, "SHOW USERS"),
            (SnowflakeShowObjectType.ROLES, "SHOW ROLES"),
            (SnowflakeShowObjectType.FUNCTIONS, "SHOW FUNCTIONS"),
            (SnowflakeShowObjectType.PROCEDURES, "SHOW PROCEDURES"),
            (SnowflakeShowObjectType.COLUMNS, "SHOW COLUMNS"),
        ],
    )
    def test_show_object_type(self, dialect, object_type, expected):
        expr = SnowflakeShowExpression(dialect, object_type)
        sql, params = expr.to_sql()
        assert sql == expected
        assert params == ()


class TestSnowflakeShowScope:
    """SHOW statement IN scope generation."""

    def test_show_in_schema_with_name(self, dialect):
        expr = SnowflakeShowExpression(
            dialect,
            SnowflakeShowObjectType.TABLES,
            in_scope=SnowflakeShowScope.SCHEMA,
            in_name="my_schema",
        )
        sql, _ = expr.to_sql()
        assert sql == 'SHOW TABLES IN SCHEMA "my_schema"'

    def test_show_in_schema_no_name(self, dialect):
        expr = SnowflakeShowExpression(
            dialect,
            SnowflakeShowObjectType.TABLES,
            in_scope=SnowflakeShowScope.SCHEMA,
        )
        sql, _ = expr.to_sql()
        assert sql == "SHOW TABLES IN SCHEMA"

    def test_show_in_database_with_name(self, dialect):
        expr = SnowflakeShowExpression(
            dialect,
            SnowflakeShowObjectType.SCHEMAS,
            in_scope=SnowflakeShowScope.DATABASE,
            in_name="my_db",
        )
        sql, _ = expr.to_sql()
        assert sql == 'SHOW SCHEMAS IN DATABASE "my_db"'

    def test_show_in_account(self, dialect):
        expr = SnowflakeShowExpression(
            dialect,
            SnowflakeShowObjectType.ROLES,
            in_scope=SnowflakeShowScope.ACCOUNT,
        )
        sql, _ = expr.to_sql()
        assert sql == "SHOW ROLES IN ACCOUNT"


class TestSnowflakeShowFilters:
    """SHOW statement LIKE / LIMIT generation."""

    def test_show_like(self, dialect):
        expr = SnowflakeShowExpression(
            dialect,
            SnowflakeShowObjectType.TABLES,
            like="emp%",
        )
        sql, _ = expr.to_sql()
        assert sql == "SHOW TABLES LIKE 'emp%'"

    def test_show_like_escaped(self, dialect):
        expr = SnowflakeShowExpression(
            dialect,
            SnowflakeShowObjectType.TABLES,
            like="it's",
        )
        sql, _ = expr.to_sql()
        assert sql == "SHOW TABLES LIKE 'it''s'"

    def test_show_limit(self, dialect):
        expr = SnowflakeShowExpression(
            dialect,
            SnowflakeShowObjectType.TABLES,
            limit=100,
        )
        sql, _ = expr.to_sql()
        assert sql == "SHOW TABLES LIMIT 100"

    def test_show_full_options(self, dialect):
        expr = SnowflakeShowExpression(
            dialect,
            SnowflakeShowObjectType.TABLES,
            in_scope=SnowflakeShowScope.SCHEMA,
            in_name="my_schema",
            like="emp%",
            limit=10,
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "SHOW TABLES LIKE 'emp%' IN SCHEMA \"my_schema\" LIMIT 10"
        )
