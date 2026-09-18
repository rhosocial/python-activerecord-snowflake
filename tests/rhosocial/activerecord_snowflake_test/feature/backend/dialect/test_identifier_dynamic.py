# tests/rhosocial/activerecord_snowflake_test/feature/backend/dialect/test_identifier_dynamic.py
"""Tests for Snowflake IDENTIFIER() dynamic identifier support.

Pure construction tests — no real Snowflake instance required.
The placeholder for snowflake-connector-python is ``%s`` (pyformat).
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeIdentifierExpression,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeDynamicIdentifierSupport:
    """Dialect exposes the dynamic identifier (IDENTIFIER()) surface."""

    def test_supports_dynamic_identifier(self, dialect):
        assert dialect.supports_dynamic_identifier() is True


class TestSnowflakeIdentifierExpression:
    """IDENTIFIER() expression generation with parameter binding."""

    def test_placeholder_is_pyformat(self, dialect):
        assert dialect.get_parameter_placeholder() == "%s"

    def test_identifier_expression_basic(self, dialect):
        expr = SnowflakeIdentifierExpression(dialect, "my_table")
        sql, params = expr.to_sql()
        assert sql == "IDENTIFIER(%s)"
        assert params == ("my_table",)

    def test_identifier_expression_other_name(self, dialect):
        expr = SnowflakeIdentifierExpression(dialect, "my_schema.my_table")
        sql, params = expr.to_sql()
        assert sql == "IDENTIFIER(%s)"
        assert params == ("my_schema.my_table",)

    def test_format_identifier_dynamic_uses_placeholder(self, dialect):
        expr = SnowflakeIdentifierExpression(dialect, "whatever")
        sql, params = expr.to_sql()
        assert sql == "IDENTIFIER(%s)"
        assert params == ("whatever",)

    def test_identifier_can_be_composed_into_ddl(self, dialect):
        expr = SnowflakeIdentifierExpression(dialect, "my_table")
        sql, params = expr.to_sql()
        composed = f"SELECT * FROM {sql}"
        assert composed == "SELECT * FROM IDENTIFIER(%s)"
        assert params == ("my_table",)
