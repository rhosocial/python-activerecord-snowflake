# src/rhosocial/activerecord/backend/impl/snowflake/protocols/partition.py
"""Snowflake partition support protocol.

Snowflake supports PARTITION BY for external tables.
Standard tables use automatic micro-partitioning and CLUSTER BY.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SnowflakePartitionSupport(Protocol):
    """Protocol for Snowflake partition support.

    Snowflake supports RANGE and LIST partitioning for external tables.
    Standard tables use automatic micro-partitioning.
    """
    pass
