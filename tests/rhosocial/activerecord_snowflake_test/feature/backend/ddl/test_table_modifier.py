# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_table_modifier.py
"""Tests for Snowflake table DDL modifier support.

Covers CREATE OR REPLACE / TRANSIENT / TEMPORARY table modifier capability
detection, CLUSTER BY, and SEARCH OPTIMIZATION protocol conformance.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeTableModifierSupport,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeTableModifierProtocol:
    """Dialect satisfies isinstance checks for the table modifier protocol."""

    def test_dialect_is_table_modifier_support(self, dialect):
        assert isinstance(dialect, SnowflakeTableModifierSupport)

    def test_supports_create_or_replace_table(self, dialect):
        assert dialect.supports_create_or_replace_table() is True

    def test_supports_transient_table(self, dialect):
        assert dialect.supports_transient_table() is True

    def test_supports_cluster_by(self, dialect):
        assert dialect.supports_cluster_by() is True

    def test_supports_search_optimization(self, dialect):
        assert dialect.supports_search_optimization() is True
