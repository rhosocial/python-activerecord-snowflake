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
- Snowflake DDL DataType subclasses
- Snowflake-specific SQL function factories

Architecture:
- SnowflakeBackend: Synchronous implementation using snowflake-connector-python
- AsyncSnowflakeBackend: Asynchronous implementation using thread pool wrapper
- Independent from ORM frameworks - uses only native drivers
"""

from .backend import SnowflakeBackend
from .async_backend import AsyncSnowflakeBackend
from .config import SnowflakeConnectionConfig
from .collation import SnowflakeCollation
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
    SnowflakeWarehouseSupport,
)
from .mixins import (
    SnowflakeTimeTravelMixin,
    SnowflakeVariantMixin,
    SnowflakeArrayMixin,
    SnowflakeCloneMixin,
    SnowflakeStageMixin,
    SnowflakeConcurrencyMixin,
    AsyncSnowflakeConcurrencyMixin,
    SnowflakeTypeSupportMixin,
    SnowflakeWarehouseMixin,
)
from .field import SnowflakePKMixin
from .introspection import (
    SnowflakeIntrospectorMixin,
    SyncSnowflakeIntrospector,
    AsyncSnowflakeIntrospector,
)
from .expression.types import (
    SnowflakeArrayType,
    SnowflakeBinaryType,
    SnowflakeBooleanType,
    SnowflakeDateType,
    SnowflakeGeographyType,
    SnowflakeGeometryType,
    SnowflakeNumberType,
    SnowflakeObjectType,
    SnowflakeTimeType,
    SnowflakeTimestampLtzType,
    SnowflakeTimestampNtzType,
    SnowflakeTimestampTzType,
    SnowflakeVarcharType,
    SnowflakeVariantType,
)
from .functions import (
    array_append,
    array_agg,
    array_construct,
    array_contains,
    array_insert,
    array_remove,
    array_size,
    flatten,
    get_path,
    object_construct,
    object_delete,
    object_keys,
    parse_json,
    st_as_geojson,
    st_as_text,
    st_contains,
    st_distance,
    st_intersects,
    st_make_point,
    st_within,
    to_array,
    to_object,
    to_variant,
    try_parse_json,
)

from .explain import SnowflakeExplainRow, SnowflakeExplainResult
from .schema import SnowflakeSchemaDiffer

__all__ = [
    # Backend classes
    "SnowflakeBackend",
    "AsyncSnowflakeBackend",
    # Configuration
    "SnowflakeConnectionConfig",
    # Dialect
    "SnowflakeDialect",
    "SnowflakeCollation",
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
    "SnowflakeWarehouseSupport",
    # Mixins
    "SnowflakeTimeTravelMixin",
    "SnowflakeVariantMixin",
    "SnowflakeArrayMixin",
    "SnowflakeCloneMixin",
    "SnowflakeStageMixin",
    "SnowflakeConcurrencyMixin",
    "AsyncSnowflakeConcurrencyMixin",
    "SnowflakeTypeSupportMixin",
    "SnowflakeWarehouseMixin",
    # Field Mixins
    "SnowflakePKMixin",
    # Introspection
    "SnowflakeIntrospectorMixin",
    "SyncSnowflakeIntrospector",
    "AsyncSnowflakeIntrospector",
    # DDL DataType subclasses
    "SnowflakeVarcharType",
    "SnowflakeNumberType",
    "SnowflakeBooleanType",
    "SnowflakeTimestampLtzType",
    "SnowflakeTimestampNtzType",
    "SnowflakeTimestampTzType",
    "SnowflakeDateType",
    "SnowflakeTimeType",
    "SnowflakeBinaryType",
    "SnowflakeVariantType",
    "SnowflakeArrayType",
    "SnowflakeObjectType",
    "SnowflakeGeographyType",
    "SnowflakeGeometryType",
    # ARRAY functions
    "array_construct",
    "array_append",
    "array_insert",
    "array_remove",
    "array_size",
    "array_contains",
    "array_agg",
    # Semi-structured functions
    "flatten",
    "get_path",
    "object_construct",
    "object_keys",
    "object_delete",
    "parse_json",
    "to_array",
    "to_object",
    "to_variant",
    "try_parse_json",
    # Geospatial functions
    "st_make_point",
    "st_distance",
    "st_within",
    "st_contains",
    "st_intersects",
    "st_as_text",
    "st_as_geojson",
    # EXPLAIN
    "SnowflakeExplainRow",
    "SnowflakeExplainResult",
    # Schema differ
    "SnowflakeSchemaDiffer",
]