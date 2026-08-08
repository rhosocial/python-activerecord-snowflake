"""Tests for Snowflake PIVOT / UNPIVOT clause support.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakePivotSupport,
)
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakePivotExpression,
    SnowflakeUnpivotExpression,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakePivotProtocol:
    """Dialect satisfies isinstance checks for the pivot protocol."""

    def test_dialect_is_pivot_support(self, dialect):
        assert isinstance(dialect, SnowflakePivotSupport)

    def test_supports_pivot(self, dialect):
        assert dialect.supports_pivot() is True

    def test_supports_unpivot(self, dialect):
        assert dialect.supports_unpivot() is True


class TestSnowflakePivot:
    """PIVOT clause generation."""

    def test_pivot_string_values(self, dialect):
        expr = SnowflakePivotExpression(
            dialect,
            aggregate_function="SUM",
            aggregate_column="v",
            pivot_column="c",
            values=["a", "b"],
        )
        sql, params = expr.to_sql()
        assert sql == "PIVOT (SUM(\"v\") FOR \"c\" IN ('a', 'b'))"
        assert params == ()

    def test_pivot_numeric_values(self, dialect):
        expr = SnowflakePivotExpression(
            dialect,
            aggregate_function="COUNT",
            aggregate_column="v",
            pivot_column="c",
            values=[1, 2, 3],
        )
        sql, _ = expr.to_sql()
        assert sql == 'PIVOT (COUNT("v") FOR "c" IN (1, 2, 3))'

    def test_pivot_with_alias(self, dialect):
        expr = SnowflakePivotExpression(
            dialect,
            aggregate_function="SUM",
            aggregate_column="v",
            pivot_column="c",
            values=["a", "b"],
            alias="p",
        )
        sql, _ = expr.to_sql()
        assert sql == 'PIVOT (SUM("v") FOR "c" IN (\'a\', \'b\')) "p"'

    def test_pivot_value_string_escaped(self, dialect):
        expr = SnowflakePivotExpression(
            dialect,
            aggregate_function="SUM",
            aggregate_column="v",
            pivot_column="c",
            values=["o'brien"],
        )
        sql, _ = expr.to_sql()
        assert "IN ('o''brien')" in sql


class TestSnowflakeUnpivot:
    """UNPIVOT clause generation."""

    def test_unpivot_exclude_nulls(self, dialect):
        expr = SnowflakeUnpivotExpression(
            dialect,
            value_column="val",
            pivot_column="col",
            columns=["a", "b"],
        )
        sql, params = expr.to_sql()
        assert sql == 'UNPIVOT EXCLUDE NULLS ("val" FOR "col" IN ("a", "b"))'
        assert params == ()

    def test_unpivot_include_nulls(self, dialect):
        expr = SnowflakeUnpivotExpression(
            dialect,
            value_column="val",
            pivot_column="col",
            columns=["a", "b"],
            include_nulls=True,
        )
        sql, _ = expr.to_sql()
        assert sql == 'UNPIVOT INCLUDE NULLS ("val" FOR "col" IN ("a", "b"))'

    def test_unpivot_with_alias(self, dialect):
        expr = SnowflakeUnpivotExpression(
            dialect,
            value_column="val",
            pivot_column="col",
            columns=["a", "b"],
            alias="u",
        )
        sql, _ = expr.to_sql()
        assert sql == 'UNPIVOT EXCLUDE NULLS ("val" FOR "col" IN ("a", "b")) "u"'


class TestSnowflakePivotClauseUsage:
    """PIVOT / UNPIVOT clauses rendered inside a SELECT statement."""

    def test_select_with_pivot(self, dialect):
        expr = SnowflakePivotExpression(
            dialect,
            aggregate_function="SUM",
            aggregate_column="v",
            pivot_column="c",
            values=["a", "b"],
            alias="p",
        )
        sql = f"SELECT * FROM t {expr.to_sql()[0]}"
        assert sql == "SELECT * FROM t PIVOT (SUM(\"v\") FOR \"c\" IN ('a', 'b')) \"p\""

    def test_select_with_unpivot(self, dialect):
        expr = SnowflakeUnpivotExpression(
            dialect,
            value_column="val",
            pivot_column="col",
            columns=["a", "b"],
            alias="u",
        )
        sql = f"SELECT * FROM t {expr.to_sql()[0]}"
        assert sql == "SELECT * FROM t UNPIVOT EXCLUDE NULLS (\"val\" FOR \"col\" IN (\"a\", \"b\")) \"u\""
