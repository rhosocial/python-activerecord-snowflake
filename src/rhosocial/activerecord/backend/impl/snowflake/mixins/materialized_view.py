# src/rhosocial/activerecord/backend/impl/snowflake/mixins/materialized_view.py
"""SnowflakeMaterializedViewMixin — materialized view DDL support."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.materialized_view import (
        SnowflakeCreateMaterializedViewExpression,
    )


class SnowflakeMaterializedViewMixin:
    """Mixin for Snowflake materialized view support."""

    def supports_materialized_view(self) -> bool:
        """Snowflake supports native materialized views."""
        return True

    def format_create_materialized_view_statement(
        self, expr: "SnowflakeCreateMaterializedViewExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] MATERIALIZED VIEW statement.

        Args:
            expr: :class:`SnowflakeCreateMaterializedViewExpression`.

        Returns:
            The formatted CREATE MATERIALIZED VIEW SQL string.

        Raises:
            ValueError: when ``as_query`` is not specified.
        """
        if expr.as_query is None:
            raise ValueError(
                "CREATE MATERIALIZED VIEW requires an as_query"
            )
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("MATERIALIZED VIEW")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.name))
        if expr.column_list:
            cols = ", ".join(self.format_identifier(c) for c in expr.column_list)
            parts.append(f"({cols})")
        if expr.cluster_by:
            cols = ", ".join(self.format_identifier(c) for c in expr.cluster_by)
            parts.append(f"CLUSTER BY ({cols})")
        if expr.comment is not None:
            parts.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        parts.extend(["AS", str(expr.as_query)])
        return " ".join(parts)
