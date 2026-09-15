# src/rhosocial/activerecord/backend/impl/snowflake/mixins/__init__.py
"""Snowflake dialect-specific Mixin implementations.

This package provides shared non-I/O mixin classes for the Snowflake backend,
including backend mixin, transaction mixin, concurrency mixins, and
Snowflake-specific feature mixins for time travel, VARIANT, ARRAY,
CLONE, stage, warehouse, stream, task, pipe, file format, routine,
undrop, materialized view, table modifiers support.
"""

from .array import SnowflakeArrayMixin
from .backend import SnowflakeBackendMixin
from .clone import SnowflakeCloneMixin
from .dml import SnowflakeDMLMixin
from .file_format import SnowflakeFileFormatMixin
from .introspection import SnowflakeIntrospectionMixin
from .materialized_view import SnowflakeMaterializedViewMixin
from .partition import SnowflakePartitionMixin
from .pipe import SnowflakePipeMixin
from .pivot import SnowflakePivotMixin
from .routine import SnowflakeRoutineMixin
from .sample import SnowflakeSampleMixin
from .show import SnowflakeShowMixin
from .stage import SnowflakeStageMixin
from .stream import SnowflakeStreamMixin
from .ddl_table_modifier import SnowflakeTableModifierMixin
from .task import SnowflakeTaskMixin
from .time_travel import SnowflakeTimeTravelMixin
from .transaction import (
    AsyncSnowflakeConcurrencyMixin,
    SnowflakeConcurrencyMixin,
    SnowflakeTransactionMixin,
)
from .undrop import SnowflakeUndropMixin
from .variant import SnowflakeVariantMixin
from .types import SnowflakeTypeSupportMixin
from .warehouse import SnowflakeWarehouseMixin
from .ddl import SnowflakeAlterColumnModifierMixin
# New mixins from dialect.py split
from .datetime import SnowflakeDateTimeMixin
from .collation import SnowflakeCollationMixin
from .set_operation import SnowflakeSetOperationMixin
from .dql import SnowflakeDQLMixin
from .capabilities import SnowflakeCapabilityMixin
from .ilike import SnowflakeILIKEMixin
from .generated_column import SnowflakeGeneratedColumnMixin
from .ordered_set_aggregation import SnowflakeOrderedSetAggregationMixin
from .truncate import SnowflakeTruncateMixin

__all__ = [
    "SnowflakeArrayMixin",
    "SnowflakeBackendMixin",
    "SnowflakeCloneMixin",
    "SnowflakeDMLMixin",
    "SnowflakeFileFormatMixin",
    "SnowflakeIntrospectionMixin",
    "SnowflakeMaterializedViewMixin",
    "SnowflakePartitionMixin",
    "SnowflakePipeMixin",
    "SnowflakePivotMixin",
    "SnowflakeRoutineMixin",
    "SnowflakeSampleMixin",
    "SnowflakeShowMixin",
    "SnowflakeStageMixin",
    "SnowflakeStreamMixin",
    "SnowflakeTableModifierMixin",
    "SnowflakeTaskMixin",
    "SnowflakeTimeTravelMixin",
    "SnowflakeTransactionMixin",
    "SnowflakeConcurrencyMixin",
    "AsyncSnowflakeConcurrencyMixin",
    "SnowflakeUndropMixin",
    "SnowflakeVariantMixin",
    "SnowflakeTypeSupportMixin",
    "SnowflakeWarehouseMixin",
    "SnowflakeAlterColumnModifierMixin",
    "SnowflakeDateTimeMixin",
    "SnowflakeCollationMixin",
    "SnowflakeSetOperationMixin",
    "SnowflakeDQLMixin",
    "SnowflakeCapabilityMixin",
    "SnowflakeILIKEMixin",
    "SnowflakeGeneratedColumnMixin",
    "SnowflakeOrderedSetAggregationMixin",
    "SnowflakeTruncateMixin",
]
