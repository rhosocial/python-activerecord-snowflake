# src/rhosocial/activerecord/backend/impl/snowflake/expression/partition.py
"""Snowflake partition expression — PARTITION BY clause for DDL."""

from typing import Any, Dict, Optional, Sequence, Type

from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.statements.ddl_partition import (
    PartitionClause,
    PartitionStrategy,
)


class SnowflakePartitionClause(PartitionClause):
    """Snowflake PARTITION BY clause with explicit partition definitions.

    Snowflake supports PARTITION BY on external tables with named
    partitions and boundary values.
    """

    strategy_type: Type = PartitionStrategy

    def __init__(
        self,
        dialect: "Any",
        method: PartitionStrategy,
        keys: Sequence[BaseExpression],
        *,
        partitions: Optional[list] = None,
        dialect_options: Optional[Dict[str, Any]] = None,
    ):
        combined_options = dict(dialect_options or {})
        if partitions:
            combined_options["partitions"] = partitions
        super().__init__(dialect, method, keys, dialect_options=combined_options)
