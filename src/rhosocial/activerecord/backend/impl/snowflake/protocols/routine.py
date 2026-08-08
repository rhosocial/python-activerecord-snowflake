# src/rhosocial/activerecord/backend/impl/snowflake/protocols/routine.py
"""Snowflake procedure / function protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake supports stored procedures and user-defined functions written in
SQL, JavaScript, Java, Python and Scala, typically with Snowflake Scripting
bodies delimited by ``AS $$ ... $$``.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-procedure
- https://docs.snowflake.com/en/sql-reference/sql/create-function
"""
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.routine import (
        SnowflakeCreateFunctionExpression,
        SnowflakeCreateProcedureExpression,
        SnowflakeDropRoutineExpression,
    )


@runtime_checkable
class SnowflakeRoutineSupport(Protocol):
    """Snowflake procedure / function protocol."""

    def supports_routines(self) -> bool:
        """Whether procedures and functions are supported."""
        ...

    def format_create_procedure_statement(
        self, expr: "SnowflakeCreateProcedureExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] PROCEDURE statement."""
        ...

    def format_create_function_statement(
        self, expr: "SnowflakeCreateFunctionExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] FUNCTION statement."""
        ...

    def format_drop_routine_statement(
        self, expr: "SnowflakeDropRoutineExpression"
    ) -> str:
        """Format DROP PROCEDURE / DROP FUNCTION statement."""
        ...
