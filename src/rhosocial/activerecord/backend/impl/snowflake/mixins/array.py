# src/rhosocial/activerecord/backend/impl/snowflake/mixins/array.py
"""SnowflakeArrayMixin — ARRAY type support."""


class SnowflakeArrayMixin:
    """Mixin for Snowflake ARRAY type support."""

    def supports_array_type(self) -> bool:
        """Snowflake supports ARRAY type."""
        return True
