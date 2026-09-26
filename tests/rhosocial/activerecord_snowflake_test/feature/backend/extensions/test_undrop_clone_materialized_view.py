# tests/rhosocial/activerecord_snowflake_test/feature/backend/extensions/test_undrop_clone_materialized_view.py
"""Tests for Snowflake UNDROP / CLONE / MATERIALIZED VIEW DDL support.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import Column, QueryExpression, TableExpression
from rhosocial.activerecord.backend.expression.statements.ddl_view import (
    CreateMaterializedViewExpression,
)
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


class TestSnowflakeGenericMaterializedViewInterop:
    """The core MV expression must render on Snowflake.

    ``SnowflakeCreateMaterializedViewExpression`` extends the core expression, so
    a backend advertising ``supports_materialized_view()`` has to work with the
    generic API too. Previously the formatter read ``expr.as_query`` only, and
    the generic expression raised ``AttributeError``.
    """

    def _query(self, dialect):
        return QueryExpression(
            dialect=dialect,
            select=[Column(dialect, "c1")],
            from_=TableExpression(dialect, "t"),
        )

    def test_generic_expression_renders(self, dialect):
        expr = CreateMaterializedViewExpression(
            dialect=dialect, view_name="mv", query=self._query(dialect)
        )
        sql, params = expr.to_sql()
        assert sql.startswith('CREATE MATERIALIZED VIEW "mv" AS SELECT')
        assert params == ()

    def test_generic_expression_with_column_aliases(self, dialect):
        expr = CreateMaterializedViewExpression(
            dialect=dialect,
            view_name="mv",
            query=self._query(dialect),
            column_aliases=["alias_c1"],
        )
        sql, _ = expr.to_sql()
        assert '("alias_c1")' in sql

    def test_generic_expression_requires_query(self, dialect):
        expr = CreateMaterializedViewExpression(
            dialect=dialect, view_name="mv", query=None
        )
        with pytest.raises(ValueError):
            expr.to_sql()

    def test_snowflake_expression_accepts_core_field_names(self, dialect):
        """The core vocabulary (view_name/query) works on the Snowflake expression."""
        expr = SnowflakeCreateMaterializedViewExpression(
            dialect, view_name="mv", query=self._query(dialect)
        )
        sql, _ = expr.to_sql()
        assert sql.startswith('CREATE MATERIALIZED VIEW "mv" AS SELECT')

    def test_snowflake_expression_accepts_raw_query_string(self, dialect):
        expr = SnowflakeCreateMaterializedViewExpression(
            dialect, "mv", as_query="SELECT 1"
        )
        sql, _ = expr.to_sql()
        assert sql == 'CREATE MATERIALIZED VIEW "mv" AS SELECT 1'

    def test_field_name_aliases(self, dialect):
        expr = SnowflakeCreateMaterializedViewExpression(
            dialect, "mv", as_query="SELECT 1", column_list=["a"]
        )
        assert expr.name == expr.view_name == "mv"
        assert expr.as_query == "SELECT 1"
        assert expr.column_list == expr.column_aliases == ["a"]

    def test_or_replace_and_if_not_exists_are_exclusive(self, dialect):
        with pytest.raises(ValueError):
            SnowflakeCreateMaterializedViewExpression(
                dialect, "mv", as_query="SELECT 1", or_replace=True, if_not_exists=True
            )

    def test_view_name_is_required(self, dialect):
        with pytest.raises(ValueError):
            SnowflakeCreateMaterializedViewExpression(dialect, as_query="SELECT 1")

    def test_tablespace_is_rejected(self, dialect):
        """Snowflake has no TABLESPACE — refuse instead of dropping the clause."""
        expr = SnowflakeCreateMaterializedViewExpression(
            dialect, "mv", as_query="SELECT 1", tablespace="fast_ssd"
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_storage_options_are_rejected(self, dialect):
        expr = SnowflakeCreateMaterializedViewExpression(
            dialect, "mv", as_query="SELECT 1", storage_options={"fillfactor": 70}
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_with_data_is_not_rendered(self, dialect):
        """Snowflake has no WITH [NO] DATA; the inherited flag must not leak out."""
        expr = CreateMaterializedViewExpression(
            dialect=dialect,
            view_name="mv",
            query=self._query(dialect),
            with_data=False,
        )
        sql, _ = expr.to_sql()
        assert "WITH DATA" not in sql
        assert "WITH NO DATA" not in sql
