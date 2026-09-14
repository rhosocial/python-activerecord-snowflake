# src/rhosocial/activerecord/backend/impl/snowflake/mixins/variant.py
"""SnowflakeVariantMixin — VARIANT semi-structured data type support."""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.variant import (
        SnowflakeVariantPathAccessExpression,
        SnowflakeVariantCastExpression,
    )


class SnowflakeVariantMixin:
    """Mixin for Snowflake VARIANT semi-structured data type support."""

    def supports_variant_type(self) -> bool:
        """Snowflake supports VARIANT type."""
        return True

    def format_variant_path_access(
        self, expr: "SnowflakeVariantPathAccessExpression"
    ) -> Tuple[str, tuple]:
        """Format VARIANT path access expression using colon notation.

        Args:
            expr: :class:`SnowflakeVariantPathAccessExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return f'{expr.column}:{expr.path}', ()

    def format_variant_cast(
        self, expr: "SnowflakeVariantCastExpression"
    ) -> Tuple[str, tuple]:
        """Format VARIANT path access with explicit cast.

        Args:
            expr: :class:`SnowflakeVariantCastExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return f'{expr.column}:{expr.path}::{expr.target_type}', ()
