# src/rhosocial/activerecord/backend/impl/snowflake/mixins/array.py
"""SnowflakeArrayMixin — ARRAY type formatting."""


class SnowflakeArrayMixin:
    """Mixin for Snowflake ARRAY type support."""

    def supports_array_type(self) -> bool:
        """Snowflake supports ARRAY type."""
        return True

    def format_array_construct(self, elements: str) -> str:
        """Format array construction expression."""
        return f'ARRAY_CONSTRUCT({elements})'

    def format_array_access(self, array_expr: str, index: str) -> str:
        """Format array element access expression."""
        return f'{array_expr}[{index}]'