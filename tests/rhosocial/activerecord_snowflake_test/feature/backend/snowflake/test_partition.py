# tests/rhosocial/activerecord_snowflake_test/feature/backend/snowflake/test_partition.py
"""Tests for Snowflake partition/clustering DDL support.

Snowflake has no declarative (RANGE/LIST/HASH) partitioning: standard tables
are micro-partitioned automatically with optional CLUSTER BY, and external
tables use PARTITION BY (cols). These tests assert the honest capability bits
and the two valid clause forms.

The capability is ``AUTOMATIC`` rather than ``UNSUPPORTED``: the engine
partitions every table itself, so there is partitioning, but no addressable
partition DDL. ``supports_table_partitioning()`` stays ``False`` because it
answers only whether such DDL exists.
"""

from typing import Set

import pytest

from rhosocial.activerecord.backend.dialect import PartitionSupport
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.partition_capability import (
    PartitionCapability,
)
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.statements import (
    PartitionByRangeClause,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import SnowflakePartitionMixin
from rhosocial.activerecord.backend.impl.snowflake.protocols import SnowflakePartitionSupport
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeAlterTableClusteringStatement,
    SnowflakeClusterByClause,
    SnowflakeExternalPartitionClause,
)


class MockKey(BaseExpression):
    """Mock key expression for testing."""

    def __init__(self, dialect, name="col"):
        super().__init__(dialect)
        self._name = name

    def to_sql(self):
        return (f'"{self._name}"', ())


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakePartitionProtocolConformance:
    """Verify SnowflakePartitionSupport protocol and mixin."""

    def test_partition_mixin_satisfies_partition_support_protocol(self):
        """SnowflakePartitionMixin should satisfy the core PartitionSupport protocol."""
        missing: Set[str] = set()
        for name in dir(PartitionSupport):
            if name.startswith("supports_") or name == "format_partition_clause":
                if not hasattr(SnowflakePartitionMixin, name):
                    missing.add(name)
        assert not missing, f"SnowflakePartitionMixin missing methods: {missing}"

    def test_snowflake_partition_protocol_methods_are_implemented(self, dialect):
        """Dialect should satisfy isinstance checks for partition protocols."""
        assert isinstance(dialect, PartitionSupport)
        assert isinstance(dialect, SnowflakePartitionSupport)


class TestSnowflakePartitionCapabilities:
    """Automatic engine partitioning, but no addressable partition DDL."""

    def test_capability_is_automatic(self, dialect):
        """Micro-partitioning happens without user DDL, so this is not UNSUPPORTED.

        Source: https://docs.snowflake.com/en/user-guide/tables-clustering-micropartitions
        ("Micro-partitioning is automatically performed on all Snowflake
        tables.")
        """
        assert dialect.partition_capability() is PartitionCapability.AUTOMATIC
        assert str(dialect.partition_capability()) == "automatic"

    def test_the_answer_is_declared_here(self, dialect):
        """The backend owns the third case; core's derivation cannot produce it."""
        declaring = next(
            cls
            for cls in type(dialect).__mro__
            if "partition_capability" in cls.__dict__
        )
        assert declaring is SnowflakePartitionMixin
        assert dialect.partition_capability() is PartitionCapability.AUTOMATIC

    def test_no_declarative_table_partitioning(self, dialect):
        """The boolean answers whether addressable partition DDL exists."""
        assert dialect.supports_table_partitioning() is False
        assert dialect.supports_partitioned_table_creation() is False
        assert dialect.supports_range_table_partitioning() is False
        assert dialect.supports_list_table_partitioning() is False
        assert dialect.supports_hash_table_partitioning() is False

    def test_subpartitioning_not_supported(self, dialect):
        assert dialect.supports_subpartitioning() is False

    def test_maintenance_operations_not_supported(self, dialect):
        assert dialect.supports_add_partition() is False
        assert dialect.supports_drop_partition() is False
        assert dialect.supports_truncate_partition() is False
        assert dialect.supports_reorganize_partition() is False
        assert dialect.supports_attach_partition() is False
        assert dialect.supports_detach_partition() is False

    def test_external_table_partitioning_supported(self, dialect):
        assert dialect.supports_external_table_partitioning() is True


