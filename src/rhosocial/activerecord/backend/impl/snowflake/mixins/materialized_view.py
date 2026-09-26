# src/rhosocial/activerecord/backend/impl/snowflake/mixins/materialized_view.py
"""SnowflakeMaterializedViewMixin — materialized view DDL support."""

from typing import Any, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from ..expression.ddl.materialized_view import (
        SnowflakeCreateMaterializedViewExpression,
    )


class SnowflakeMaterializedViewMixin:
    """Mixin for Snowflake materialized view support.

    Must stay before the core ``ViewMixin`` in ``SnowflakeDialect`` so this
    formatter takes precedence.
    """

    def supports_materialized_view(self) -> bool:
        """Snowflake supports native materialized views."""
        return True

    def format_create_materialized_view_statement(
        self, expr: "SnowflakeCreateMaterializedViewExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE [OR REPLACE] MATERIALIZED VIEW statement.

        Accepts both ``SnowflakeCreateMaterializedViewExpression`` and the core
        ``CreateMaterializedViewExpression``; the defining query may be a
        ``QueryExpression`` or a raw SQL string.

        Args:
            expr: Materialized view create expression.

        Returns:
            Tuple of (SQL string, empty params tuple).

        Raises:
            ValueError: when no defining query is supplied.
            UnsupportedFeatureError: for TABLESPACE / storage parameters, which
                Snowflake does not have.
        """
        if expr.tablespace:
            raise UnsupportedFeatureError(self.name, "MATERIALIZED VIEW TABLESPACE")
        if expr.storage_options:
            raise UnsupportedFeatureError(
                self.name, "MATERIALIZED VIEW STORAGE PARAMETERS"
            )

        query_sql = self._materialized_view_query_sql(expr)
        if query_sql is None:
            raise ValueError("CREATE MATERIALIZED VIEW requires a query")

        parts = ["CREATE"]
        if getattr(expr, "or_replace", False):
            parts.append("OR REPLACE")
        parts.append("MATERIALIZED VIEW")
        if getattr(expr, "if_not_exists", False):
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.view_name))

        column_aliases = getattr(expr, "column_aliases", None)
        if column_aliases:
            cols = ", ".join(self.format_identifier(col) for col in column_aliases)
            parts.append(f"({cols})")

        cluster_by = getattr(expr, "cluster_by", None)
        if cluster_by:
            cols = ", ".join(self.format_identifier(col) for col in cluster_by)
            parts.append(f"CLUSTER BY ({cols})")

        comment = getattr(expr, "comment", None)
        if comment is not None:
            parts.append(f"COMMENT = '{self._escape_sql_string(comment)}'")

        # Snowflake has no WITH [NO] DATA: the view is created empty and filled
        # in the background, so the inherited ``with_data`` flag is not rendered.
        parts.extend(["AS", query_sql])
        return " ".join(parts), ()

    def _materialized_view_query_sql(self, expr: Any):
        """Return the defining query as SQL text, or None when absent.

        Snowflake's own expression carries a raw ``as_query`` string; the core
        expression carries a ``QueryExpression``.
        """
        query = getattr(expr, "query", None)
        if query is None:
            return None
        if isinstance(query, str):
            return query
        sql, _params = query.to_sql()
        return sql
