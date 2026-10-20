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

from ..coercion import as_member

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


class SnowflakeRoutineLanguage(str, Enum):
    """Supported routine implementation languages."""
    #: A member *is* the word it carries: ``str()`` and f-string
    #: interpolation must yield the value, not ``ClassName.MEMBER``, or the
    #: rendered SQL and the artifact would carry the Python spelling.
    #: ``(str, Enum)`` alone does not give that -- ``Enum.__str__`` wins --
    #: so it is stated here once.
    __str__ = str.__str__

    SQL = "SQL"
    JAVASCRIPT = "JAVASCRIPT"
    JAVA = "JAVA"
    PYTHON = "PYTHON"
    SCALA = "SCALA"


class SnowflakeRoutineExecuteAs(str, Enum):
    """EXECUTE AS privilege context for routines."""
    #: A member *is* the word it carries: ``str()`` and f-string
    #: interpolation must yield the value, not ``ClassName.MEMBER``, or the
    #: rendered SQL and the artifact would carry the Python spelling.
    #: ``(str, Enum)`` alone does not give that -- ``Enum.__str__`` wins --
    #: so it is stated here once.
    __str__ = str.__str__

    CALLER = "CALLER"
    OWNER = "OWNER"


class SnowflakeRoutineType(str, Enum):
    """Routine kinds accepted by DROP PROCEDURE / FUNCTION."""
    #: A member *is* the word it carries: ``str()`` and f-string
    #: interpolation must yield the value, not ``ClassName.MEMBER``, or the
    #: rendered SQL and the artifact would carry the Python spelling.
    #: ``(str, Enum)`` alone does not give that -- ``Enum.__str__`` wins --
    #: so it is stated here once.
    __str__ = str.__str__

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
        self.language = as_member(SnowflakeRoutineLanguage, language, parameter="language")
        self.execute_as = as_member(SnowflakeRoutineExecuteAs, execute_as, parameter="execute_as")
        self.body = body
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE PROCEDURE SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_create_procedure_statement(self)


class SnowflakeCreateFunctionExpression(BaseExpression):
    """Snowflake CREATE [OR REPLACE] FUNCTION statement expression.

    Attributes:
        name: Function name.
        or_replace: Emit ``OR REPLACE``.
        args: Argument list of ``(name, type)`` tuples; ``name`` may be None.
        returns: ``RETURNS`` result type.
        language: :class:`SnowflakeRoutineLanguage`.
        immutable: Emit ``IMMUTABLE``.
        volatile: Emit ``VOLATILE`` (the server default).
        execute_as: :class:`SnowflakeRoutineExecuteAs`.
        body: Function body emitted as ``AS $$ ... $$``.
        comment: ``COMMENT`` string literal.

    ``immutable`` / ``volatile`` are the two spellings of the function's
    volatility; leaving both unset omits the clause (the server then applies
    its ``VOLATILE`` default), and setting both raises ``ValueError``.
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
        immutable: bool = False,
        volatile: bool = False,
        execute_as: Optional[SnowflakeRoutineExecuteAs] = None,
        body: Optional[str] = None,
        comment: Optional[str] = None,
    ):
        super().__init__(dialect)
        if immutable and volatile:
            raise ValueError(
                "immutable and volatile are mutually exclusive options"
            )
        self.name = name
        self.or_replace = or_replace
        self.args = args or []
        self.returns = returns
        self.language = as_member(SnowflakeRoutineLanguage, language, parameter="language")
        self.immutable = immutable
        self.volatile = volatile
        self.execute_as = as_member(
            SnowflakeRoutineExecuteAs, execute_as, parameter="execute_as"
        )
        self.body = body
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE FUNCTION SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_create_function_statement(self)


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
        self.routine_type = as_member(SnowflakeRoutineType, routine_type, parameter="routine_type")
        self.if_exists = if_exists

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate DROP PROCEDURE / FUNCTION SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_drop_routine_statement(self)
