# src/rhosocial/activerecord/backend/impl/snowflake/mixins/collation.py
"""Snowflake collation support mixin."""
from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.collation import CollateExpression


class SnowflakeCollationMixin:
    """Snowflake COLLATE expression support."""

    def supports_collate_expression(self) -> bool:
        """Snowflake supports expression-level COLLATE."""
        return True

    def validate_collation_name(self, expr: "CollateExpression") -> str:
        """Validate Snowflake collation specs and return their SQL representation."""
        if expr.collation_options:
            unsupported = ", ".join(sorted(expr.collation_options))
            raise UnsupportedFeatureError(self.name, f"COLLATE options: {unsupported}")
        from ..collation import validate_snowflake_collation_name
        spec = validate_snowflake_collation_name(expr.collation_name, getattr(self, "version", None))
        return f"'{self._escape_sql_string(spec)}'"


__all__ = ['SnowflakeCollationMixin']
