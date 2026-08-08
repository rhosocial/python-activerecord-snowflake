# src/rhosocial/activerecord/backend/impl/snowflake/mixins/__init__.py
"""Snowflake dialect-specific Mixin implementations.

This package provides shared non-I/O mixin classes for the Snowflake backend,
including backend mixin, transaction mixin, concurrency mixins, and
Snowflake-specific feature mixins for time travel, VARIANT, ARRAY,
CLONE, stage, warehouse, stream, task, pipe, file format, routine,
undrop, materialized view, table modifiers and dynamic identifier support.
"""

from .array import SnowflakeArrayMixin
from .backend import SnowflakeBackendMixin
from .clone import SnowflakeCloneMixin
from .dynamic_identifier import SnowflakeDynamicIdentifierMixin
from .file_format import SnowflakeFileFormatMixin
from .introspection import SnowflakeIntrospectionMixin
from .materialized_view import SnowflakeMaterializedViewMixin
from .partition import SnowflakePartitionMixin
from .pipe import SnowflakePipeMixin
from .routine import SnowflakeRoutineMixin
from .stage import SnowflakeStageMixin
from .stream import SnowflakeStreamMixin
from .table_modifier import SnowflakeTableModifierMixin
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
from .ddl.alter_table_modifier import SnowflakeAlterColumnModifierMixin

__all__ = [
    "SnowflakeArrayMixin",
    "SnowflakeBackendMixin",
    "SnowflakeCloneMixin",
    "SnowflakeDynamicIdentifierMixin",
    "SnowflakeFileFormatMixin",
    "SnowflakeIntrospectionMixin",
    "SnowflakeMaterializedViewMixin",
    "SnowflakePartitionMixin",
    "SnowflakePipeMixin",
    "SnowflakeRoutineMixin",
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
]
