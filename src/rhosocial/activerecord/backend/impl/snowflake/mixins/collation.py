# src/rhosocial/activerecord/backend/impl/snowflake/mixins/collation.py
"""Snowflake collation support mixin."""
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.collation import CollateFunction


class SnowflakeCollationMixin:
    """Snowflake COLLATE expression support."""

    def supports_collate_expression(self) -> bool:
        """Snowflake supports expression-level COLLATE."""
        return True

    def validate_collation_name(self, expr: "CollateFunction") -> str:
        """Validate Snowflake collation specs and return their SQL representation."""
        # A schema-qualified collation is the one option the core node still
        # carries; Snowflake's collation specs are spec strings like 'en-ci'
        # and are never schema-qualified, so the option is refused rather than
        # rendered. Core replaced the former open ``**collation_options`` bag
        # with this named parameter, so the refusal names it directly.
        if expr.schema:
            raise UnsupportedFeatureError(self.name, "COLLATE options: schema")
        from ..collation import validate_snowflake_collation_name
        spec = validate_snowflake_collation_name(expr.collation_name, getattr(self, "version", None))
        return f"'{self.escape_sql_string(spec)}'"

    def format_column_attribute(self, attr) -> Tuple[str, tuple]:
        """Snowflake requires a quoted collation specification on a column."""
        from rhosocial.activerecord.base import CollationAttribute
        from ..collation import validate_snowflake_collation_name

        if isinstance(attr, CollationAttribute):
            spec = validate_snowflake_collation_name(attr.name, getattr(self, "version", None))
            return f" COLLATE '{self.escape_sql_string(spec)}'", ()
        return super().format_column_attribute(attr)


__all__ = ['SnowflakeCollationMixin']
