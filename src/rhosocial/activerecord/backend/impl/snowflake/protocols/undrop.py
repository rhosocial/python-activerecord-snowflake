# src/rhosocial/activerecord/backend/impl/snowflake/protocols/undrop.py
"""Snowflake UNDROP protocol.

Feature Source: Snowflake native (not SQL standard)

UNDROP restores an object dropped within its time-travel retention
window (tables, schemas, databases, tags, ...). It is the recovery
companion to time travel.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/undrop
"""
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.undrop import SnowflakeUndropExpression


@runtime_checkable
class SnowflakeUndropSupport(Protocol):
    """Snowflake UNDROP (object restore) protocol."""

    def supports_undrop(self) -> bool:
        """Whether UNDROP is supported."""
        ...

    def format_undrop_statement(
        self, expr: "SnowflakeUndropExpression"
    ) -> str:
        """Format UNDROP statement."""
        ...
