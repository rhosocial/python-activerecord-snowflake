# tests/rhosocial/activerecord_snowflake_test/feature/backend/snowflake/test_partition.py
"""Tests for Snowflake partition/clustering DDL support.

Snowflake has no declarative (RANGE/LIST/HASH) partitioning: standard tables
are micro-partitioned automatically with optional CLUSTER BY, and external
tables use PARTITION BY (cols). These tests assert the honest capability bits
and the two valid clause forms.
"""

from typing import Set

import pytest

from rhosocial.activerecord.backend.dialect import PartitionSupport
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.statements import (
    PartitionClause,
    PartitionStrategy,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import SnowflakePartitionMixin
from rhosocial.activerecord.backend.impl.snowflake.protocols import SnowflakePartitionSupport
from rhosocial.activerecord.backend.impl.snowflake.expression import (
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
    """Snowflake has no declarative table partitioning; capabilities are False."""

    def test_no_declarative_table_partitioning(self, dialect):
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
        clause = PartitionClause(dialect, PartitionStrategy.RANGE, [MockKey(dialect, "id")])
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
        with pytest.raises(ValueError, match="at least one clustering key"):
            SnowflakeClusterByClause(dialect, [])


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
        with pytest.raises(ValueError, match="at least one partition column"):
            SnowflakeExternalPartitionClause(dialect, [])
