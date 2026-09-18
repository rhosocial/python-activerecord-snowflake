# src/rhosocial/activerecord/backend/impl/snowflake/mixins/dql.py
"""Snowflake DQL support mixin."""


class SnowflakeDQLMixin:
    """Snowflake DQL (Data Query Language) support."""

    def supports_offset_without_limit(self) -> bool:
        """Snowflake supports OFFSET without LIMIT."""
        return True

    def supports_fetch_with_ties(self) -> bool:
        """Snowflake does not support FETCH ... WITH TIES."""
        return False

    def supports_nulls_first_last(self) -> bool:
        """Snowflake supports explicit NULLS FIRST / NULLS LAST ordering."""
        return True


__all__ = ['SnowflakeDQLMixin']
