# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/materialized_view.py
"""Snowflake MATERIALIZED VIEW expression.

Snowflake materialized views precompute query results and are refreshed
incrementally in the background. This expression generates
CREATE [OR REPLACE] MATERIALIZED VIEW statements with optional column
aliases, CLUSTER BY keys and COMMENT.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- CREATE MATERIALIZED VIEW: https://docs.snowflake.com/en/sql-reference/sql/create-materialized-view
"""
from typing import List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeCreateMaterializedViewExpression",
]


class SnowflakeCreateMaterializedViewExpression(BaseExpression):
    """Snowflake CREATE [OR REPLACE] MATERIALIZED VIEW statement expression.

    Attributes:
        name: Materialized view name.
        or_replace: Emit ``OR REPLACE``.
        if_not_exists: Emit ``IF NOT EXISTS``.
        column_list: Optional column alias list.
        cluster_by: ``CLUSTER BY`` column list.
        comment: ``COMMENT`` string literal.
        as_query: Query SQL fragment (the ``SELECT`` body).
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        or_replace: bool = False,
        if_not_exists: bool = False,
        column_list: Optional[List[str]] = None,
        cluster_by: Optional[List[str]] = None,
        comment: Optional[str] = None,
        as_query: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.or_replace = or_replace
        self.if_not_exists = if_not_exists
        self.column_list = column_list
        self.cluster_by = cluster_by
        self.comment = comment
        self.as_query = as_query

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE MATERIALIZED VIEW SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_create_materialized_view_statement(self), ()
