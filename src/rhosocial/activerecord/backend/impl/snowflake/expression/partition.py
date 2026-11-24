# src/rhosocial/activerecord/backend/impl/snowflake/expression/partition.py
"""Snowflake partition/clustering DDL expressions.

Snowflake does **not** use declarative (RANGE/LIST/HASH) table partitioning:

* Standard tables are micro-partitioned automatically. The only user control
  over data layout is ``CLUSTER BY ( <expr> [, ...] )`` clustering keys.
* External tables support ``PARTITION BY ( <part_col_name> [, ...] )`` — a
  partition **column list**, not VALUES-based partition definitions.

This module defines Snowflake-owned clause expressions for both forms. The
generic RANGE/LIST/HASH ``PartitionClause`` is *not* valid Snowflake syntax
and is rejected by the Snowflake partition mixin.
"""

from typing import Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeClusterByClause",
    "SnowflakeExternalPartitionClause",
]


class SnowflakeClusterByClause(BaseExpression):
    """Snowflake ``CLUSTER BY ( <expr> [, ...] )`` clustering-key clause.

    Applies to standard (and materialized-view) DDL, not to declarative
    partitioning. Carries the clustering key expressions; SQL generation is
    delegated to ``dialect.format_cluster_by_clause``.

    The node only collects parameters. Whether the collected keys are usable
    (non-empty, expression instances) is decided by the formatter, not here.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        keys: Sequence[BaseExpression],
    ):
        super().__init__(dialect)
        self.keys = list(keys)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_cluster_by_clause"


class SnowflakeExternalPartitionClause(BaseExpression):
    """Snowflake external-table ``PARTITION BY ( <col> [, ...] )`` clause.

    External-table partitioning declares one or more partition **columns**;
    it has no RANGE/LIST/HASH method and no inline ``VALUES`` boundaries.
    This expression therefore carries only the partition columns and renders
    the bare list; it is deliberately **not** a generic ``PartitionClause``,
    because its shape (no method) differs from declarative partitioning.
    SQL generation is delegated to ``dialect.format_external_partition_clause``.

    The node only collects parameters; the formatter decides whether the
    collected columns are usable.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        columns: Sequence[BaseExpression],
    ):
        super().__init__(dialect)
        self.columns = list(columns)

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_external_partition_clause"
