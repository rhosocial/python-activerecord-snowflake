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

The clause is rendered by ``format_temporal_options``, the same hook the
shared ``format_named_relation`` uses, so a three-level name and its time-travel
suffix stay separate concerns.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/constructs/at-before
"""
from typing import Any, Protocol, Tuple, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.datetime import (
        TemporalOptionsExpression,
    )


@runtime_checkable
class SnowflakeTimeTravelSupport(Protocol):
    """Snowflake time travel query protocol."""

    def supports_time_travel(self) -> bool:
        """Whether time travel queries are supported."""
        ...

    def format_time_travel_point(self, keyword: str, point: Tuple[str, Any]) -> str:
        """Render a single AT/BEFORE clause."""
        ...

    def format_temporal_options(self, expr: "TemporalOptionsExpression") -> Tuple[str, tuple]:
        """Render the time-travel clause of a relation reference."""
        ...
