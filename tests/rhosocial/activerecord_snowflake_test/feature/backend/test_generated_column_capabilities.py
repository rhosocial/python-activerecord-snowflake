# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_generated_column_capabilities.py
"""Explicit Snowflake generated-column capability assertions.

Snowflake supports virtual (expression) computed columns but not stored ones.
"""

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


def test_generated_columns_supported():
    assert SnowflakeDialect((8, 0, 0)).supports_generated_columns() is True


def test_stored_unsupported_virtual_supported():
    dialect = SnowflakeDialect((8, 0, 0))
    assert dialect.supports_stored_generated_columns() is False
    assert dialect.supports_virtual_generated_columns() is True
