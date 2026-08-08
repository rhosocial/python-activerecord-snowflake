# src/rhosocial/activerecord/backend/impl/snowflake/mixins/show.py
"""SnowflakeShowMixin — SHOW statement support."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.show import SnowflakeShowExpression


class SnowflakeShowMixin:
    """Mixin for Snowflake SHOW statement support."""

    def supports_show(self) -> bool:
        """Snowflake supports the SHOW command."""
        return True

    def format_show_statement(
        self, expr: "SnowflakeShowExpression"
    ) -> str:
        """Format a SHOW statement.

        Emits ``SHOW {type} [LIKE 'pattern'] [IN {ACCOUNT|DATABASE|SCHEMA}
        [name]] [LIMIT n]`` (clause order follows the Snowflake docs).

        Args:
            expr: :class:`SnowflakeShowExpression`.

        Returns:
            The formatted SHOW statement SQL string.

        """
        parts = ["SHOW", expr.object_type.value]
        if expr.like is not None:
            parts.append(f"LIKE '{self._escape_sql_string(expr.like)}'")
        if expr.in_scope is not None:
            clause = f"IN {expr.in_scope.value}"
            if expr.in_name:
                clause += f" {self.format_identifier(expr.in_name)}"
            parts.append(clause)
        if expr.limit is not None:
            parts.append(f"LIMIT {int(expr.limit)}")
        return " ".join(parts)
