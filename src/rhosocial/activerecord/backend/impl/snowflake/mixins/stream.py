# src/rhosocial/activerecord/backend/impl/snowflake/mixins/stream.py
"""SnowflakeStreamMixin — stream (change data capture) DDL support."""

from typing import Tuple, TYPE_CHECKING

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
    ) -> Tuple[str, tuple]:
        """Format CREATE [OR REPLACE] STREAM statement.

        Args:
            expr: :class:`SnowflakeCreateStreamExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

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
            kind, value = expr.at
            kind = str(kind).upper()
            if kind == "OFFSET":
                parts.append(f"AT(OFFSET => {int(value)})")
            else:
                escaped = self._escape_sql_string(str(value))
                parts.append(f"AT({kind} => '{escaped}')")
        if expr.before is not None:
            kind, value = expr.before
            kind = str(kind).upper()
            if kind == "OFFSET":
                parts.append(f"BEFORE(OFFSET => {int(value)})")
            else:
                escaped = self._escape_sql_string(str(value))
                parts.append(f"BEFORE({kind} => '{escaped}')")
        if expr.copy_grants is not None:
            parts.append(f"COPY_GRANTS = {str(bool(expr.copy_grants)).upper()}")
        if expr.comment is not None:
            parts.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        return " ".join(parts), ()

    def format_drop_stream_statement(
        self, expr: "SnowflakeDropStreamExpression"
    ) -> Tuple[str, tuple]:
        """Format DROP STREAM statement.

        Args:
            expr: :class:`SnowflakeDropStreamExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = ["DROP STREAM"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts), ()
