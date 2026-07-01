# src/rhosocial/activerecord/backend/impl/snowflake/protocols/time_travel.py
"""Snowflake time travel query protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake supports querying historical data at a specific point in time
using AT/BEFORE clauses:
- AT(TIMESTAMP => 'timestamp'): Query data as of a specific timestamp
- AT(OFFSET => N): Query data N seconds ago
- AT(STATEMENT => 'uuid'): Query data as of a statement
- BEFORE(STATEMENT => 'uuid'): Query data before a statement
- BEFORE(TIMESTAMP => 'timestamp'): Query data before a timestamp

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/constructs/at-before
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class SnowflakeTimeTravelSupport(Protocol):
    """Snowflake time travel query protocol."""

    def supports_time_travel(self) -> bool:
        """Whether time travel queries are supported."""
        ...

    def format_time_travel_at_timestamp(self, timestamp: str) -> str:
        """Format AT(TIMESTAMP => ...) clause."""
        ...

    def format_time_travel_at_offset(self, seconds: int) -> str:
        """Format AT(OFFSET => ...) clause."""
        ...

    def format_time_travel_before_timestamp(self, timestamp: str) -> str:
        """Format BEFORE(TIMESTAMP => ...) clause."""
        ...