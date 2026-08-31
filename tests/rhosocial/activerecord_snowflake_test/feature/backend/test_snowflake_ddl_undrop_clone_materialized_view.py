"""Tests for Snowflake UNDROP / CLONE / MATERIALIZED VIEW DDL support.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeCloneSupport,
    SnowflakeMaterializedViewSupport,
    SnowflakeUndropSupport,
)
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeCreateMaterializedViewExpression,
    SnowflakeUndropExpression,
    SnowflakeUndropObjectType,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeUndropProtocol:
    """Dialect satisfies isinstance checks for the undrop protocol."""

    def test_dialect_is_undrop_support(self, dialect):
        assert isinstance(dialect, SnowflakeUndropSupport)

    def test_supports_undrop(self, dialect):
        assert dialect.supports_undrop() is True


class TestSnowflakeUndrop:
    """UNDROP statement generation."""

    def test_undrop_table(self, dialect):
        expr = SnowflakeUndropExpression(
            dialect, "t", object_type=SnowflakeUndropObjectType.TABLE
        )
        sql, params = expr.to_sql()
        assert sql == 'UNDROP TABLE "t"'
        assert params == ()

    def test_undrop_schema(self, dialect):
        expr = SnowflakeUndropExpression(
            dialect, "s", object_type=SnowflakeUndropObjectType.SCHEMA
        )
        sql, _ = expr.to_sql()
        assert sql == 'UNDROP SCHEMA "s"'

    def test_undrop_database(self, dialect):
        expr = SnowflakeUndropExpression(
            dialect, "d", object_type=SnowflakeUndropObjectType.DATABASE
        )
        sql, _ = expr.to_sql()
        assert sql == 'UNDROP DATABASE "d"'

    def test_undrop_defaults_to_table(self, dialect):
        expr = SnowflakeUndropExpression(dialect, "t")
        sql, _ = expr.to_sql()
        assert sql == 'UNDROP TABLE "t"'


class TestSnowflakeCloneProtocol:
    """Dialect satisfies isinstance checks for the clone protocol."""

    def test_dialect_is_clone_support(self, dialect):
        assert isinstance(dialect, SnowflakeCloneSupport)

    def test_supports_clone(self, dialect):
        assert dialect.supports_clone() is True


class TestSnowflakeClone:
    """CREATE TABLE / SCHEMA / DATABASE ... CLONE generation."""

    def test_clone_table_backward_compatible(self, dialect):
        assert (
            dialect.format_clone_table("new_table", "source_table")
            == "CREATE TABLE new_table CLONE source_table"
        )

    def test_clone_schema(self, dialect):
        assert (
            dialect.format_clone_schema("s2", "s1")
            == "CREATE SCHEMA s2 CLONE s1"
        )

    def test_clone_database(self, dialect):
        assert (
            dialect.format_clone_database("d2", "d1")
            == "CREATE DATABASE d2 CLONE d1"
        )


class TestSnowflakeMaterializedViewProtocol:
    """Dialect satisfies isinstance checks for the materialized view protocol."""

    def test_dialect_is_materialized_view_support(self, dialect):
        assert isinstance(dialect, SnowflakeMaterializedViewSupport)

    def test_supports_materialized_view(self, dialect):
        assert dialect.supports_materialized_view() is True


class TestSnowflakeCreateMaterializedView:
    """CREATE [OR REPLACE] MATERIALIZED VIEW statement generation."""

    def test_create_materialized_view_basic(self, dialect):
        expr = SnowflakeCreateMaterializedViewExpression(
            dialect, "mv", as_query="SELECT c1, SUM(c2) FROM t GROUP BY c1"
        )
        sql, params = expr.to_sql()
        assert sql == (
            'CREATE MATERIALIZED VIEW "mv" AS '
            "SELECT c1, SUM(c2) FROM t GROUP BY c1"
        )
        assert params == ()

    def test_create_materialized_view_or_replace(self, dialect):
        expr = SnowflakeCreateMaterializedViewExpression(
            dialect, "mv", or_replace=True, as_query="SELECT 1"
        )
        sql, _ = expr.to_sql()
        assert sql == 'CREATE OR REPLACE MATERIALIZED VIEW "mv" AS SELECT 1'

    def test_create_materialized_view_cluster_by(self, dialect):
        expr = SnowflakeCreateMaterializedViewExpression(
            dialect,
            "mv",
            cluster_by=["c1"],
            as_query="SELECT c1, c2 FROM t",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE MATERIALIZED VIEW "mv" CLUSTER BY ("c1") '
            "AS SELECT c1, c2 FROM t"
        )

    def test_create_materialized_view_column_list(self, dialect):
        expr = SnowflakeCreateMaterializedViewExpression(
            dialect,
            "mv",
            column_list=["a", "b"],
            as_query="SELECT c1, c2 FROM t",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE MATERIALIZED VIEW "mv" ("a", "b") '
            "AS SELECT c1, c2 FROM t"
        )

    def test_create_materialized_view_requires_as_query(self, dialect):
        expr = SnowflakeCreateMaterializedViewExpression(dialect, "mv")
        with pytest.raises(ValueError):
            expr.to_sql()
