"""Tests for Snowflake partition DDL support."""

from typing import Set

import pytest

from rhosocial.activerecord.backend.dialect import protocols as dialect_protocols
from rhosocial.activerecord.backend.dialect import PartitionSupport
from rhosocial.activerecord.backend.dialect.mixins import PartitionMixin
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.statements.ddl_partition import (
    PartitionClause,
    PartitionStrategy,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import SnowflakePartitionMixin
from rhosocial.activerecord.backend.impl.snowflake.protocols import SnowflakePartitionSupport
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakePartitionClause,
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


@pytest.fixture
def old_dialect():
    return SnowflakeDialect(version=(6, 0, 0))


class TestSnowflakePartitionProtocolConformance:
    """Verify SnowflakePartitionSupport protocol and mixin."""

    def test_partition_mixin_satisfies_partition_support_protocol(self):
        """SnowflakePartitionMixin should satisfy the core PartitionSupport protocol."""
        missing: Set[str] = set()
        for name in dir(PartitionSupport):
            if name.startswith("supports_") or name == "format_partition_clause":
                if not hasattr(SnowflakePartitionMixin, name):
                    missing.add(name)
        assert not missing, (
            f"SnowflakePartitionMixin missing methods: {missing}"
        )

    def test_snowflake_partition_protocol_methods_are_implemented(self, dialect):
        """Dialect should satisfy isinstance checks for partition protocols."""
        assert isinstance(dialect, PartitionSupport)
        assert isinstance(dialect, SnowflakePartitionSupport)


class TestSnowflakePartitionCapabilities:
    """Test partition capability detection."""

    def test_supports_table_partitioning(self, dialect):
        assert dialect.supports_table_partitioning() is True

    def test_supports_range_partitioning(self, dialect):
        assert dialect.supports_range_table_partitioning() is True

    def test_supports_list_partitioning(self, dialect):
        assert dialect.supports_list_table_partitioning() is True

    def test_hash_not_supported(self, dialect):
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


class TestSnowflakePartitionClauseFormatting:
    """Test PARTITION BY clause SQL generation."""

    def test_format_partition_clause_range(self, dialect):
        key = MockKey(dialect, "date_col")

        clause = SnowflakePartitionClause(
            dialect,
            PartitionStrategy.RANGE,
            [key],
            partitions=[
                {"name": "p1", "values": ["'2020-01-01'"]},
                {"name": "p2", "values": ["'2022-01-01'"]},
            ],
        )
        sql, params = clause.to_sql()
        assert "PARTITION BY RANGE" in sql
        assert '"date_col"' in sql
        assert "PARTITION p1" in sql
        assert "VALUES LESS THAN" in sql
        assert "'2020-01-01'" in sql

    def test_format_partition_clause_list(self, dialect):
        key = MockKey(dialect, "region")

        clause = SnowflakePartitionClause(
            dialect,
            PartitionStrategy.LIST,
            [key],
            partitions=[
                {"name": "p_north", "values": ["'North'"]},
            ],
        )
        sql, params = clause.to_sql()
        assert "PARTITION BY LIST" in sql
        assert "VALUES IN" in sql

    def test_format_partition_clause_without_partitions(self, dialect):
        key = MockKey(dialect, "id")

        clause = PartitionClause(
            dialect,
            PartitionStrategy.RANGE,
            [key],
        )
        sql, params = clause.to_sql()
        assert "PARTITION BY RANGE" in sql
        assert '"id"' in sql

    def test_format_partition_clause_multiple_keys(self, dialect):
        key1 = MockKey(dialect, "year")
        key2 = MockKey(dialect, "month")

        clause = PartitionClause(
            dialect,
            PartitionStrategy.RANGE,
            [key1, key2],
        )
        sql, params = clause.to_sql()
        assert "PARTITION BY RANGE" in sql
        assert '"year"' in sql
        assert '"month"' in sql

    def test_partition_not_supported_on_default_mixin(self):
        """UnsupportedFeatureError should be raised on plain PartitionMixin."""
        class TestDialect:
            name = "test"
        mixin = PartitionMixin()
        mixin.name = "test"
        with pytest.raises(UnsupportedFeatureError):
            mixin.format_partition_clause(None)
