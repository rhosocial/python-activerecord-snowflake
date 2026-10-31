# src/rhosocial/activerecord/backend/impl/snowflake/mixins/routine.py
"""SnowflakeRoutineMixin — procedure / function DDL support."""

from typing import Dict, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.routine import (
        SnowflakeCreateFunctionStatement,
        SnowflakeCreateProcedureStatement,
        SnowflakeDropRoutineStatement,
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
        self, expr: "SnowflakeCreateProcedureStatement"
    ) -> Tuple[str, tuple]:
        """Format CREATE [OR REPLACE] PROCEDURE statement.

        Args:
            expr: :class:`SnowflakeCreateProcedureStatement`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("PROCEDURE")
        parts.append(self.format_identifier(expr.name))
        from rhosocial.activerecord.backend.expression.types import DataType

        if not expr.args:
            parts.append("()")
        else:
            rendered = []
            for arg in expr.args:
                arg_name, arg_type = arg
                if arg_type is not None:
                    arg_type, _ = DataType.as_type(self, arg_type).to_sql()
                arg_type_sql = arg_type
                if arg_name:
                    rendered.append(
                        f"{self.format_identifier(arg_name)} {arg_type_sql}"
                    )
                else:
                    rendered.append(arg_type_sql)
            parts.append("(" + ", ".join(rendered) + ")")
        returns = expr.returns
        if returns is not None:
            returns, _ = DataType.as_type(self, returns).to_sql()
        parts.append(f"RETURNS {returns}")
        parts.append(f"LANGUAGE {expr.language.value}")
        if expr.execute_as is not None:
            parts.append(f"EXECUTE AS {expr.execute_as.value}")
        if expr.body is not None:
            parts.append(f"AS $$ {expr.body} $$")
        if expr.comment is not None:
            parts.append(
                f"COMMENT = '{self.escape_sql_string(expr.comment)}'"
            )
        return " ".join(parts), ()

    def format_create_function_statement(
        self, expr: "SnowflakeCreateFunctionStatement"
    ) -> Tuple[str, tuple]:
        """Format CREATE [OR REPLACE] FUNCTION statement.

        Args:
            expr: :class:`SnowflakeCreateFunctionStatement`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("FUNCTION")
        parts.append(self.format_identifier(expr.name))
        from rhosocial.activerecord.backend.expression.types import DataType

        if not expr.args:
            parts.append("()")
        else:
            rendered = []
            for arg in expr.args:
                arg_name, arg_type = arg
                if arg_type is not None:
                    arg_type, _ = DataType.as_type(self, arg_type).to_sql()
                arg_type_sql = arg_type
                if arg_name:
                    rendered.append(
                        f"{self.format_identifier(arg_name)} {arg_type_sql}"
                    )
                else:
                    rendered.append(arg_type_sql)
            parts.append("(" + ", ".join(rendered) + ")")
        returns = expr.returns
        if returns is not None:
            returns, _ = DataType.as_type(self, returns).to_sql()
        parts.append(f"RETURNS {returns}")
        parts.append(f"LANGUAGE {expr.language.value}")
        if expr.immutable:
            parts.append("IMMUTABLE")
        elif expr.volatile:
            parts.append("VOLATILE")
        if expr.execute_as is not None:
            parts.append(f"EXECUTE AS {expr.execute_as.value}")
        if expr.body is not None:
            parts.append(f"AS $$ {expr.body} $$")
        if expr.comment is not None:
            parts.append(
                f"COMMENT = '{self.escape_sql_string(expr.comment)}'"
            )
        return " ".join(parts), ()

    def format_drop_routine_statement(
        self, expr: "SnowflakeDropRoutineStatement"
    ) -> Tuple[str, tuple]:
        """Format DROP PROCEDURE / FUNCTION statement.

        Args:
            expr: :class:`SnowflakeDropRoutineStatement`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = [f"DROP {expr.routine_type.value}"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts), ()
