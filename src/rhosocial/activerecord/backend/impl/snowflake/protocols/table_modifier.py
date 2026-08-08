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
from typing import Iterable, Optional, Protocol, runtime_checkable


@runtime_checkable
class SnowflakeTableModifierSupport(Protocol):
    """Snowflake table DDL modifier protocol."""

    def supports_create_or_replace_table(self) -> bool:
        """Whether CREATE OR REPLACE TABLE is supported."""
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

    def format_create_table_modifier(
        self,
        *,
        or_replace: bool = False,
        transient: bool = False,
        temporary: bool = False,
    ) -> str:
        """Format CREATE TABLE header modifier tokens."""
        ...

    def format_create_table_options(
        self,
        *,
        data_retention_time_in_days: Optional[int] = None,
        change_tracking: Optional[bool] = None,
        comment: Optional[str] = None,
    ) -> str:
        """Format trailing CREATE TABLE options."""
        ...

    def format_alter_table_cluster_by(
        self, table: str, columns: Iterable[str]
    ) -> str:
        """Format ALTER TABLE ... CLUSTER BY statement."""
        ...

    def format_drop_clustering_key(self, table: str) -> str:
        """Format ALTER TABLE ... DROP CLUSTERING KEY statement."""
        ...

    def format_add_search_optimization(
        self,
        table: str,
        on: Optional[Iterable[str]] = None,
        method: str = "EQUALITY",
    ) -> str:
        """Format ALTER TABLE ... ADD SEARCH OPTIMIZATION statement."""
        ...
