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
  empty and fills it in the background, so the inherited ``with_data`` flag is
  accepted but not rendered.
* ``TABLESPACE`` and ``WITH (storage_parameter)`` do not exist; passing them
  raises ``UnsupportedFeatureError`` rather than silently dropping them.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- CREATE MATERIALIZED VIEW: https://docs.snowflake.com/en/sql-reference/sql/create-materialized-view
"""
from typing import Any, List, Optional, Tuple, TYPE_CHECKING

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
    ``column_list``) and the core ones (``view_name`` / ``query`` /
    ``column_aliases``), so callers can use either vocabulary.

    Attributes:
        view_name: Materialized view name.
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
        name: Optional[str] = None,
        query: Any = None,
        *,
        view_name: Optional[str] = None,
        as_query: Optional[str] = None,
        column_list: Optional[List[str]] = None,
        column_aliases: Optional[List[str]] = None,
        cluster_by: Optional[List[str]] = None,
        comment: Optional[str] = None,
        or_replace: bool = False,
        if_not_exists: bool = False,
        **core_kwargs: Any,
    ):
        resolved_name = view_name if view_name is not None else name
        if resolved_name is None:
            raise ValueError("CREATE MATERIALIZED VIEW requires a view name")
        if view_name is not None and name is not None and view_name != name:
            raise ValueError("name and view_name disagree; pass only one")

        resolved_query = query if query is not None else as_query
        resolved_columns = column_aliases if column_aliases is not None else column_list
        if column_aliases is not None and column_list is not None:
            raise ValueError("column_list and column_aliases disagree; pass only one")

        super().__init__(
            dialect,
            view_name=resolved_name,
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
        """Alias for view_name (Snowflake field name)."""
        return self.view_name

    @property
    def as_query(self) -> Any:
        """Alias for query (Snowflake field name)."""
        return self.query

    @property
    def column_list(self) -> List[str]:
        """Alias for column_aliases (Snowflake field name)."""
        return self.column_aliases

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE MATERIALIZED VIEW SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).
        """
        return self.dialect.format_create_materialized_view_statement(self)
