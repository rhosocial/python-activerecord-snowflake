# src/rhosocial/activerecord/backend/impl/snowflake/mixins/undrop.py
"""SnowflakeUndropMixin — UNDROP support."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.undrop import SnowflakeUndropExpression


class SnowflakeUndropMixin:
    """Mixin for Snowflake UNDROP (object restore) support."""

    def supports_undrop(self) -> bool:
        """Snowflake supports UNDROP."""
        return True

    def format_undrop_statement(
        self, expr: "SnowflakeUndropExpression"
    ) -> str:
        """Format UNDROP statement.

        Args:
            expr: :class:`SnowflakeUndropExpression`.

        Returns:
            The formatted UNDROP SQL string.

        """
        return (
            f"UNDROP {expr.object_type.value} "
            f"{self.format_identifier(expr.name)}"
        )
