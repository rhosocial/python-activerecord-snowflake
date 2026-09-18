# src/rhosocial/activerecord/backend/impl/snowflake/mixins/file_format.py
"""SnowflakeFileFormatMixin — file format DDL support."""

from typing import Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.file_format import (
        SnowflakeAlterFileFormatExpression,
        SnowflakeCreateFileFormatExpression,
        SnowflakeDropFileFormatExpression,
    )


def _format_ff_value(value: Any, escape: callable) -> str:
    """Render a single format option value.

    Strings are quoted, booleans uppercased, lists/tuples rendered as
    parenthesized lists and numbers left verbatim.
    """
    if isinstance(value, bool):
        return str(value).upper()
    if isinstance(value, (list, tuple)):
        inner = ", ".join(_format_ff_value(v, escape) for v in value)
        return f"({inner})"
    if isinstance(value, str):
        return f"'{escape(value)}'"
    return str(value)


class SnowflakeFileFormatMixin:
    """Mixin for Snowflake file format support."""

    def supports_file_formats(self) -> bool:
        """Snowflake supports named file formats."""
        return True

    def format_create_file_format_statement(
        self, expr: "SnowflakeCreateFileFormatExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE [OR REPLACE] FILE FORMAT statement.

        Args:
            expr: :class:`SnowflakeCreateFileFormatExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("FILE FORMAT")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.name))
        if expr.type_ is not None:
            type_value = getattr(expr.type_, "value", expr.type_)
            parts.append(f"TYPE = {str(type_value).upper()}")
        for key, value in expr.options.items():
            parts.append(
                f"{key} = {_format_ff_value(value, self._escape_sql_string)}"
            )
        if expr.comment is not None:
            parts.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        return " ".join(parts), ()

    def format_alter_file_format_statement(
        self, expr: "SnowflakeAlterFileFormatExpression"
    ) -> Tuple[str, tuple]:
        """Format ALTER FILE FORMAT SET statement.

        Args:
            expr: :class:`SnowflakeAlterFileFormatExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        Raises:
            ValueError: when no ``SET`` property is specified.
        """
        options: list[str] = []
        for key, value in expr.options.items():
            options.append(
                f"{key} = {_format_ff_value(value, self._escape_sql_string)}"
            )
        if expr.comment is not None:
            options.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        if not options:
            raise ValueError("ALTER FILE FORMAT SET requires a property")
        parts = ["ALTER FILE FORMAT"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        parts.append("SET")
        parts.extend(options)
        return " ".join(parts), ()

    def format_drop_file_format_statement(
        self, expr: "SnowflakeDropFileFormatExpression"
    ) -> Tuple[str, tuple]:
        """Format DROP FILE FORMAT statement.

        Args:
            expr: :class:`SnowflakeDropFileFormatExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = ["DROP FILE FORMAT"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts), ()
