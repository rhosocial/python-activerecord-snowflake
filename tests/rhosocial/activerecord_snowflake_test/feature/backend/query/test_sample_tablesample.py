# tests/rhosocial/activerecord_snowflake_test/feature/backend/query/test_sample_tablesample.py
"""Tests for Snowflake SAMPLE / TABLESAMPLE clause support.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeSampleSupport,
)
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeSampleExpression,
    SnowflakeSampleForm,
    SnowflakeSamplingMethod,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeSampleProtocol:
    """Dialect satisfies isinstance checks for the sample protocol."""

    def test_dialect_is_sample_support(self, dialect):
        assert isinstance(dialect, SnowflakeSampleSupport)

    def test_supports_sample(self, dialect):
        assert dialect.supports_sample() is True

    def test_supports_tablesample(self, dialect):
        assert dialect.supports_tablesample() is True


class TestSnowflakeSampleClause:
    """SAMPLE clause generation."""

    def test_sample_row_count(self, dialect):
        expr = SnowflakeSampleExpression(dialect, 10)
        sql, params = expr.to_sql()
        assert sql == "SAMPLE (10 ROWS)"
        assert params == ()

    def test_sample_percentage_float(self, dialect):
        expr = SnowflakeSampleExpression(dialect, 0.5)
        sql, _ = expr.to_sql()
        assert sql == "SAMPLE (0.5)"

    def test_sample_percentage_flag(self, dialect):
        expr = SnowflakeSampleExpression(dialect, 5, is_percent=True)
        sql, _ = expr.to_sql()
        assert sql == "SAMPLE (5)"

    def test_sample_with_repeatable_seed(self, dialect):
        expr = SnowflakeSampleExpression(dialect, 10, seed=42)
        sql, _ = expr.to_sql()
        assert sql == "SAMPLE (10 ROWS) REPEATABLE (42)"

    def test_sample_repeatable_with_percentage(self, dialect):
        expr = SnowflakeSampleExpression(dialect, 0.5, seed=7)
        sql, _ = expr.to_sql()
        assert sql == "SAMPLE (0.5) REPEATABLE (7)"


class TestSnowflakeTableSampleClause:
    """TABLESAMPLE clause generation."""

    def test_tablesample_bernoulli(self, dialect):
        expr = SnowflakeSampleExpression(
            dialect,
            10,
            form=SnowflakeSampleForm.TABLESAMPLE,
            sampling_method=SnowflakeSamplingMethod.BERNOULLI,
        )
        sql, params = expr.to_sql()
        assert sql == "TABLESAMPLE BERNOULLI (10 ROWS)"
        assert params == ()

    def test_tablesample_system_percentage(self, dialect):
        expr = SnowflakeSampleExpression(
            dialect,
            0.5,
            form=SnowflakeSampleForm.TABLESAMPLE,
            sampling_method=SnowflakeSamplingMethod.SYSTEM,
        )
        sql, _ = expr.to_sql()
        assert sql == "TABLESAMPLE SYSTEM (0.5)"

    def test_tablesample_without_method(self, dialect):
        expr = SnowflakeSampleExpression(
            dialect, 10, form=SnowflakeSampleForm.TABLESAMPLE
        )
        sql, _ = expr.to_sql()
        assert sql == "TABLESAMPLE (10 ROWS)"


class TestSnowflakeSampleClauseUsage:
    """SAMPLE clause rendered inside a SELECT statement."""

    def test_select_with_sample_row_count(self, dialect):
        expr = SnowflakeSampleExpression(dialect, 10)
        sql = f"SELECT * FROM t {expr.to_sql()[0]}"
        assert sql == "SELECT * FROM t SAMPLE (10 ROWS)"

    def test_select_with_tablesample(self, dialect):
        expr = SnowflakeSampleExpression(
            dialect,
            0.5,
            form=SnowflakeSampleForm.TABLESAMPLE,
            sampling_method=SnowflakeSamplingMethod.SYSTEM,
        )
        sql = f"SELECT * FROM t {expr.to_sql()[0]}"
        assert sql == "SELECT * FROM t TABLESAMPLE SYSTEM (0.5)"
