# src/rhosocial/activerecord/backend/impl/snowflake/mixins/file_format.py
"""SnowflakeFileFormatMixin — file format DDL support."""

from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.file_format import (
        SnowflakeAlterFileFormatExpression,
        SnowflakeCreateFileFormatExpression,
        SnowflakeDropFileFormatExpression,
    )


class SnowflakeFileFormatMixin:
    """Mixin for Snowflake file format support."""

    def supports_file_formats(self) -> bool:
        """Snowflake supports named file formats."""
        return True

    def format_create_file_format_statement(
        self, expr: "SnowflakeCreateFileFormatExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] FILE FORMAT statement.

        Args:
            expr: :class:`SnowflakeCreateFileFormatExpression`.

        Returns:
            The formatted CREATE FILE FORMAT SQL string.

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
        parts.extend(self._render_file_format_options(expr.options))
        if expr.comment is not None:
            parts.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        return " ".join(parts)

    def format_alter_file_format_statement(
        self, expr: "SnowflakeAlterFileFormatExpression"
    ) -> str:
        """Format ALTER FILE FORMAT SET statement.

        Args:
            expr: :class:`SnowflakeAlterFileFormatExpression`.

        Returns:
            The formatted ALTER FILE FORMAT SQL string.

        Raises:
            ValueError: when no ``SET`` property is specified.
        """
        options = self._render_file_format_options(expr.options)
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
        return " ".join(parts)

    def format_drop_file_format_statement(
        self, expr: "SnowflakeDropFileFormatExpression"
    ) -> str:
        """Format DROP FILE FORMAT statement.

        Args:
            expr: :class:`SnowflakeDropFileFormatExpression`.

        Returns:
            The formatted DROP FILE FORMAT SQL string.

        """
        parts = ["DROP FILE FORMAT"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts)

    def _render_file_format_options(self, options: Dict[str, Any]) -> List[str]:
        """Render pass-through format options as ``KEY = value`` tokens."""
        rendered = []
        for key, value in options.items():
            rendered.append(f"{key} = {self._render_file_format_value(value)}")
        return rendered

    def _render_file_format_value(self, value: Any) -> str:
        """Render a single format option value.

        Strings are quoted, booleans uppercased, lists/tuples rendered as
        parenthesized lists and numbers left verbatim.
        """
        if isinstance(value, bool):
            return str(value).upper()
        if isinstance(value, (list, tuple)):
            inner = ", ".join(self._render_file_format_value(v) for v in value)
            return f"({inner})"
        if isinstance(value, str):
            return f"'{self._escape_sql_string(value)}'"
        return str(value)
