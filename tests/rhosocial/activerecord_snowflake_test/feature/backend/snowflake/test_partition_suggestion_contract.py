# tests/rhosocial/activerecord_snowflake_test/feature/backend/snowflake/test_partition_suggestion_contract.py
"""Snowflake's eight partition suggestions answer an explicit "unsupported".

Snowflake has no declarative (RANGE/LIST/HASH) table partitioning: standard
tables are micro-partitioned automatically, and data layout is controlled by
``CLUSTER BY`` clustering keys, which is not partitioning. Every partition
lifecycle suggestion therefore reports the explicit ``False`` state rather than
silence, so a caller can distinguish "this backend has no mechanism" from "no
action needed".
"""

import pytest

from rhosocial.activerecord.backend.dialect.partition_capability import (
    PartitionCapability,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.suggestion.protocols import (
    PartitionAddSuggestionSupport,
    PartitionBuildSuggestionSupport,
    PartitionDropSuggestionSupport,
    PartitionMergeSuggestionSupport,
    PartitionRetentionSuggestionSupport,
    PartitionSplitSuggestionSupport,
    PartitionTableAlterSuggestionSupport,
    PartitionTableDropSuggestionSupport,
)

INTENTS = [
    ("build", "suggest_partition_build", PartitionBuildSuggestionSupport),
    ("add", "suggest_partition_add", PartitionAddSuggestionSupport),
    ("drop", "suggest_partition_drop", PartitionDropSuggestionSupport),
    ("retention", "suggest_partition_retention", PartitionRetentionSuggestionSupport),
    ("table_drop", "suggest_partition_table_drop", PartitionTableDropSuggestionSupport),
    ("table_alter", "suggest_partition_table_alter", PartitionTableAlterSuggestionSupport),
    ("split", "suggest_partition_split", PartitionSplitSuggestionSupport),
    ("merge", "suggest_partition_merge", PartitionMergeSuggestionSupport),
]


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


@pytest.mark.parametrize("intent,method,protocol", INTENTS, ids=[i[0] for i in INTENTS])
def test_every_protocol_is_satisfied(dialect, intent, method, protocol):
    assert isinstance(dialect, protocol)


@pytest.mark.parametrize("intent,method,protocol", INTENTS, ids=[i[0] for i in INTENTS])
def test_every_intent_reports_explicit_unsupported(dialect, intent, method, protocol):
    suggestion = getattr(dialect, method)(None, None)
    assert suggestion.operations is False


def test_nothing_is_silently_no_action(dialect):
    """Silence (None) would hide the capability gap; False names it."""
    for _intent, method, _protocol in INTENTS:
        assert getattr(dialect, method)(None, None).operations is not None


def test_automatic_partitioning_does_not_turn_a_suggestion_into_an_action(dialect):
    """The capability is AUTOMATIC, yet there is no partition DDL to suggest.

    Micro-partitions exist without user control, so no build/add/drop/... intent
    has an addressable object to operate on. The suggestions stay the explicit
    ``False`` state; a capability value never substitutes for a DDL spelling.
    """
    assert dialect.partition_capability() is PartitionCapability.AUTOMATIC
    assert dialect.supports_table_partitioning() is False
    for _intent, method, _protocol in INTENTS:
        assert getattr(dialect, method)(None, None).operations is False
