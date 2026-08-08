"""Tests for Snowflake INSERT OVERWRITE support.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.expression import (
    Column,
    InsertExpression,
    Literal,
    QueryExpression,
    SelectSource,
    TableExpression,
    ValuesSource,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeDMLSupport,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


@pytest.fixture
def select_source(dialect):
    query = QueryExpression(
        dialect,
        select=[Column(dialect, "id"), Column(dialect, "name")],
        from_=TableExpression(dialect, "src"),
    )
    return SelectSource(dialect, query)


class TestSnowflakeDMLProtocol:
    """Dialect satisfies isinstance checks for the DML protocol."""

    def test_dialect_is_dml_support(self, dialect):
        assert isinstance(dialect, SnowflakeDMLSupport)

    def test_supports_insert_overwrite(self, dialect):
        assert dialect.supports_insert_overwrite() is True


class TestSnowflakeInsertOverwrite:
    """INSERT OVERWRITE statement generation."""

    def test_insert_overwrite_via_dialect_option(self, dialect, select_source):
        expr = InsertExpression(
            dialect,
            into="t",
            source=select_source,
            columns=["id", "name"],
            dialect_options={"overwrite": True},
        )
        sql, params = expr.to_sql()
        assert sql == (
            'INSERT OVERWRITE INTO "t" ("id", "name") '
            'SELECT "id", "name" FROM "src"'
        )
        assert params == ()

    def test_insert_overwrite_standalone(self, dialect, select_source):
        expr = InsertExpression(
            dialect, into="t", source=select_source, columns=["id", "name"]
        )
        sql, _ = dialect.format_insert_overwrite_statement(expr)
        assert sql.startswith("INSERT OVERWRITE INTO ")

    def test_plain_insert_unchanged(self, dialect, select_source):
        expr = InsertExpression(
            dialect, into="t", source=select_source, columns=["id", "name"]
        )
        sql, _ = expr.to_sql()
        assert sql.startswith("INSERT INTO ")

    def test_insert_overwrite_values_source(self, dialect):
        values = [
            [
                Literal(dialect, 1),
                Literal(dialect, "a"),
            ],
            [
                Literal(dialect, 2),
                Literal(dialect, "b"),
            ],
        ]
        expr = InsertExpression(
            dialect,
            into="t",
            source=ValuesSource(dialect, values),
            dialect_options={"overwrite": True},
        )
        sql, params = expr.to_sql()
        assert sql == (
            'INSERT OVERWRITE INTO "t"  VALUES (%s, %s), (%s, %s)'
        )
        assert params == (1, "a", 2, "b")
