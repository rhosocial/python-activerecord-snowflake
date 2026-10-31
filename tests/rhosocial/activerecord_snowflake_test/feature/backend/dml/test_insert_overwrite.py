# tests/rhosocial/activerecord_snowflake_test/feature/backend/dml/test_insert_overwrite.py
"""Tests for Snowflake INSERT OVERWRITE support.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.expression import (
    Column,
    InsertStatement,
    Literal,
    QueryStatement,
    SelectSource,
    ValuesSource,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeInsertExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeDMLSupport,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


@pytest.fixture
def select_source(dialect):
    query = QueryStatement(
        dialect,
        select=[Column(dialect, "id"), Column(dialect, "name")],
        from_=Table(dialect, "src"),
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
        expr = SnowflakeInsertExpression(
            dialect,
            into=Table(dialect, "t"),
            source=select_source,
            columns=["id", "name"],
            overwrite=True,
        )
        sql, params = expr.to_sql()
        assert sql == (
            'INSERT OVERWRITE INTO "t" ("id", "name") '
            'SELECT "id", "name" FROM "src"'
        )
        assert params == ()

    def test_insert_overwrite_standalone(self, dialect, select_source):
        expr = InsertStatement(
            dialect, into=Table(dialect, "t"), source=select_source, columns=["id", "name"]
        )
        sql, _ = dialect.format_insert_overwrite_statement(expr)
        assert sql.startswith("INSERT OVERWRITE INTO ")

    def test_plain_insert_unchanged(self, dialect, select_source):
        expr = InsertStatement(
            dialect, into=Table(dialect, "t"), source=select_source, columns=["id", "name"]
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
        expr = SnowflakeInsertExpression(
            dialect,
            into=Table(dialect, "t"),
            source=ValuesSource(dialect, values),
            overwrite=True,
        )
        sql, params = expr.to_sql()
        assert sql == (
            'INSERT OVERWRITE INTO "t"  VALUES (%s, %s), (%s, %s)'
        )
        assert params == (1, "a", 2, "b")


class TestBareHostValueCellsBindThroughDelegation:
    """VALUES cells may be bare host values; the override delegates, so they bind.

    Core collects the expression-versus-host-value judgment in one place, and
    ``SnowflakeDMLMixin.format_insert_statement`` delegates both of its paths
    to the core renderer -- the plain path outright, the overwrite path by
    rewriting the prefix of what the core renderer produced. A bare scalar
    cell must therefore bind behind %s exactly as a ``Literal`` cell does, on
    both paths, without the prefix rewrite disturbing the parameters.
    """

    def test_plain_insert_binds_bare_cells(self, dialect):
        expr = InsertStatement(
            dialect,
            into=Table(dialect, "t"),
            source=ValuesSource(dialect, [[1, "a"], [2, "b"]]),
            columns=["id", "name"],
        )
        sql, params = expr.to_sql()
        assert sql == 'INSERT INTO "t" ("id", "name") VALUES (%s, %s), (%s, %s)'
        assert params == (1, "a", 2, "b")

    def test_overwrite_insert_binds_bare_cells(self, dialect):
        expr = SnowflakeInsertExpression(
            dialect,
            into=Table(dialect, "t"),
            source=ValuesSource(dialect, [[1, "a"], [2, "b"]]),
            overwrite=True,
        )
        sql, params = expr.to_sql()
        assert sql == 'INSERT OVERWRITE INTO "t"  VALUES (%s, %s), (%s, %s)'
        assert params == (1, "a", 2, "b")

    def test_mixed_cells_bind_in_written_order(self, dialect):
        expr = InsertStatement(
            dialect,
            into=Table(dialect, "t"),
            source=ValuesSource(dialect, [[Literal(dialect, 3), "c"]]),
        )
        sql, params = expr.to_sql()
        assert sql == 'INSERT INTO "t"  VALUES (%s, %s)'
        assert params == (3, "c")
