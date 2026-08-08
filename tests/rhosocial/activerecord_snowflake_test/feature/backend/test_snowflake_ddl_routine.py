"""Tests for Snowflake PROCEDURE / FUNCTION DDL support.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeRoutineSupport,
)
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeCreateFunctionExpression,
    SnowflakeCreateProcedureExpression,
    SnowflakeDropRoutineExpression,
    SnowflakeRoutineExecuteAs,
    SnowflakeRoutineLanguage,
    SnowflakeRoutineType,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeRoutineProtocol:
    """Dialect satisfies isinstance checks for the routine protocol."""

    def test_dialect_is_routine_support(self, dialect):
        assert isinstance(dialect, SnowflakeRoutineSupport)

    def test_supports_routines(self, dialect):
        assert dialect.supports_routines() is True


class TestSnowflakeCreateProcedure:
    """CREATE [OR REPLACE] PROCEDURE statement generation."""

    def test_create_procedure_basic(self, dialect):
        expr = SnowflakeCreateProcedureExpression(
            dialect,
            "p",
            args=[("x", "NUMBER")],
            returns="VARCHAR",
            body="BEGIN RETURN 'x=' || x; END",
        )
        sql, params = expr.to_sql()
        assert sql == (
            'CREATE PROCEDURE "p" ("x" NUMBER) RETURNS VARCHAR '
            "LANGUAGE SQL "
            "AS $$ BEGIN RETURN 'x=' || x; END $$"
        )
        assert params == ()

    def test_create_procedure_or_replace(self, dialect):
        expr = SnowflakeCreateProcedureExpression(
            dialect,
            "p",
            or_replace=True,
            args=[("x", "NUMBER")],
            returns="VARCHAR",
            body="SELECT 1",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE OR REPLACE PROCEDURE "p" ("x" NUMBER) RETURNS VARCHAR '
            "LANGUAGE SQL AS $$ SELECT 1 $$"
        )

    def test_create_procedure_javascript_language(self, dialect):
        expr = SnowflakeCreateProcedureExpression(
            dialect,
            "p",
            args=[("x", "NUMBER")],
            returns="VARCHAR",
            language=SnowflakeRoutineLanguage.JAVASCRIPT,
            body="return 'x=' + x;",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE PROCEDURE "p" ("x" NUMBER) RETURNS VARCHAR '
            "LANGUAGE JAVASCRIPT AS $$ return 'x=' + x; $$"
        )

    def test_create_procedure_execute_as_caller(self, dialect):
        expr = SnowflakeCreateProcedureExpression(
            dialect,
            "p",
            returns="VARCHAR",
            execute_as=SnowflakeRoutineExecuteAs.CALLER,
            body="SELECT 'hi'",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE PROCEDURE "p" () RETURNS VARCHAR LANGUAGE SQL '
            "EXECUTE AS CALLER AS $$ SELECT 'hi' $$"
        )

    def test_create_procedure_multiple_args(self, dialect):
        expr = SnowflakeCreateProcedureExpression(
            dialect,
            "p",
            args=[("a", "NUMBER"), (None, "VARCHAR")],
            returns="NUMBER",
            body="SELECT 1",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE PROCEDURE "p" ("a" NUMBER, VARCHAR) RETURNS NUMBER '
            "LANGUAGE SQL AS $$ SELECT 1 $$"
        )


class TestSnowflakeCreateFunction:
    """CREATE [OR REPLACE] FUNCTION statement generation."""

    def test_create_function_basic(self, dialect):
        expr = SnowflakeCreateFunctionExpression(
            dialect,
            "f",
            args=[("x", "NUMBER")],
            returns="NUMBER",
            immutable=True,
            body="SELECT x * 2",
        )
        sql, params = expr.to_sql()
        assert sql == (
            'CREATE FUNCTION "f" ("x" NUMBER) RETURNS NUMBER '
            "LANGUAGE SQL IMMUTABLE AS $$ SELECT x * 2 $$"
        )
        assert params == ()

    def test_create_function_volatile(self, dialect):
        expr = SnowflakeCreateFunctionExpression(
            dialect,
            "f",
            returns="NUMBER",
            immutable=False,
            body="SELECT 1",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE FUNCTION "f" () RETURNS NUMBER LANGUAGE SQL VOLATILE '
            "AS $$ SELECT 1 $$"
        )

    def test_create_function_execute_as_owner(self, dialect):
        expr = SnowflakeCreateFunctionExpression(
            dialect,
            "f",
            returns="NUMBER",
            execute_as=SnowflakeRoutineExecuteAs.OWNER,
            body="SELECT 1",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE FUNCTION "f" () RETURNS NUMBER LANGUAGE SQL '
            "EXECUTE AS OWNER AS $$ SELECT 1 $$"
        )

    def test_create_function_or_replace(self, dialect):
        expr = SnowflakeCreateFunctionExpression(
            dialect,
            "f",
            or_replace=True,
            returns="NUMBER",
            body="SELECT 2",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE OR REPLACE FUNCTION "f" () RETURNS NUMBER LANGUAGE SQL '
            "AS $$ SELECT 2 $$"
        )

    def test_create_function_python_language(self, dialect):
        expr = SnowflakeCreateFunctionExpression(
            dialect,
            "f",
            returns="NUMBER",
            language=SnowflakeRoutineLanguage.PYTHON,
            body="return x * 2",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE FUNCTION "f" () RETURNS NUMBER LANGUAGE PYTHON '
            "AS $$ return x * 2 $$"
        )


class TestSnowflakeDropRoutine:
    """DROP PROCEDURE / FUNCTION statement generation."""

    def test_drop_procedure(self, dialect):
        expr = SnowflakeDropRoutineExpression(
            dialect, "p", routine_type=SnowflakeRoutineType.PROCEDURE
        )
        sql, params = expr.to_sql()
        assert sql == 'DROP PROCEDURE "p"'
        assert params == ()

    def test_drop_function_if_exists(self, dialect):
        expr = SnowflakeDropRoutineExpression(
            dialect,
            "f",
            routine_type=SnowflakeRoutineType.FUNCTION,
            if_exists=True,
        )
        sql, _ = expr.to_sql()
        assert sql == 'DROP FUNCTION IF EXISTS "f"'

    def test_drop_routine_defaults_to_procedure(self, dialect):
        expr = SnowflakeDropRoutineExpression(dialect, "p")
        sql, _ = expr.to_sql()
        assert sql == 'DROP PROCEDURE "p"'
