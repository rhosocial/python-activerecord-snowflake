# tests/rhosocial/activerecord_snowflake_test/feature/query/test_collation_expression.py
"""
Tests for expression-level COLLATE support on Snowflake.
"""

import os

import pytest

from rhosocial.activerecord.backend.expression import Column, Literal
from rhosocial.activerecord.backend.expression.collation import CollationName
from rhosocial.activerecord.backend.impl.snowflake import (
    SnowflakeBackend,
    SnowflakeCollation,
    SnowflakeConnectionConfig,
    SnowflakeDialect,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


@pytest.fixture(scope="session")
def snowflake_backend():
    required = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_WAREHOUSE",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.skip(f"Missing Snowflake env vars: {', '.join(missing)}")

    config = SnowflakeConnectionConfig(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ.get("SNOWFLAKE_PASSWORD"),
        private_key_path=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH"),
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
    )
    backend = SnowflakeBackend(connection_config=config)
    backend.connect()
    test_schema = f"AR_TEST_{os.getpid()}"
    backend.execute(f'CREATE SCHEMA IF NOT EXISTS "{test_schema}"', ())
    backend.execute(f'USE SCHEMA "{test_schema}"', ())
    yield backend
    backend.execute(f'DROP SCHEMA IF EXISTS "{test_schema}" CASCADE', ())
    backend.disconnect()


@pytest.fixture
def collation_table(snowflake_backend):
    snowflake_backend.execute('DROP TABLE IF EXISTS "TEST_COLLATION_EXPRESSION"', ())
    snowflake_backend.execute(
        """
        CREATE TABLE "TEST_COLLATION_EXPRESSION" (
            "ID" INTEGER AUTOINCREMENT PRIMARY KEY,
            "NAME" VARCHAR NOT NULL
        )
        """,
        (),
    )
    snowflake_backend.execute(
        """
        INSERT INTO "TEST_COLLATION_EXPRESSION" ("NAME")
        VALUES ('Alice'), ('alice'), ('Bob')
        """,
        (),
    )
    yield "TEST_COLLATION_EXPRESSION"
    snowflake_backend.execute('DROP TABLE IF EXISTS "TEST_COLLATION_EXPRESSION"', ())


class TestSnowflakeCollationExpression:
    def test_column_collate_generates_sql(self, dialect):
        expr = Column(dialect, "name", table="users").collate(SnowflakeCollation.EN_CI)

        sql, params = expr.to_sql()

        assert sql == '"users"."name" COLLATE \'en-ci\''
        assert params == ()

    def test_literal_collate_preserves_parameter_binding(self, dialect):
        expr = Literal(dialect, "Alice").collate(SnowflakeCollation.EN_CI)

        sql, params = expr.to_sql()

        assert sql == "%s COLLATE 'en-ci'"
        assert params == ("Alice",)

    def test_rejects_schema_qualified_collation(self, dialect):
        expr = Column(dialect, "name").collate(CollationName("en-ci", schema="PUBLIC"))

        with pytest.raises(Exception, match="schema-qualified or keyword COLLATE"):
            expr.to_sql()

    def test_rejects_keyword_collation(self, dialect):
        expr = Column(dialect, "name").collate(CollationName.as_keyword("upper"))

        with pytest.raises(Exception, match="schema-qualified or keyword COLLATE"):
            expr.to_sql()

    def test_rejects_unsupported_collation(self, dialect):
        expr = Column(dialect, "name").collate("unknown-ci")

        with pytest.raises(ValueError, match="Unsupported Snowflake collation"):
            expr.to_sql()

    @pytest.mark.integration
    def test_collate_executes_case_sensitive_match(self, snowflake_backend, collation_table):
        expr = Column(snowflake_backend.dialect, "NAME", table=collation_table).collate(
            SnowflakeCollation.EN_CS
        )
        sql, params = expr.to_sql()

        rows = snowflake_backend.fetch_all(
            f'SELECT "NAME" FROM "{collation_table}" WHERE {sql} = %s ORDER BY "ID"',
            (*params, "Alice"),
        )

        assert [row["NAME"] for row in rows] == ["Alice"]

    @pytest.mark.integration
    def test_collate_executes_case_insensitive_match(self, snowflake_backend, collation_table):
        expr = Column(snowflake_backend.dialect, "NAME", table=collation_table).collate(
            SnowflakeCollation.EN_CI
        )
        sql, params = expr.to_sql()

        rows = snowflake_backend.fetch_all(
            f'SELECT "NAME" FROM "{collation_table}" WHERE {sql} = %s ORDER BY "ID"',
            (*params, "Alice"),
        )

        assert [row["NAME"] for row in rows] == ["Alice", "alice"]
