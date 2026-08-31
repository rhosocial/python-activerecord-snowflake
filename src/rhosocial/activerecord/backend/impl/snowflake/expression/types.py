# src/rhosocial/activerecord/backend/impl/snowflake/expression/types.py
"""Snowflake-specific DataType subclass definitions.

Snowflake data types per official documentation:
https://docs.snowflake.com/en/sql-reference/data-types

Key Snowflake types:
- VARCHAR / STRING / TEXT
- NUMBER / DECIMAL / NUMERIC / INT / INTEGER / BIGINT / SMALLINT / TINYINT / BYTEINT
- FLOAT / FLOAT4 / FLOAT8 / DOUBLE / DOUBLE PRECISION / REAL
- BOOLEAN
- DATE
- TIME
- TIMESTAMP / TIMESTAMP_LTZ / TIMESTAMP_NTZ / TIMESTAMP_TZ
- BINARY / VARBINARY
- VARIANT
- OBJECT
- ARRAY
- GEOGRAPHY
- GEOMETRY
"""
from typing import Any, Optional

from rhosocial.activerecord.backend.expression.types._base import DataType
from rhosocial.activerecord.backend.expression.types.integer import IntegerType
from rhosocial.activerecord.backend.expression.types.string import VarCharType
from rhosocial.activerecord.backend.expression.types.numeric import DecimalType
from rhosocial.activerecord.backend.expression.types.boolean import BooleanType
from rhosocial.activerecord.backend.expression.types.binary import BlobType
from rhosocial.activerecord.backend.expression.types.datetime_ import DateType, TimeType, TimestampType
from rhosocial.activerecord.backend.expression.types.json_ import JsonType
from rhosocial.activerecord.backend.expression.types.array import ArrayType


class SnowflakeDataTypeMixin:
    """Mixin that provides Snowflake-specific DDL type formatting.

    Concrete DataType subclasses should implement :meth:`format_type`
    to return the SQL type string representation, including any
    length/precision/scale parameters.
    """

    def format_type(self, dialect=None) -> str:
        raise NotImplementedError

    def ddl(self, dialect=None) -> str:
        return self.format_type(dialect)


# ========== String Types ==========

class SnowflakeVarcharType(SnowflakeDataTypeMixin, VarCharType):
    """Snowflake VARCHAR type.

    Snowflake VARCHAR supports up to 16,777,216 bytes.
    """

    def __init__(self, dialect=None, *, length: Optional[int] = None):
        super().__init__(length=length, dialect=dialect)

    def format_type(self, dialect=None) -> str:
        if self.length is not None:
            return f"VARCHAR({self.length})"
        return "VARCHAR"

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return self.length == other.length

    def __hash__(self) -> int:
        return hash((type(self), self.length))


# ========== Numeric Types ==========

class SnowflakeNumberType(SnowflakeDataTypeMixin, DecimalType):
    """Snowflake NUMBER type (fixed-point).

    NUMBER(precision, scale) with precision up to 38, scale -84..127.
    """

    def __init__(self, dialect=None, *, precision: Optional[int] = None, scale: Optional[int] = None):
        super().__init__(precision=precision, scale=scale, dialect=dialect)

    def format_type(self, dialect=None) -> str:
        if self.precision is not None:
            if self.scale is not None:
                return f"NUMBER({self.precision}, {self.scale})"
            return f"NUMBER({self.precision})"
        return "NUMBER"

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return self.precision == other.precision and self.scale == other.scale

    def __hash__(self) -> int:
        return hash((type(self), self.precision, self.scale))


# ========== Boolean Type ==========

class SnowflakeBooleanType(SnowflakeDataTypeMixin, BooleanType):
    """Snowflake BOOLEAN type."""

    def format_type(self, dialect=None) -> str:
        return "BOOLEAN"


# ========== Timestamp Variants ==========

class SnowflakeTimestampLtzType(SnowflakeDataTypeMixin, TimestampType):
    """Snowflake TIMESTAMP_LTZ type (local timezone).

    Stored in UTC, displayed in session timezone.
    """

    def __init__(self, dialect=None, *, precision: Optional[int] = None):
        super().__init__(precision=precision, dialect=dialect)

    def format_type(self, dialect=None) -> str:
        if self.precision is not None:
            return f"TIMESTAMP_LTZ({self.precision})"
        return "TIMESTAMP_LTZ"

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return self.precision == other.precision

    def __hash__(self) -> int:
        return hash((type(self), self.precision))


