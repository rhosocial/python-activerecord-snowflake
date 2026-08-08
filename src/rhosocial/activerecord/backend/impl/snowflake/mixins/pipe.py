# src/rhosocial/activerecord/backend/impl/snowflake/mixins/pipe.py
"""SnowflakePipeMixin — pipe (Snowpipe) DDL support."""

from typing import TYPE_CHECKING

from ..expression.ddl.pipe import SnowflakeAlterPipeMode

if TYPE_CHECKING:
    from ..expression.ddl.pipe import (
        SnowflakeAlterPipeExpression,
        SnowflakeCreatePipeExpression,
        SnowflakeDropPipeExpression,
    )


class SnowflakePipeMixin:
    """Mixin for Snowflake pipe (Snowpipe) support."""

    def supports_pipes(self) -> bool:
        """Snowflake supports pipes."""
        return True

    def format_create_pipe_statement(
        self, expr: "SnowflakeCreatePipeExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] PIPE statement.

        Args:
            expr: :class:`SnowflakeCreatePipeExpression`.

        Returns:
            The formatted CREATE PIPE SQL string.

        Raises:
            ValueError: when ``copy_sql`` is not specified.
        """
        if expr.copy_sql is None:
            raise ValueError("CREATE PIPE requires a copy_sql body")
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("PIPE")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.name))
        if expr.auto_ingest is not None:
            parts.append(f"AUTO_INGEST = {str(bool(expr.auto_ingest)).upper()}")
        if expr.error_integration is not None:
            parts.append(
                f"ERROR_INTEGRATION = "
                f"{self.format_identifier(expr.error_integration)}"
            )
        if expr.aws_sns_topic is not None:
            parts.append(
                f"AWS_SNS_TOPIC = '{self._escape_sql_string(expr.aws_sns_topic)}'"
            )
        if expr.integration is not None:
            parts.append(
                f"INTEGRATION = '{self._escape_sql_string(expr.integration)}'"
            )
        if expr.comment is not None:
            parts.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        parts.extend(["AS", str(expr.copy_sql)])
        return " ".join(parts)

    def format_alter_pipe_statement(
        self, expr: "SnowflakeAlterPipeExpression"
    ) -> str:
        """Format ALTER PIPE statement.

        Emits ``REFRESH`` / ``SET ...`` / pause / resume based on
        :attr:`expr.mode`.

        Args:
            expr: :class:`SnowflakeAlterPipeExpression`.

        Returns:
            The formatted ALTER PIPE SQL string.

        Raises:
            ValueError: SET with no property.
        """
        parts = ["ALTER PIPE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        mode = expr.mode
        if mode is SnowflakeAlterPipeMode.REFRESH:
            parts.append("REFRESH")
            if expr.modified_after is not None:
                value = self._escape_sql_string(str(expr.modified_after))
                parts.append(f"MODIFIED_AFTER => '{value}'")
            return " ".join(parts)
        if mode is SnowflakeAlterPipeMode.PAUSE:
            parts.append("SET PIPE_EXECUTION_PAUSED = TRUE")
            return " ".join(parts)
        if mode is SnowflakeAlterPipeMode.RESUME:
            parts.append("SET PIPE_EXECUTION_PAUSED = FALSE")
            return " ".join(parts)
        options = []
        if expr.pipe_execution_paused is not None:
            options.append(
                "PIPE_EXECUTION_PAUSED = "
                f"{str(bool(expr.pipe_execution_paused)).upper()}"
            )
        if expr.comment is not None:
            options.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        if not options:
            raise ValueError("ALTER PIPE SET requires at least one property")
        parts.append("SET")
        parts.extend(options)
        return " ".join(parts)

    def format_drop_pipe_statement(
        self, expr: "SnowflakeDropPipeExpression"
    ) -> str:
        """Format DROP PIPE statement.

        Args:
            expr: :class:`SnowflakeDropPipeExpression`.

        Returns:
            The formatted DROP PIPE SQL string.

        """
        parts = ["DROP PIPE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts)
