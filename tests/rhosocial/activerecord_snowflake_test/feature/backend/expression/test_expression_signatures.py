# tests/rhosocial/activerecord_snowflake_test/feature/backend/expression/test_expression_signatures.py
"""Tests for Snowflake expression class signatures and format method compliance.

Verifies that each expression class can be instantiated and produces the
expected SQL when passed to the corresponding dialect format method.
"""
import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.warehouse import (
    SnowflakeCreateWarehouseExpression,
    SnowflakeAlterWarehouseExpression,
    SnowflakeAlterWarehouseMode,
    SnowflakeDropWarehouseExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.warehouse_options import (
    SnowflakeWarehouseOptionsExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.variant import (
    SnowflakeVariantPathAccessExpression,
    SnowflakeVariantCastExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.undrop import (
    SnowflakeUndropExpression,
    SnowflakeUndropObjectType,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestCreateWarehouseExpression:
    """Tests for SnowflakeCreateWarehouseExpression."""

    def test_create_warehouse_basic(self, dialect):
        expr = SnowflakeCreateWarehouseExpression(dialect, "my_wh")
        sql, _ = expr.to_sql()
        assert sql == 'CREATE WAREHOUSE "my_wh"'

    def test_create_warehouse_with_options(self, dialect):
        expr = SnowflakeCreateWarehouseExpression(
            dialect,
            "my_wh",
            or_replace=True,
            warehouse_size="X-SMALL",
            auto_suspend=300,
            auto_resume=True,
            comment="Test warehouse",
        )
        sql, _ = expr.to_sql()
        assert "CREATE OR REPLACE WAREHOUSE" in sql
        assert '"my_wh"' in sql
        assert "WAREHOUSE_SIZE = 'X-SMALL'" in sql
        assert "AUTO_SUSPEND = 300" in sql
        assert "AUTO_RESUME = TRUE" in sql
        assert "COMMENT = 'Test warehouse'" in sql


class TestAlterWarehouseExpression:
    """Tests for SnowflakeAlterWarehouseExpression."""

    def test_alter_warehouse_suspend(self, dialect):
        expr = SnowflakeAlterWarehouseExpression(
            dialect, "my_wh", mode=SnowflakeAlterWarehouseMode.SUSPEND
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER WAREHOUSE "my_wh" SUSPEND'

    def test_alter_warehouse_set(self, dialect):
        expr = SnowflakeAlterWarehouseExpression(
            dialect,
            "my_wh",
            mode=SnowflakeAlterWarehouseMode.SET,
            warehouse_size="LARGE",
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER WAREHOUSE "my_wh" SET WAREHOUSE_SIZE = \'LARGE\''


class TestDropWarehouseExpression:
    """Tests for SnowflakeDropWarehouseExpression."""

    def test_drop_warehouse_basic(self, dialect):
        expr = SnowflakeDropWarehouseExpression(dialect, "my_wh")
        sql, _ = expr.to_sql()
        assert sql == 'DROP WAREHOUSE "my_wh"'

    def test_drop_warehouse_if_exists(self, dialect):
        expr = SnowflakeDropWarehouseExpression(
            dialect, "my_wh", if_exists=True
        )
        sql, _ = expr.to_sql()
        assert sql == 'DROP WAREHOUSE IF EXISTS "my_wh"'


class TestWarehouseOptionsExpression:
    """Tests for SnowflakeWarehouseOptionsExpression."""

    def test_warehouse_options_all(self, dialect):
        expr = SnowflakeWarehouseOptionsExpression(
            dialect,
            warehouse_size="MEDIUM",
            max_cluster_count=4,
            min_cluster_count=2,
            scaling_policy="ECONOMY",
            auto_suspend=600,
            auto_resume=False,
            initially_suspended=True,
            comment="Options test",
        )
        joined, _ = expr.to_sql()
        assert "WAREHOUSE_SIZE = 'MEDIUM'" in joined
        assert "MAX_CLUSTER_COUNT = 4" in joined
        assert "MIN_CLUSTER_COUNT = 2" in joined
        assert "SCALING_POLICY = 'ECONOMY'" in joined
        assert "AUTO_SUSPEND = 600" in joined
        assert "AUTO_RESUME = FALSE" in joined
        assert "INITIALLY_SUSPENDED = TRUE" in joined
        assert "COMMENT = 'Options test'" in joined

    def test_warehouse_options_empty(self, dialect):
        expr = SnowflakeWarehouseOptionsExpression(dialect)
        sql, _ = expr.to_sql()
        assert sql == ""


class TestVariantPathAccessExpression:
    """Tests for SnowflakeVariantPathAccessExpression."""

    def test_variant_path_simple(self, dialect):
        expr = SnowflakeVariantPathAccessExpression(
            dialect, "data", "key"
        )
        sql, _ = expr.to_sql()
        assert sql == "data:key"

    def test_variant_path_nested(self, dialect):
        expr = SnowflakeVariantPathAccessExpression(
            dialect, "data", "key.nested.deep"
        )
        sql, _ = expr.to_sql()
        assert sql == "data:key.nested.deep"


class TestVariantCastExpression:
    """Tests for SnowflakeVariantCastExpression."""

    def test_variant_cast_number(self, dialect):
        expr = SnowflakeVariantCastExpression(
            dialect, "data", "count", "NUMBER"
        )
        sql, _ = expr.to_sql()
        assert sql == "data:count::NUMBER"

    def test_variant_cast_string(self, dialect):
        expr = SnowflakeVariantCastExpression(
            dialect, "data", "name", "VARCHAR"
        )
        sql, _ = expr.to_sql()
        assert sql == "data:name::VARCHAR"


class TestUndropExpression:
    """Tests for SnowflakeUndropExpression."""

    def test_undrop_table(self, dialect):
        expr = SnowflakeUndropExpression(dialect, "my_table")
        sql, _ = expr.to_sql()
        assert sql == 'UNDROP TABLE "my_table"'

    def test_undrop_schema(self, dialect):
        expr = SnowflakeUndropExpression(
            dialect, "my_schema", object_type=SnowflakeUndropObjectType.SCHEMA
        )
        sql, _ = expr.to_sql()
        assert sql == 'UNDROP SCHEMA "my_schema"'
