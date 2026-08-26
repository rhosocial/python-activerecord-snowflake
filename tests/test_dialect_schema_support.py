# tests/rhosocial/activerecord_snowflake_test/test_dialect_schema_support.py
"""Tests for the SchemaSupport capability declared on the Snowflake dialect.

Snowflake exposes the full three-level namespace (database.schema.table), so
the umbrella ``supports_schema()`` flag must be True. Granular schema DDL
capability bits are not wired up yet and stay False.
"""
from rhosocial.activerecord.backend.dialect.protocols import SchemaSupport
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


class TestSchemaCapability:
    """Umbrella flag and granular schema DDL capability bits."""

    def _dialect(self) -> SnowflakeDialect:
        return SnowflakeDialect()

    def test_supports_schema_is_true(self):
        assert self._dialect().supports_schema() is True

    def test_implements_schema_support_protocol(self):
        assert isinstance(self._dialect(), SchemaSupport)

    def test_granular_ddl_flags_currently_false(self):
        """Documents current state until CREATE/DROP SCHEMA DDL is wired up."""
        d = self._dialect()
        assert d.supports_create_schema() is False
        assert d.supports_drop_schema() is False
