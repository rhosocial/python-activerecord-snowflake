# src/rhosocial/activerecord/backend/impl/snowflake/mixins/ilike.py
"""Snowflake ILIKE support mixin."""
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.bases import BaseExpression


class SnowflakeILIKEMixin:
    """Snowflake native ILIKE operator support."""

    def supports_ilike(self) -> bool:
        """Snowflake supports the native ILIKE operator."""
        return True

    def format_ilike_expression(
        self, column: "BaseExpression", pattern: str, negate: bool = False
    ) -> Tuple[str, tuple]:
        """Format a native Snowflake [NOT] ILIKE expression."""
        col_sql, col_params = column.to_sql()
        operator = "NOT ILIKE" if negate else "ILIKE"
        return f"{col_sql} {operator} {self.p()}", col_params + (pattern,)


__all__ = ['SnowflakeILIKEMixin']
