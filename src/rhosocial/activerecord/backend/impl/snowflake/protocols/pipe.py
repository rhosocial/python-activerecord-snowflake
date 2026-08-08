# src/rhosocial/activerecord/backend/impl/snowflake/protocols/pipe.py
"""Snowflake pipe (Snowpipe) protocol.

Feature Source: Snowflake native (not SQL standard)

Pipes continuously load data as files land in a stage. They are managed
via CREATE / ALTER / DROP PIPE statements, with ``AUTO_INGEST`` mode and
REFRESH / PAUSE / RESUME controls.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-pipe
- https://docs.snowflake.com/en/sql-reference/sql/alter-pipe
"""
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.pipe import (
        SnowflakeAlterPipeExpression,
        SnowflakeCreatePipeExpression,
        SnowflakeDropPipeExpression,
    )


@runtime_checkable
class SnowflakePipeSupport(Protocol):
    """Snowflake pipe (Snowpipe) protocol."""

    def supports_pipes(self) -> bool:
        """Whether pipes are supported."""
        ...

    def format_create_pipe_statement(
        self, expr: "SnowflakeCreatePipeExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] PIPE statement."""
        ...

    def format_alter_pipe_statement(
        self, expr: "SnowflakeAlterPipeExpression"
    ) -> str:
        """Format ALTER PIPE statement (REFRESH / SET / PAUSE / RESUME)."""
        ...

    def format_drop_pipe_statement(
        self, expr: "SnowflakeDropPipeExpression"
    ) -> str:
        """Format DROP PIPE statement."""
        ...
