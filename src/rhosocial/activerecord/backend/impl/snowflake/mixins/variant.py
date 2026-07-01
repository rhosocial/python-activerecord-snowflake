# src/rhosocial/activerecord/backend/impl/snowflake/mixins/variant.py
"""SnowflakeVariantMixin — VARIANT semi-structured data type support."""


class SnowflakeVariantMixin:
    """Mixin for Snowflake VARIANT semi-structured data type support."""

    def supports_variant_type(self) -> bool:
        """Snowflake supports VARIANT type."""
        return True

    def format_variant_path_access(self, column: str, path: str) -> str:
        """Format VARIANT path access expression using colon notation."""
        return f'{column}:{path}'

    def format_variant_cast(self, column: str, path: str, target_type: str) -> str:
        """Format VARIANT path access with explicit cast."""
        return f'{column}:{path}::{target_type}'