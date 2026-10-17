# src/rhosocial/activerecord/backend/impl/snowflake/mixins/materialized_view.py
"""SnowflakeMaterializedViewMixin — materialized view DDL support."""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import MaterializedView

from ..expression.ddl.materialized_view import (
    SnowflakeCreateMaterializedViewExpression,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_view import (
        CreateMaterializedViewStatement,
    )


class SnowflakeMaterializedViewMixin:
    """Mixin for Snowflake materialized view support.

    Must stay before the core ``ViewMixin`` in ``SnowflakeDialect`` so this
    formatter takes precedence.
    """

    def supports_materialized_view(self) -> bool:
        """Snowflake supports native materialized views."""
        return True

    def supports_with_data_clause(self) -> bool:
        """Snowflake has no ``WITH [NO] DATA`` population clause.

        All three consumers core declares the probe for lack it here:

        * ``CREATE TABLE ... AS <query>`` -- the CTAS grammar ends at the
          query;
        * ``CREATE MATERIALIZED VIEW ... AS <select_statement>`` -- the view
          is created empty and filled in the background; the ``WITH DATA``
          token on that page belongs to ``WITH DATA METRIC FUNCTION``, a
          data-quality binding, not to a population clause;
        * ``REFRESH MATERIALIZED VIEW`` -- Snowflake has no such statement
          (the command reference has no page for it); maintenance is
          automatic.

        Core's three consumers (CTAS, CREATE MATERIALIZED VIEW, REFRESH
        MATERIALIZED VIEW) read this probe and refuse either spelling by
        name; this dialect's own materialized view formatter refuses it
        before the shared gate is reached.

        https://docs.snowflake.com/en/sql-reference/sql/create-table
        https://docs.snowflake.com/en/sql-reference/sql/create-materialized-view
        """
        return False

    def format_create_materialized_view_statement(
        self, expr: "SnowflakeCreateMaterializedViewExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE [OR REPLACE] MATERIALIZED VIEW statement.

        Accepts both ``SnowflakeCreateMaterializedViewExpression`` and the core
        ``CreateMaterializedViewStatement``; the defining query may be a
        ``QueryStatement`` or a raw SQL string.

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
        if expr.with_data or expr.no_data:
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
        # ``or_replace`` / ``if_not_exists`` / ``cluster_by`` / ``comment``
        # are the Snowflake expression's own fields: the core statement this
        # formatter also accepts declares none of them, so the subclass is
        # asked by name rather than probed for attributes its contract does
        # not carry.
        if isinstance(expr, SnowflakeCreateMaterializedViewExpression) and expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("MATERIALIZED VIEW")
        if isinstance(expr, SnowflakeCreateMaterializedViewExpression) and expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        # The statement already holds the named view, so it renders itself
        # through its own format_materialized_view_object rather than through
        # a name assembled here.
        view_sql, _view_params = expr.view.to_sql()
        parts.append(view_sql)

        column_aliases = expr.column_aliases
        if column_aliases:
            cols = ", ".join(self.format_identifier(col) for col in column_aliases)
            parts.append(f"({cols})")

        if isinstance(expr, SnowflakeCreateMaterializedViewExpression):
            if expr.cluster_by:
                cols = ", ".join(
                    self.format_identifier(col) for col in expr.cluster_by
                )
                parts.append(f"CLUSTER BY ({cols})")
            if expr.comment is not None:
                parts.append(f"COMMENT = '{self._escape_sql_string(expr.comment)}'")

        # Snowflake has no WITH [NO] DATA: the view is created empty and filled
        # in the background. An explicit request for either spelling was refused
        # above, so the inherited flag cannot leak out here.
        parts.extend(["AS", query_sql])
        return " ".join(parts), ()

    def _materialized_view_query_sql(self, expr: "CreateMaterializedViewStatement"):
        """Return the defining query as SQL text, or None when absent.

        Snowflake's own expression coerces the query from either vocabulary
        but stores it in the core ``query`` field, so the declared field is
        read directly: the core statement declares it too, and a Snowflake
        expression may hold ``None`` when no query was given.
        """
        query = expr.query
        if query is None:
            return None
        if isinstance(query, str):
            return query
        sql, _params = query.to_sql()
        return sql