class SnowflakeTimestampNtzType(SnowflakeDataTypeMixin, TimestampType):
    """Snowflake TIMESTAMP_NTZ type (no timezone).

    Stored and displayed as-is, without timezone conversion.
    """

    def __init__(self, dialect=None, *, precision: Optional[int] = None):
        super().__init__(precision=precision, dialect=dialect)

    def format_type(self, dialect=None) -> str:
        if self.precision is not None:
            return f"TIMESTAMP_NTZ({self.precision})"
        return "TIMESTAMP_NTZ"

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return self.precision == other.precision

    def __hash__(self) -> int:
        return hash((type(self), self.precision))


class SnowflakeTimestampTzType(SnowflakeDataTypeMixin, TimestampType):
    """Snowflake TIMESTAMP_TZ type (with timezone).

    Stores the timezone offset alongside the timestamp.
    """

    def __init__(self, dialect=None, *, precision: Optional[int] = None):
        super().__init__(precision=precision, dialect=dialect)

    def format_type(self, dialect=None) -> str:
        if self.precision is not None:
            return f"TIMESTAMP_TZ({self.precision})"
        return "TIMESTAMP_TZ"

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return self.precision == other.precision

    def __hash__(self) -> int:
        return hash((type(self), self.precision))


# ========== Date & Time ==========

class SnowflakeDateType(SnowflakeDataTypeMixin, DateType):
    """Snowflake DATE type."""

    def format_type(self, dialect=None) -> str:
        return "DATE"


class SnowflakeTimeType(SnowflakeDataTypeMixin, TimeType):
    """Snowflake TIME type."""

    def __init__(self, dialect=None, *, precision: Optional[int] = None):
        super().__init__(precision=precision, dialect=dialect)

    def format_type(self, dialect=None) -> str:
        if self.precision is not None:
            return f"TIME({self.precision})"
        return "TIME"

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return self.precision == other.precision

    def __hash__(self) -> int:
        return hash((type(self), self.precision))


# ========== Binary ==========

class SnowflakeBinaryType(SnowflakeDataTypeMixin, BlobType):
    """Snowflake BINARY type (VARBINARY).

    Maximum size: 8,388,608 bytes.
    """

    def __init__(self, dialect=None, *, length: Optional[int] = None):
        super().__init__(dialect=dialect)
        self._length = length

    def format_type(self, dialect=None) -> str:
        if self._length is not None:
            return f"BINARY({self._length})"
        return "BINARY"

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return self._length == other._length

    def __hash__(self) -> int:
        return hash((type(self), self._length))


# ========== Semi-Structured Types ==========

class SnowflakeVariantType(SnowflakeDataTypeMixin, JsonType):
    """Snowflake VARIANT type for semi-structured data.

    Stores JSON, Avro, ORC, Parquet, or any semi-structured data.
    """

    def format_type(self, dialect=None) -> str:
        return "VARIANT"


class SnowflakeObjectType(SnowflakeDataTypeMixin, JsonType):
    """Snowflake OBJECT type for key-value structured data."""

    def format_type(self, dialect=None) -> str:
        return "OBJECT"


class SnowflakeArrayType(SnowflakeDataTypeMixin, ArrayType):
    """Snowflake ARRAY type for ordered sequences."""

    def __init__(self, dialect=None, *, element_type: Optional[DataType] = None):
        super().__init__(element_type=element_type or IntegerType(), dialect=dialect)

    def format_type(self, dialect=None) -> str:
        if self.element_type is not None and not isinstance(self.element_type, IntegerType):
            return "ARRAY"
        return "ARRAY"

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return self.is_element_type_equivalent(other)

    def __hash__(self) -> int:
        return hash((type(self), type(self.element_type)))


# ========== Geospatial Types ==========

class SnowflakeGeographyType(SnowflakeDataTypeMixin, DataType):
    """Snowflake GEOGRAPHY type for geospatial data.

    Earth-surface coordinates (WGS 84, latitude/longitude).
    """

    def format_type(self, dialect=None) -> str:
        return "GEOGRAPHY"


class SnowflakeGeometryType(SnowflakeDataTypeMixin, DataType):
    """Snowflake GEOMETRY type for planar geospatial data.

    Cartesian (flat-plane) coordinates.
    """

    def format_type(self, dialect=None) -> str:
        return "GEOMETRY"