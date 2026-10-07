# src/rhosocial/activerecord/backend/impl/snowflake/mixins/materialized_view.py
"""SnowflakeMaterializedViewMixin — materialized view DDL support."""

from typing import Any, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import MaterializedView

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
            TypeError: ``expr.view`` is not a MaterializedView. Any other object
                kind would have rendered its own name as the view's.
            ValueError: when no defining query is supplied.
            UnsupportedFeatureError: for TABLESPACE / storage parameters and for
                ``WITH DATA`` / ``WITH NO DATA``, none of which Snowflake has.
        """
        # Snowflake's own expression coerces a bare name into a MaterializedView
        # at construction, so both it and the core expression arrive here holding
        # the right kind. The check stays because the object renders itself:
        # without it a View would produce ``CREATE MATERIALIZED VIEW "v"``.
        if not isinstance(expr.view, MaterializedView):
            raise TypeError(
                f"{type(expr).__name__}.view must be a MaterializedView, "
                f"got {type(expr.view).__name__}"
            )
        if expr.tablespace:
            raise UnsupportedFeatureError(self.name, "MATERIALIZED VIEW TABLESPACE")
        if expr.storage_options:
            raise UnsupportedFeatureError(
                self.name, "MATERIALIZED VIEW STORAGE PARAMETERS"
            )
        if getattr(expr, "with_data", False) or getattr(expr, "no_data", False):
            # The clause is absent from Snowflake's grammar entirely: the view
            # is created empty and filled in the background. An explicitly
            # requested spelling is refused by name rather than dropped.
            raise UnsupportedFeatureError(
                self.name,
                "MATERIALIZED VIEW WITH [NO] DATA",
                suggestion=(
                    "Snowflake creates the materialized view empty and fills it "
                    "in the background; it has no WITH DATA / WITH NO DATA clause."
                ),
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
        # The statement already holds the named view, so it renders itself
        # through its own format_materialized_view_object rather than through
        # a name assembled here.
        view_sql, _view_params = expr.view.to_sql()
        parts.append(view_sql)

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
        # in the background. An explicit request for either spelling was refused
        # above, so the inherited flag cannot leak out here.
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
