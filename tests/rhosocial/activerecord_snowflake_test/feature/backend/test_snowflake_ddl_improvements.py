# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_snowflake_ddl_improvements.py
"""Tests for Snowflake DDL improvements: capability gating, UnsupportedFeatureError."""
import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import CreateTableExpression
from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


class TestSnowflakeViewCapabilityGating:
    """Tests for Snowflake VIEW DDL capability gating."""

    def test_create_or_replace_view_supported(self):
        """Snowflake supports CREATE OR REPLACE VIEW."""
        dialect = SnowflakeDialect()
        assert dialect.supports_create_or_replace_view() is True

    def test_create_view_if_not_exists_supported(self):
        """Snowflake supports CREATE VIEW IF NOT EXISTS."""
        dialect = SnowflakeDialect()
        assert dialect.supports_if_not_exists_view() is True

    def test_drop_view_if_exists_supported(self):
        """Snowflake supports DROP VIEW IF EXISTS."""
        dialect = SnowflakeDialect()
        assert dialect.supports_if_exists_view() is True

    def test_materialized_view_supported(self):
        """Snowflake supports native materialized views."""
        dialect = SnowflakeDialect()
        assert dialect.supports_materialized_view() is True


class TestSnowflakeSchemaCapabilityGating:
    """Tests for Snowflake SCHEMA DDL capability gating."""

    def test_create_schema_supported(self):
        """Snowflake supports CREATE SCHEMA."""
        dialect = SnowflakeDialect()
        assert dialect.supports_create_schema() is True

    def test_drop_schema_supported(self):
        """Snowflake supports DROP SCHEMA."""
        dialect = SnowflakeDialect()
        assert dialect.supports_drop_schema() is True

    def test_schema_if_not_exists_supported(self):
        """Snowflake supports CREATE SCHEMA IF NOT EXISTS."""
        dialect = SnowflakeDialect()
        assert dialect.supports_schema_if_not_exists() is True

    def test_schema_if_exists_supported(self):
        """Snowflake supports DROP SCHEMA IF EXISTS."""
        dialect = SnowflakeDialect()
        assert dialect.supports_schema_if_exists() is True


class TestSnowflakeTableDeclarationGating:
    def test_table_declaration_defaults_are_absent(self):
        dialect = SnowflakeDialect(version=(8, 0, 0))
        expression = CreateTableExpression(
            dialect,
            "plain_table_defaults",
            [ColumnDefinition(dialect, "id", IntegerType(dialect))],
        )
        sql, params = expression.to_sql()
        assert expression.inherits == []
        assert expression.tablespace is None
        assert "plain_table_defaults" in sql.lower()
        assert "id" in sql.lower()
        assert params == ()

    def test_table_inherits_is_propagated_and_rejected(self):
        dialect = SnowflakeDialect(version=(8, 0, 0))
        assert dialect.supports_table_inheritance() is False
        expression = CreateTableExpression(
            dialect,
            "inherited",
            [ColumnDefinition(dialect, "id", IntegerType(dialect))],
            inherits=["parent_a", "parent_b"],
        )
        assert expression.inherits == ["parent_a", "parent_b"]
        with pytest.raises(UnsupportedFeatureError, match="INHERITS"):
            expression.to_sql()

    def test_table_tablespace_is_propagated_and_rejected(self):
        dialect = SnowflakeDialect(version=(8, 0, 0))
        assert dialect.supports_table_tablespace() is False
        expression = CreateTableExpression(
            dialect,
            "tablespaced",
            [ColumnDefinition(dialect, "id", IntegerType(dialect))],
            tablespace="ts_data",
        )
        assert expression.tablespace == "ts_data"
        with pytest.raises(UnsupportedFeatureError, match="TABLESPACE"):
            expression.to_sql()
