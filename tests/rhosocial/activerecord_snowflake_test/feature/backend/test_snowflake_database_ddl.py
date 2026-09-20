# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_snowflake_database_ddl.py
"""Explicit SnowflakeDialect database DDL capability + rendering tests."""

from rhosocial.activerecord.backend.expression.statements.ddl_database import (
    CreateDatabaseExpression,
    DropDatabaseExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


def _dialect():
    return SnowflakeDialect()


def test_database_capabilities():
    dialect = _dialect()
    assert dialect.supports_create_database() is True
    assert dialect.supports_drop_database() is True


def test_create_database_renders():
    sql, params = CreateDatabaseExpression(_dialect(), database_name="app").to_sql()
    assert "CREATE DATABASE" in sql
    assert params == ()


def test_drop_database_renders():
    sql, _ = DropDatabaseExpression(_dialect(), database_name="app").to_sql()
    assert "DROP DATABASE" in sql
