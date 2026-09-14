# src/rhosocial/activerecord/backend/impl/snowflake/mixins/ilike.py
"""Snowflake ILIKE support mixin."""
from typing import Any, Tuple


class SnowflakeILIKEMixin:
    """Snowflake native ILIKE operator support."""

    def supports_ilike(self) -> bool:
        """Snowflake supports the native ILIKE operator."""
        return True

    def format_ilike_expression(
        self, column: Any, pattern: str, negate: bool = False
    ) -> Tuple[str, tuple]:
        """Format a native Snowflake [NOT] ILIKE expression."""
        if isinstance(column, str):
            col_sql = self.format_identifier(column)
        elif hasattr(column, "to_sql"):
            col_sql, _ = column.to_sql()
        else:
            col_sql = str(column)
        operator = "NOT ILIKE" if negate else "ILIKE"
        return f"{col_sql} {operator} {self.p()}", (pattern,)


__all__ = ['SnowflakeILIKEMixin']
