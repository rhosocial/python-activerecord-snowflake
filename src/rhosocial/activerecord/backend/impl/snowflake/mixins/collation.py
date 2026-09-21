# src/rhosocial/activerecord/backend/impl/snowflake/mixins/collation.py
"""Snowflake collation support mixin."""
from typing import Tuple, TYPE_CHECKING

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

    def format_column_attribute(self, attr) -> Tuple[str, tuple]:
        """Snowflake requires a quoted collation specification on a column."""
        from rhosocial.activerecord.base.ddl.attributes import CollationAttribute
        from ..collation import validate_snowflake_collation_name

        if isinstance(attr, CollationAttribute):
            spec = validate_snowflake_collation_name(attr.name, getattr(self, "version", None))
            return f" COLLATE '{self._escape_sql_string(spec)}'", ()
        return super().format_column_attribute(attr)


__all__ = ['SnowflakeCollationMixin']
