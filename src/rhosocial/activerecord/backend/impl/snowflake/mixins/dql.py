# src/rhosocial/activerecord/backend/impl/snowflake/mixins/dql.py
"""Snowflake DQL support mixin."""


class SnowflakeDQLMixin:
    """Snowflake DQL (Data Query Language) support."""

    def supports_offset_without_limit(self) -> bool:
        """Snowflake supports OFFSET without LIMIT."""
        return True


__all__ = ['SnowflakeDQLMixin']
