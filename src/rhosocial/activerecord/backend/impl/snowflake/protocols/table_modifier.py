# src/rhosocial/activerecord/backend/impl/snowflake/protocols/table_modifier.py
"""Snowflake table modifier protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake table DDL supports ``CREATE [OR REPLACE] [TRANSIENT|TEMPORARY]
TABLE`` headers, ``DATA_RETENTION_TIME_IN_DAYS`` / ``CHANGE_TRACKING``
options, ``CLUSTER BY`` clustering keys and ``SEARCH OPTIMIZATION`` in
place of traditional indexes.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-table
- https://docs.snowflake.com/en/sql-reference/sql/alter-table
"""
from typing import Protocol, Tuple, runtime_checkable


@runtime_checkable
class SnowflakeTableModifierSupport(Protocol):
    """Snowflake table DDL modifier protocol."""

    def supports_create_or_replace_table(self) -> bool:
        """Whether CREATE OR REPLACE TABLE is supported."""
        ...

    def format_cluster_by_clause(self, expr) -> Tuple[str, tuple]:
        """Format ``CLUSTER BY ( <expr> [, ...] )`` clustering keys."""
        ...

    def supports_transient_table(self) -> bool:
        """Whether TRANSIENT tables are supported."""
        ...

    def supports_cluster_by(self) -> bool:
        """Whether CLUSTER BY clustering keys are supported."""
        ...

    def supports_search_optimization(self) -> bool:
        """Whether SEARCH OPTIMIZATION is supported."""
        ...
