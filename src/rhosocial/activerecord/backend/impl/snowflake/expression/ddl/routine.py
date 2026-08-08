# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/routine.py
"""Snowflake PROCEDURE / FUNCTION expressions.

Snowflake supports stored procedures and user-defined functions written in
SQL, JavaScript, Java, Python and Scala, with Snowflake Scripting bodies
typically delimited by ``AS $$ ... $$``. These expressions generate
CREATE [OR REPLACE] PROCEDURE / FUNCTION and DROP PROCEDURE / FUNCTION
statements.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- CREATE PROCEDURE: https://docs.snowflake.com/en/sql-reference/sql/create-procedure
- CREATE FUNCTION:  https://docs.snowflake.com/en/sql-reference/sql/create-function
- DROP PROCEDURE:   https://docs.snowflake.com/en/sql-reference/sql/drop-procedure
- DROP FUNCTION:    https://docs.snowflake.com/en/sql-reference/sql/drop-function
"""
from enum import Enum
from typing import List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeRoutineLanguage",
    "SnowflakeRoutineExecuteAs",
    "SnowflakeRoutineType",
    "SnowflakeCreateProcedureExpression",
    "SnowflakeCreateFunctionExpression",
    "SnowflakeDropRoutineExpression",
]


class SnowflakeRoutineLanguage(Enum):
    """Supported routine implementation languages."""

    SQL = "SQL"
    JAVASCRIPT = "JAVASCRIPT"
    JAVA = "JAVA"
    PYTHON = "PYTHON"
    SCALA = "SCALA"


class SnowflakeRoutineExecuteAs(Enum):
    """EXECUTE AS privilege context for routines."""

    CALLER = "CALLER"
    OWNER = "OWNER"


class SnowflakeRoutineType(Enum):
    """Routine kinds accepted by DROP PROCEDURE / FUNCTION."""

    PROCEDURE = "PROCEDURE"
    FUNCTION = "FUNCTION"


class SnowflakeCreateProcedureExpression(BaseExpression):
    """Snowflake CREATE [OR REPLACE] PROCEDURE statement expression.

    Attributes:
        name: Procedure name.
        or_replace: Emit ``OR REPLACE``.
        args: Argument list of ``(name, type)`` tuples; ``name`` may be None.
        returns: ``RETURNS`` result type.
        language: :class:`SnowflakeRoutineLanguage`.
        execute_as: :class:`SnowflakeRoutineExecuteAs`.
        body: Routine body emitted as ``AS $$ ... $$``.
        comment: ``COMMENT`` string literal.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        or_replace: bool = False,
        args: Optional[List[Tuple[Optional[str], str]]] = None,
        returns: Optional[str] = None,
        language: SnowflakeRoutineLanguage = SnowflakeRoutineLanguage.SQL,
        execute_as: Optional[SnowflakeRoutineExecuteAs] = None,
        body: Optional[str] = None,
        comment: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.or_replace = or_replace
        self.args = args or []
        self.returns = returns
        self.language = language
        self.execute_as = execute_as
        self.body = body
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE PROCEDURE SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_create_procedure_statement(self), ()


class SnowflakeCreateFunctionExpression(BaseExpression):
    """Snowflake CREATE [OR REPLACE] FUNCTION statement expression.

    Attributes:
        name: Function name.
        or_replace: Emit ``OR REPLACE``.
        args: Argument list of ``(name, type)`` tuples; ``name`` may be None.
        returns: ``RETURNS`` result type.
        language: :class:`SnowflakeRoutineLanguage`.
        immutable: ``IMMUTABLE`` / ``VOLATILE`` when not None.
        execute_as: :class:`SnowflakeRoutineExecuteAs`.
        body: Function body emitted as ``AS $$ ... $$``.
        comment: ``COMMENT`` string literal.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        or_replace: bool = False,
        args: Optional[List[Tuple[Optional[str], str]]] = None,
        returns: Optional[str] = None,
        language: SnowflakeRoutineLanguage = SnowflakeRoutineLanguage.SQL,
        immutable: Optional[bool] = None,
        execute_as: Optional[SnowflakeRoutineExecuteAs] = None,
        body: Optional[str] = None,
        comment: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.or_replace = or_replace
        self.args = args or []
        self.returns = returns
        self.language = language
        self.immutable = immutable
        self.execute_as = execute_as
        self.body = body
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE FUNCTION SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_create_function_statement(self), ()


class SnowflakeDropRoutineExpression(BaseExpression):
    """Snowflake DROP PROCEDURE / DROP FUNCTION statement expression.

    Attributes:
        name: Routine name.
        routine_type: :class:`SnowflakeRoutineType`.
        if_exists: Emit ``IF EXISTS``.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        routine_type: SnowflakeRoutineType = SnowflakeRoutineType.PROCEDURE,
        if_exists: bool = False,
    ):
        super().__init__(dialect)
        self.name = name
        self.routine_type = routine_type
        self.if_exists = if_exists

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate DROP PROCEDURE / FUNCTION SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_drop_routine_statement(self), ()
