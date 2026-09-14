# src/rhosocial/activerecord/backend/impl/snowflake/mixins/time_travel.py
"""SnowflakeTimeTravelMixin — time travel query support."""


class SnowflakeTimeTravelMixin:
    """Mixin for Snowflake time travel query support."""

    def supports_time_travel(self) -> bool:
        """Snowflake supports time travel queries."""
        return True
