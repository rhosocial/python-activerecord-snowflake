# src/rhosocial/activerecord/backend/impl/snowflake/protocols/partition.py
"""Snowflake partition support protocol.

Snowflake has no declarative (RANGE/LIST/HASH) table partitioning. Standard
tables use automatic micro-partitioning with optional ``CLUSTER BY``.
External tables support ``PARTITION BY ( <col> [, ...] )``.
"""

from typing import Tuple, Protocol, runtime_checkable


@runtime_checkable
class SnowflakePartitionSupport(Protocol):
    """Protocol for Snowflake partition support.

    Declarative RANGE/LIST/HASH partitioning is not supported; external
    tables declare partition columns via ``PARTITION BY (cols)``.
    """

    def supports_external_table_partitioning(self) -> bool:
        """Whether external-table ``PARTITION BY (cols)`` is supported."""
        ...

    def format_external_partition_clause(self, expr) -> Tuple[str, tuple]:
        """Format ``PARTITION BY ( <col> [, ...] )`` for external tables."""
        ...
