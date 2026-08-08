# src/rhosocial/activerecord/backend/impl/snowflake/protocols/stream.py
"""Snowflake stream (change data capture) protocol.

Feature Source: Snowflake native (not SQL standard)

Streams track row-level changes (CDC) on a source object. They are created
via ``CREATE [OR REPLACE] STREAM ... ON {TABLE|VIEW|EXTERNAL TABLE|STAGE}``
with optional ``APPEND_ONLY`` / ``INSERT_ONLY`` controls and ``AT`` /
``BEFORE`` time-travel points, and dropped via ``DROP STREAM``.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-stream
"""
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.stream import (
        SnowflakeCreateStreamExpression,
        SnowflakeDropStreamExpression,
    )


@runtime_checkable
class SnowflakeStreamSupport(Protocol):
    """Snowflake stream (change data capture) protocol."""

    def supports_stream(self) -> bool:
        """Whether streams are supported."""
        ...

    def format_create_stream_statement(
        self, expr: "SnowflakeCreateStreamExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] STREAM statement."""
        ...

    def format_drop_stream_statement(
        self, expr: "SnowflakeDropStreamExpression"
    ) -> str:
        """Format DROP STREAM statement."""
        ...
