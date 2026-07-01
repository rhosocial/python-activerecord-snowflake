# src/rhosocial/activerecord/backend/impl/snowflake/mixins/time_travel.py
"""SnowflakeTimeTravelMixin — time travel query formatting."""


class SnowflakeTimeTravelMixin:
    """Mixin for Snowflake time travel query support."""

    def supports_time_travel(self) -> bool:
        """Snowflake supports time travel queries."""
        return True

    def format_time_travel_at_timestamp(self, timestamp: str) -> str:
        """Format AT(TIMESTAMP => ...) clause."""
        return f"AT(TIMESTAMP => '{timestamp}')"

    def format_time_travel_at_offset(self, seconds: int) -> str:
        """Format AT(OFFSET => ...) clause."""
        return f"AT(OFFSET => {seconds})"

    def format_time_travel_before_timestamp(self, timestamp: str) -> str:
        """Format BEFORE(TIMESTAMP => ...) clause."""
        return f"BEFORE(TIMESTAMP => '{timestamp}')"