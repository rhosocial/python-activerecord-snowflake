# src/rhosocial/activerecord/backend/impl/snowflake/mixins/partition_drop_suggestion.py
"""Snowflake's partition drop suggestion.

Snowflake has no declarative (RANGE/LIST/HASH) table partitioning: standard
tables are micro-partitioned automatically. Data layout is controlled through
``CLUSTER BY`` clustering keys, which is a separate feature, not partitioning.
There is therefore no mechanism to drop or detach a partition; the explicit "unsupported" state
(``False``) is returned — not silence — so a caller can report it as
unavailable rather than guessing. Unconditional, consults no probe.
"""

from typing import TYPE_CHECKING

from ....suggestion import PartitionDropSuggestion

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.statements import PartitionByClause


class SnowflakePartitionDropSuggestionMixin:
    """Answer Snowflake's lack of declarative partitioning explicitly."""

    def suggest_partition_drop(
        self, strategy: "PartitionByClause", plan: object
    ) -> PartitionDropSuggestion:
        return PartitionDropSuggestion(False)
