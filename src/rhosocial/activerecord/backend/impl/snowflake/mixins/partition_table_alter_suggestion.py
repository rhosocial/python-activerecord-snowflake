# src/rhosocial/activerecord/backend/impl/snowflake/mixins/partition_table_alter_suggestion.py
"""Snowflake's partition table_alter suggestion.

Snowflake has no declarative (RANGE/LIST/HASH) table partitioning: standard
tables are micro-partitioned automatically. Data layout is controlled through
``CLUSTER BY`` clustering keys, which is a separate feature, not partitioning.
There is therefore no mechanism to alter the table's partitioning scheme; the explicit "unsupported" state
(``False``) is returned — not silence — so a caller can report it as
unavailable rather than guessing. Unconditional, consults no probe.
"""

from typing import TYPE_CHECKING

from ....suggestion import PartitionTableAlterSuggestion

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionByClause


class SnowflakePartitionTableAlterSuggestionMixin:
    """Answer Snowflake's lack of declarative partitioning explicitly."""

    def suggest_partition_table_alter(
        self, strategy: "PartitionByClause", plan: object
    ) -> PartitionTableAlterSuggestion:
        return PartitionTableAlterSuggestion(False)
