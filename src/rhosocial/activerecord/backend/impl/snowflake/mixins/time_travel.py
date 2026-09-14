# src/rhosocial/activerecord/backend/impl/snowflake/mixins/time_travel.py
"""SnowflakeTimeTravelMixin — time travel query formatting."""
from typing import Tuple


class SnowflakeTimeTravelMixin:
    """Mixin for Snowflake time travel query support."""

    def supports_time_travel(self) -> bool:
        """Snowflake supports time travel queries."""
        return True

    def format_time_travel_at_timestamp(self, timestamp: str) -> Tuple[str, tuple]:
        """Format AT(TIMESTAMP => ...) clause."""
        return f"AT(TIMESTAMP => '{timestamp}')", ()

    def format_time_travel_at_offset(self, seconds: int) -> Tuple[str, tuple]:
        """Format AT(OFFSET => ...) clause."""
        return f"AT(OFFSET => {seconds})", ()

    def format_time_travel_before_timestamp(self, timestamp: str) -> Tuple[str, tuple]:
        """Format BEFORE(TIMESTAMP => ...) clause."""
        return f"BEFORE(TIMESTAMP => '{timestamp}')", ()