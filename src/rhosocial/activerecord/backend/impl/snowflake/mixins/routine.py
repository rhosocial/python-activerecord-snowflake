# src/rhosocial/activerecord/backend/impl/snowflake/mixins/routine.py
"""SnowflakeRoutineMixin — procedure / function DDL support."""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.routine import (
        SnowflakeCreateFunctionExpression,
        SnowflakeCreateProcedureExpression,
        SnowflakeDropRoutineExpression,
    )


class SnowflakeRoutineMixin:
    """Mixin for Snowflake stored procedure / UDF support."""

    def supports_routines(self) -> bool:
        """Snowflake supports procedures and functions."""
        return True

    def supports_functions(self) -> Dict[str, bool]:
        """Return the SQL functions available in this dialect.

        Snowflake ships a large built-in function library; this mapping is
        intentionally empty so function-gated tests skip rather than assume
        availability.
        """
        return {}

    def format_create_procedure_statement(
        self, expr: "SnowflakeCreateProcedureExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE [OR REPLACE] PROCEDURE statement.

        Args:
            expr: :class:`SnowflakeCreateProcedureExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("PROCEDURE")
        parts.append(self.format_identifier(expr.name))
        parts.append(self.format_routine_args(expr.args))
        parts.append(f"RETURNS {expr.returns}")
        parts.append(f"LANGUAGE {expr.language.value}")
        if expr.execute_as is not None:
            parts.append(f"EXECUTE AS {expr.execute_as.value}")
        parts.append(self.format_routine_body(expr.body))
        if expr.comment is not None:
            parts.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        return " ".join(parts), ()

    def format_create_function_statement(
        self, expr: "SnowflakeCreateFunctionExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE [OR REPLACE] FUNCTION statement.

        Args:
            expr: :class:`SnowflakeCreateFunctionExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("FUNCTION")
        parts.append(self.format_identifier(expr.name))
        parts.append(self.format_routine_args(expr.args))
        parts.append(f"RETURNS {expr.returns}")
        parts.append(f"LANGUAGE {expr.language.value}")
        if expr.immutable is not None:
            parts.append("IMMUTABLE" if expr.immutable else "VOLATILE")
        if expr.execute_as is not None:
            parts.append(f"EXECUTE AS {expr.execute_as.value}")
        parts.append(self.format_routine_body(expr.body))
        if expr.comment is not None:
            parts.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        return " ".join(parts), ()

    def format_drop_routine_statement(
        self, expr: "SnowflakeDropRoutineExpression"
    ) -> Tuple[str, tuple]:
        """Format DROP PROCEDURE / FUNCTION statement.

        Args:
            expr: :class:`SnowflakeDropRoutineExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = [f"DROP {expr.routine_type.value}"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts), ()

    def format_routine_args(self, args: Any) -> str:
        """Render a routine argument list as ``(name TYPE, ...)``."""
        if not args:
            return "()"
        rendered = []
        for arg in args:
            arg_name, arg_type = arg
            if arg_name:
                rendered.append(
                    f"{self.format_identifier(arg_name)} {arg_type}"
                )
            else:
                rendered.append(str(arg_type))
        return "(" + ", ".join(rendered) + ")"

    def format_routine_body(self, body: Any) -> str:
        """Render a routine body as a dollar-quoted ``AS $$ ... $$`` clause."""
        if body is None:
            return ""
        return f"AS $$ {body} $$"