class TestSnowflakeGenericPartitionClauseRejected:
    """The generic RANGE/LIST/HASH PartitionClause is not valid Snowflake SQL."""

    def test_generic_partition_clause_rejected(self, dialect):
        clause = PartitionByRangeClause(dialect, [MockKey(dialect, "id")])
        with pytest.raises(UnsupportedFeatureError):
            clause.to_sql()


class TestSnowflakeClusterByClause:
    """CLUSTER BY is the standard-table data-layout mechanism."""

    def test_cluster_by_single_key(self, dialect):
        clause = SnowflakeClusterByClause(dialect, [MockKey(dialect, "ts")])
        sql, params = clause.to_sql()
        assert sql == ' CLUSTER BY ("ts")'
        assert params == ()

    def test_cluster_by_multiple_keys(self, dialect):
        clause = SnowflakeClusterByClause(
            dialect, [MockKey(dialect, "date"), MockKey(dialect, "id")]
        )
        sql, _ = clause.to_sql()
        assert sql == ' CLUSTER BY ("date", "id")'

    def test_cluster_by_requires_keys(self, dialect):
        # The node collects parameters only; the formatter refuses an empty list.
        clause = SnowflakeClusterByClause(dialect, [])
        with pytest.raises(ValueError, match="at least one clustering key"):
            clause.to_sql()


class TestSnowflakeExternalPartitionClause:
    """External tables use PARTITION BY (cols) — no method, no VALUES."""

    def test_external_partition_single_column(self, dialect):
        clause = SnowflakeExternalPartitionClause(dialect, [MockKey(dialect, "date_part")])
        sql, params = clause.to_sql()
        assert sql == ' PARTITION BY ("date_part")'
        assert params == ()

    def test_external_partition_multiple_columns(self, dialect):
        clause = SnowflakeExternalPartitionClause(
            dialect, [MockKey(dialect, "col1"), MockKey(dialect, "col2")]
        )
        sql, _ = clause.to_sql()
        assert sql == ' PARTITION BY ("col1", "col2")'

    def test_external_partition_requires_columns(self, dialect):
        clause = SnowflakeExternalPartitionClause(dialect, [])
        with pytest.raises(ValueError, match="at least one partition column"):
            clause.to_sql()


class TestSnowflakeAlterTableClustering:
    """ALTER TABLE ... CLUSTER BY (...) / DROP CLUSTERING KEY on an existing table."""

    def _table(self, dialect):
        from rhosocial.activerecord.backend.expression.objects import Table

        return Table(dialect, "events")

    def test_set_cluster_by(self, dialect):
        clause = SnowflakeClusterByClause(dialect, [MockKey(dialect, "id")])
        stmt = SnowflakeAlterTableClusteringStatement(
            dialect, self._table(dialect), cluster_by=clause
        )
        sql, params = stmt.to_sql()
        assert sql == 'ALTER TABLE "events" CLUSTER BY ("id")'
        assert params == ()

    def test_multiple_cluster_keys(self, dialect):
        clause = SnowflakeClusterByClause(
            dialect, [MockKey(dialect, "date"), MockKey(dialect, "id")]
        )
        stmt = SnowflakeAlterTableClusteringStatement(
            dialect, self._table(dialect), cluster_by=clause
        )
        assert stmt.to_sql()[0] == 'ALTER TABLE "events" CLUSTER BY ("date", "id")'

    def test_drop_clustering_key(self, dialect):
        stmt = SnowflakeAlterTableClusteringStatement(dialect, self._table(dialect))
        sql, params = stmt.to_sql()
        assert sql == 'ALTER TABLE "events" DROP CLUSTERING KEY'
        assert params == ()

    def test_empty_cluster_keys_are_refused_at_render(self, dialect):
        stmt = SnowflakeAlterTableClusteringStatement(
            dialect,
            self._table(dialect),
            cluster_by=SnowflakeClusterByClause(dialect, []),
        )
        with pytest.raises(ValueError, match="at least one clustering key"):
            stmt.to_sql()
