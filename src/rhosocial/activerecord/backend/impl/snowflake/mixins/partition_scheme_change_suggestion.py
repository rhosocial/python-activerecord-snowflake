# src/rhosocial/activerecord/backend/impl/snowflake/mixins/partition_scheme_change_suggestion.py
"""Snowflake's partition-scheme-change suggestion.

Snowflake's ``partition_capability()`` is ``AUTOMATIC``: standard tables are
divided into micro-partitions by the engine, with no user-addressable
partition names, ids or boundaries. ``CLUSTER BY`` controls *clustering* --
which micro-partitions hold which values -- and is a clustering action in
``ALTER TABLE``, not partition DDL. ``supports_table_partitioning()`` is
``False`` because no declarative (RANGE/LIST/HASH) partitioning exists; the
eight partition-lifecycle suggestions all answer ``False`` for the same
reason.

A change between two partition declarations therefore has no DDL statement to
suggest, automatic or otherwise. The ``AUTOMATIC`` capability must never be
turned into a fabricated build/drop/alter chain: the explicit ``False`` state
is returned, with the engine-managed reason recorded here.

Evidence: https://docs.snowflake.com/en/user-guide/tables-clustering-micropartitions
and the ``partition_capability()`` / ``supports_table_partitioning()`` probes
in :mod:`..partition`.
"""
from dataclasses import replace

from rhosocial.activerecord.backend.suggestion.definitions import (
    PartitionSchemeChangeSuggestion,
)


class SnowflakePartitionSchemeChangeSuggestionMixin:
    """Answer the partition-scheme-change decision point as unsupported."""

    def suggest_partition_scheme_change(
        self, point: PartitionSchemeChangeSuggestion
    ) -> PartitionSchemeChangeSuggestion:
        """Return ``point`` with ``operations=False`` (unaddressable)."""
        return replace(point, operations=False)


__all__ = ["SnowflakePartitionSchemeChangeSuggestionMixin"]
