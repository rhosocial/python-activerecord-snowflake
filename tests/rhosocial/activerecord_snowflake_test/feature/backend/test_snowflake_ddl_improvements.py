# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_snowflake_ddl_improvements.py
"""Tests for Snowflake DDL improvements: capability gating, UnsupportedFeatureError."""
import pytest
from unittest.mock import patch, PropertyMock

from rhosocial.activerecord.backend.expression import (
    Column,
    TableExpression,
    QueryExpression,
    CreateViewExpression,
    DropViewExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class TestSnowflakeViewCapabilityGating:
    """Tests for Snowflake VIEW DDL capability gating."""

    def test_create_or_replace_view_supported(self):
        """Snowflake supports CREATE OR REPLACE VIEW."""
        dialect = SnowflakeDialect()
        assert dialect.supports_create_or_replace_view() is True

    def test_create_view_if_not_exists_not_supported(self):
        """Snowflake does not support CREATE VIEW IF NOT EXISTS."""
        dialect = SnowflakeDialect()
        assert dialect.supports_if_not_exists_view() is False

    def test_drop_view_if_exists_supported(self):
        """Snowflake supports DROP VIEW IF EXISTS."""
        dialect = SnowflakeDialect()
        assert dialect.supports_if_exists_view() is True

    def test_materialized_view_not_supported(self):
        """Snowflake does not support materialized views."""
        dialect = SnowflakeDialect()
        assert dialect.supports_materialized_view() is False


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
