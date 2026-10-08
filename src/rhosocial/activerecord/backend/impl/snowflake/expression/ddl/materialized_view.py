# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/materialized_view.py
"""Snowflake MATERIALIZED VIEW expression.

Snowflake materialized views precompute query results and are refreshed
incrementally in the background. This expression generates
CREATE [OR REPLACE] MATERIALIZED VIEW statements with optional column
aliases, CLUSTER BY keys and COMMENT.

The expression extends the core
:class:`~rhosocial.activerecord.backend.expression.statements.ddl_view.CreateMaterializedViewExpression`
so the generic MV API works on Snowflake, and layers the Snowflake-specific
options on top.

Snowflake divergence from the generic expression
------------------------------------------------
* ``OR REPLACE`` and ``IF NOT EXISTS`` are mutually exclusive.
* There is no ``WITH [NO] DATA`` clause: Snowflake always creates the view
  empty and fills it in the background, so an explicit ``with_data`` /
  ``no_data`` request is refused by name rather than silently dropped.
* ``TABLESPACE`` and ``WITH (storage_parameter)`` do not exist; passing them
  raises ``UnsupportedFeatureError`` rather than silently dropping them.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- CREATE MATERIALIZED VIEW: https://docs.snowflake.com/en/sql-reference/sql/create-materialized-view
"""
from typing import Any, List, Optional, Tuple, Union, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.objects import MaterializedView
from rhosocial.activerecord.backend.expression.statements.ddl_view import (
    CreateMaterializedViewExpression,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeCreateMaterializedViewExpression",
]


class SnowflakeCreateMaterializedViewExpression(CreateMaterializedViewExpression):
    """Snowflake CREATE [OR REPLACE] MATERIALIZED VIEW statement expression.

    Accepts both the Snowflake field names (``name`` / ``as_query`` /
    ``column_list``) and the core ones (``view`` / ``query`` /
    ``column_aliases``), so callers can use either vocabulary. The view may be
    given as a ``MaterializedView`` object or as a bare name, which is wrapped
    in one.

    Attributes:
        view: The ``MaterializedView`` object being created; a bare name is
            accepted and wrapped in one.
        query: Defining query — a ``QueryExpression`` or a raw SQL string.
        column_aliases: Optional column alias list.
        or_replace: Emit ``OR REPLACE`` (mutually exclusive with ``if_not_exists``).
        if_not_exists: Emit ``IF NOT EXISTS``.
        cluster_by: ``CLUSTER BY`` column list.
        comment: ``COMMENT`` string literal.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: Optional[Union[str, "MaterializedView"]] = None,
        query: Any = None,
        *,
        view_name: Optional[Union[str, "MaterializedView"]] = None,
        view: Optional[Union[str, "MaterializedView"]] = None,
        as_query: Optional[str] = None,
        column_list: Optional[List[str]] = None,
        column_aliases: Optional[List[str]] = None,
        cluster_by: Optional[List[str]] = None,
        comment: Optional[str] = None,
        or_replace: bool = False,
        if_not_exists: bool = False,
        **core_kwargs: Any,
    ):
        resolved_view = view if view is not None else view_name
        if resolved_view is None:
            resolved_view = name
        if resolved_view is None:
            raise ValueError("CREATE MATERIALIZED VIEW requires a view")
        if isinstance(resolved_view, str):
            resolved_view = MaterializedView(dialect, resolved_view)

        resolved_query = query if query is not None else as_query
        resolved_columns = column_aliases if column_aliases is not None else column_list
        if column_aliases is not None and column_list is not None:
            raise ValueError("column_list and column_aliases disagree; pass only one")

        super().__init__(
            dialect,
            view=resolved_view,
            query=resolved_query,
            column_aliases=resolved_columns,
            **core_kwargs,
        )
        if or_replace and if_not_exists:
            raise ValueError(
                "Snowflake rejects OR REPLACE together with IF NOT EXISTS"
            )
        self.or_replace = or_replace
        self.if_not_exists = if_not_exists
        self.cluster_by = cluster_by
        self.comment = comment

    @property
    def name(self) -> str:
        """Alias for the view object's own name (Snowflake field name)."""
        return self.view.name

    @property
    def as_query(self) -> Any:
        """Alias for query (Snowflake field name)."""
        return self.query

    @property
    def column_list(self) -> List[str]:
        """Alias for column_aliases (Snowflake field name)."""
        return self.column_aliases

    def get_params(self) -> dict:
        """Return the core vocabulary only, so the expression round-trips.

        The default introspection reads this class's ``__init__`` signature,
        which lists *both* spellings of every aliased field: ``name`` and
        ``view``, ``as_query`` and ``query``, ``column_list`` and
        ``column_aliases``, plus the ``core_kwargs`` catch-all that has no
        attribute to read. Reconstruction therefore handed the constructor both
        halves of each pair, and ``column_aliases is not None and column_list is
        not None`` is exactly the disagreement this class refuses -- so
        serialising any instance of it raised and it could not be deserialised at
        all.

        The aliases exist so a *caller* may use either vocabulary. There is no
        reason for a *serialised* form to carry both, and the core spelling is
        the one that round-trips: it is what the base class writes, what the
        formatter reads, and what reconstruction needs. Emitting it alone keeps
        the two vocabularies available to callers without making the wire format
        ambiguous.
        """
        return {
            "view": self.view,
            "query": self.query,
            "column_aliases": self.column_aliases,
            "cluster_by": self.cluster_by,
            "comment": self.comment,
            "or_replace": self.or_replace,
            "if_not_exists": self.if_not_exists,
        }

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE MATERIALIZED VIEW SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).
        """
        return self.dialect.format_create_materialized_view_statement(self)
