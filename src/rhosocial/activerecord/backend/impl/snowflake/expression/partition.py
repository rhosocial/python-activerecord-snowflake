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

from typing import Any, Dict, Optional, Sequence, TYPE_CHECKING

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
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        keys: Sequence[BaseExpression],
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        if not keys:
            raise ValueError("CLUSTER BY requires at least one clustering key")
        for key in keys:
            if not isinstance(key, BaseExpression):
                raise TypeError(
                    "clustering keys must be BaseExpression instances, "
                    f"got {type(key).__name__}"
                )
        if dialect_options is not None and not isinstance(dialect_options, dict):
            raise TypeError(
                "dialect_options must be a dict when provided, "
                f"got {type(dialect_options).__name__}"
            )
        self.keys = list(keys)
        self.dialect_options = dict(dialect_options or {})

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
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        columns: Sequence[BaseExpression],
        *,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        if not columns:
            raise ValueError("PARTITION BY requires at least one partition column")
        for column in columns:
            if not isinstance(column, BaseExpression):
                raise TypeError(
                    "partition columns must be BaseExpression instances, "
                    f"got {type(column).__name__}"
                )
        if dialect_options is not None and not isinstance(dialect_options, dict):
            raise TypeError(
                "dialect_options must be a dict when provided, "
                f"got {type(dialect_options).__name__}"
            )
        self.columns = list(columns)
        self.dialect_options = dict(dialect_options or {})

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_external_partition_clause"
