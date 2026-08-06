# src/rhosocial/activerecord/backend/impl/snowflake/mixins/__init__.py
"""Snowflake dialect-specific Mixin implementations.

This package provides shared non-I/O mixin classes for the Snowflake backend,
including backend mixin, transaction mixin, concurrency mixins, and
Snowflake-specific feature mixins for time travel, VARIANT, ARRAY,
CLONE, and stage support.
"""

from .array import SnowflakeArrayMixin
from .backend import SnowflakeBackendMixin
from .clone import SnowflakeCloneMixin
from .introspection import SnowflakeIntrospectionMixin
from .partition import SnowflakePartitionMixin
from .stage import SnowflakeStageMixin
from .time_travel import SnowflakeTimeTravelMixin
from .transaction import (
    AsyncSnowflakeConcurrencyMixin,
    SnowflakeConcurrencyMixin,
    SnowflakeTransactionMixin,
)
from .variant import SnowflakeVariantMixin
from .types import SnowflakeTypeSupportMixin
from .ddl.alter_table_modifier import SnowflakeAlterColumnModifierMixin

__all__ = [
    "SnowflakeArrayMixin",
    "SnowflakeBackendMixin",
    "SnowflakeCloneMixin",
    "SnowflakeIntrospectionMixin",
    "SnowflakePartitionMixin",
    "SnowflakeStageMixin",
    "SnowflakeTimeTravelMixin",
    "SnowflakeTransactionMixin",
    "SnowflakeConcurrencyMixin",
    "AsyncSnowflakeConcurrencyMixin",
    "SnowflakeVariantMixin",
    "SnowflakeTypeSupportMixin",
    "SnowflakeAlterColumnModifierMixin",
]