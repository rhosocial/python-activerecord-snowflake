# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_create_table_family.py
"""Snowflake CREATE TABLE family tests (LIKE / CLONE / COPY / USING TEMPLATE).

Snowflake reuses the generic core TableMixin renderers once the capability
flags are advertised. Pure construction tests — no real instance required.
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeCreateTableOptions,
)
from rhosocial.activerecord.backend.expression import (
    CreateTableLikeExpression,
    CreateTableCloneExpression,
    CreateTableCloneMode,
    CreateTableFromTemplateExpression,
    CreateTableOptions,
    CreateTableExpression,
    QueryExpression,
    Literal,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeCreateTableFamily:
    """Capability flags and generic rendering for the CREATE TABLE family."""

    def test_capabilities(self, dialect):
        assert dialect.supports_create_table_like() is True
        assert dialect.supports_create_table_clone() is True
        assert dialect.supports_create_table_using_template() is True

    def test_create_table_like(self, dialect):
        sql, params = CreateTableLikeExpression(dialect, "copy", "src").to_sql()
        assert sql == 'CREATE TABLE "copy" LIKE "src"'
        assert params == ()

    def test_create_table_clone(self, dialect):
        sql, params = CreateTableCloneExpression(
            dialect, "clone_t", "src", copy_grants=True
        ).to_sql()
        assert sql == 'CREATE TABLE "clone_t" CLONE "src" COPY GRANTS'
        assert params == ()

    def test_create_table_copy(self, dialect):
        sql, params = CreateTableCloneExpression(
            dialect, "copy_t", "src", mode=CreateTableCloneMode.COPY
        ).to_sql()
        assert sql == 'CREATE TABLE "copy_t" COPY "src"'
        assert params == ()

    def test_create_table_using_template(self, dialect):
        template = QueryExpression(dialect, select=[Literal(dialect, 1)])
        sql, params = CreateTableFromTemplateExpression(dialect, "t", template).to_sql()
        assert "USING TEMPLATE" in sql
        assert params == (1,)

    def test_create_or_replace(self, dialect):
        expr = CreateTableExpression(
            dialect,
            table="t",
            columns=[],
            table_options=CreateTableOptions(dialect, or_replace=True),
        )
        sql, _ = expr.to_sql()
        assert sql.startswith("CREATE OR REPLACE TABLE")

    def test_create_transient(self, dialect):
        expr = CreateTableExpression(
            dialect,
            table="t",
            columns=[],
            table_options=SnowflakeCreateTableOptions(dialect, transient=True),
        )
        sql, _ = expr.to_sql()
        assert sql.startswith("CREATE TRANSIENT TABLE")

    def test_create_or_replace_transient(self, dialect):
        expr = CreateTableExpression(
            dialect,
            table="t",
            columns=[],
            table_options=SnowflakeCreateTableOptions(
                dialect, or_replace=True, transient=True
            ),
        )
        sql, _ = expr.to_sql()
        assert sql.startswith("CREATE OR REPLACE TRANSIENT TABLE")
