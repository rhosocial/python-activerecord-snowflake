"""Snowflake backend implementation for the Python ORM.

This module provides:
- Snowflake synchronous backend with connection management and query execution
- Snowflake asynchronous backend with async/await support (thread pool wrapper)
- Snowflake-specific connection configuration
- Type mapping and value conversion
- Transaction management (sync and async)
- Snowflake dialect and expression handling
- Snowflake-specific type helpers (VARIANT, ARRAY)
- Snowflake-specific type adapters

Architecture:
- SnowflakeBackend: Synchronous implementation using snowflake-connector-python
- AsyncSnowflakeBackend: Asynchronous implementation using thread pool wrapper
- Independent from ORM frameworks - uses only native drivers
"""

from .backend import SnowflakeBackend
from .async_backend import AsyncSnowflakeBackend
from .config import SnowflakeConnectionConfig
from .dialect import SnowflakeDialect
from .transaction import SnowflakeTransactionManager
from .async_transaction import AsyncSnowflakeTransactionManager
from .types import SnowflakeVariant, SnowflakeArray
from .adapters import (
    SnowflakeVariantAdapter,
    SnowflakeArrayAdapter,
    SnowflakeBooleanAdapter,
    SnowflakeDecimalAdapter,
    SnowflakeTimestampAdapter,
)
from .protocols import (
    SnowflakeTimeTravelSupport,
    SnowflakeVariantSupport,
    SnowflakeArraySupport,
    SnowflakeCloneSupport,
    SnowflakeStageSupport,
)
from .mixins import (
    SnowflakeTimeTravelMixin,
    SnowflakeVariantMixin,
    SnowflakeArrayMixin,
    SnowflakeCloneMixin,
    SnowflakeStageMixin,
)
from .field import SnowflakePKMixin
from .introspection import (
    SnowflakeIntrospectorMixin,
    SyncSnowflakeIntrospector,
    AsyncSnowflakeIntrospector,
)

__all__ = [
    # Backend classes
    "SnowflakeBackend",
    "AsyncSnowflakeBackend",
    # Configuration
    "SnowflakeConnectionConfig",
    # Dialect
    "SnowflakeDialect",
    # Transaction managers
    "SnowflakeTransactionManager",
    "AsyncSnowflakeTransactionManager",
    # Type helpers
    "SnowflakeVariant",
    "SnowflakeArray",
    # Type adapters
    "SnowflakeVariantAdapter",
    "SnowflakeArrayAdapter",
    "SnowflakeBooleanAdapter",
    "SnowflakeDecimalAdapter",
    "SnowflakeTimestampAdapter",
    # Protocols
    "SnowflakeTimeTravelSupport",
    "SnowflakeVariantSupport",
    "SnowflakeArraySupport",
    "SnowflakeCloneSupport",
    "SnowflakeStageSupport",
    # Mixins
    "SnowflakeTimeTravelMixin",
    "SnowflakeVariantMixin",
    "SnowflakeArrayMixin",
    "SnowflakeCloneMixin",
    "SnowflakeStageMixin",
    # Field Mixins
    "SnowflakePKMixin",
    # Introspection
    "SnowflakeIntrospectorMixin",
    "SyncSnowflakeIntrospector",
    "AsyncSnowflakeIntrospector",
]
