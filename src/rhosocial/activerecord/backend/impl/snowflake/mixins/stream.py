# src/rhosocial/activerecord/backend/impl/snowflake/mixins/stream.py
"""SnowflakeStreamMixin — stream (change data capture) DDL support."""

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.stream import (
        SnowflakeCreateStreamExpression,
        SnowflakeDropStreamExpression,
    )


class SnowflakeStreamMixin:
    """Mixin for Snowflake stream (CDC) support."""

    def supports_stream(self) -> bool:
        """Snowflake supports streams."""
        return True

    def format_create_stream_statement(
        self, expr: "SnowflakeCreateStreamExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] STREAM statement.

        Args:
            expr: :class:`SnowflakeCreateStreamExpression`.

        Returns:
            The formatted CREATE STREAM SQL string.

        Raises:
            ValueError: when ``object_name`` is not specified.
        """
        if expr.object_name is None:
            raise ValueError("CREATE STREAM requires an object_name")
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("STREAM")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.name))
        parts.append("ON")
        parts.append(expr.object_type.value)
        parts.append(self.format_identifier(expr.object_name))
        if expr.append_only is not None:
            parts.append(
                f"APPEND_ONLY = {str(bool(expr.append_only)).upper()}"
            )
        if expr.insert_only is not None:
            parts.append(
                f"INSERT_ONLY = {str(bool(expr.insert_only)).upper()}"
            )
        if expr.show_initial_rows is not None:
            parts.append(
                f"SHOW_INITIAL_ROWS = {str(bool(expr.show_initial_rows)).upper()}"
            )
        if expr.at is not None:
            parts.append(self.format_stream_time_point("AT", expr.at))
        if expr.before is not None:
            parts.append(self.format_stream_time_point("BEFORE", expr.before))
        if expr.copy_grants is not None:
            parts.append(f"COPY_GRANTS = {str(bool(expr.copy_grants)).upper()}")
        if expr.comment is not None:
            parts.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        return " ".join(parts)

    def format_drop_stream_statement(
        self, expr: "SnowflakeDropStreamExpression"
    ) -> str:
        """Format DROP STREAM statement.

        Args:
            expr: :class:`SnowflakeDropStreamExpression`.

        Returns:
            The formatted DROP STREAM SQL string.

        """
        parts = ["DROP STREAM"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts)

    def format_stream_time_point(self, keyword: str, spec: Any) -> str:
        """Render an AT / BEFORE time-travel point.

        ``spec`` is a ``(kind, value)`` tuple where kind is one of
        ``TIMESTAMP`` / ``OFFSET`` / ``STATEMENT``.
        """
        kind, value = spec
        kind = str(kind).upper()
        if kind == "OFFSET":
            return f"{keyword}(OFFSET => {int(value)})"
        escaped = self._escape_sql_string(str(value))
        return f"{keyword}({kind} => '{escaped}')"
