# src/rhosocial/activerecord/backend/impl/snowflake/mixins/types.py
"""Snowflake DataType formatting and parsing mixin.

Uses DDLTypeMixin naming-convention dispatch for Snowflake-specific type SQL.
"""

from __future__ import annotations

import re
from typing import Tuple

from rhosocial.activerecord.backend.dialect.mixins.ddl_type import DDLTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DDLTypeSupport
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BooleanType,
    CharType,
    CustomType,
    DataType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonType,
    SmallIntType,
    TextType,
    TimeType,
    TimestampType,
    VarCharType,
    BlobType,
)
from ..expression.types import (
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
    SnowflakeVariantType,
    SnowflakeVarcharType,
)


class SnowflakeTypeSupportMixin(DDLTypeMixin, DDLTypeSupport):
    """Snowflake DataType formatting and parsing.

    Implements ``DDLTypeSupport`` so the dialect can render ``DataType``
    expressions to SQL strings and parse raw SQL type strings back into
    ``DataType`` instances.

    Formatting dispatches by the type instance's ``name`` through the
    naming-convention ``format_data_type_<name>`` methods (see
    ``DDLTypeMixin``). Snowflake-specific types carry ``snowflake_``-prefixed
    names; core types render their real Snowflake SQL.
    """

    # ------------------------------------------------------------------
    # DDLTypeSupport — formatting (core types)
    # ------------------------------------------------------------------

    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        return "INTEGER", ()

    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        return "BIGINT", ()

    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        return "SMALLINT", ()

    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        return "FLOAT", ()

    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        return "DOUBLE", ()

    def format_data_type_decimal(self, data_type: DecimalType) -> Tuple[str, tuple]:
        if data_type.precision is not None and data_type.scale is not None:
            return f"NUMBER({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"NUMBER({data_type.precision})", ()
        return "NUMBER", ()

    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        return "BOOLEAN", ()

    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        if data_type.length is not None:
            return f"VARCHAR({data_type.length})", ()
        return "VARCHAR", ()

    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        return (f"CHAR({data_type.length})" if data_type.length is not None else "CHAR(1)"), ()

    def format_data_type_text(self, data_type: TextType) -> Tuple[str, tuple]:
        return "VARCHAR(16777216)", ()

    def format_data_type_blob(self, data_type: BlobType) -> Tuple[str, tuple]:
        return "BINARY", ()

    def format_data_type_datetime(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        return "TIMESTAMP_NTZ", ()

    def format_data_type_date(self, data_type: DateType) -> Tuple[str, tuple]:
        return "DATE", ()

    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        return "TIME", ()

    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        return "TIMESTAMP_NTZ", ()

    def format_data_type_json(self, data_type: JsonType) -> Tuple[str, tuple]:
        return "VARIANT", ()

    # --- Snowflake-specific type formatters (dispatch key = type name) ---

    def format_data_type_snowflake_varchar(self, data_type: SnowflakeVarcharType) -> Tuple[str, tuple]:
        if data_type.length is not None:
            return f"VARCHAR({data_type.length})", ()
        return "VARCHAR", ()

    def format_data_type_snowflake_number(self, data_type: SnowflakeNumberType) -> Tuple[str, tuple]:
        if data_type.precision is not None and data_type.scale is not None:
            return f"NUMBER({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"NUMBER({data_type.precision})", ()
        return "NUMBER", ()

    def format_data_type_snowflake_boolean(self, data_type: SnowflakeBooleanType) -> Tuple[str, tuple]:
        return "BOOLEAN", ()

    def format_data_type_snowflake_timestamp_ltz(self, data_type: SnowflakeTimestampLtzType) -> Tuple[str, tuple]:
        if data_type.precision is not None:
            return f"TIMESTAMP_LTZ({data_type.precision})", ()
        return "TIMESTAMP_LTZ", ()

    def format_data_type_snowflake_timestamp_ntz(self, data_type: SnowflakeTimestampNtzType) -> Tuple[str, tuple]:
        if data_type.precision is not None:
            return f"TIMESTAMP_NTZ({data_type.precision})", ()
        return "TIMESTAMP_NTZ", ()

    def format_data_type_snowflake_timestamp_tz(self, data_type: SnowflakeTimestampTzType) -> Tuple[str, tuple]:
        if data_type.precision is not None:
            return f"TIMESTAMP_TZ({data_type.precision})", ()
        return "TIMESTAMP_TZ", ()

    def format_data_type_snowflake_date(self, data_type: SnowflakeDateType) -> Tuple[str, tuple]:
        return "DATE", ()

    def format_data_type_snowflake_time(self, data_type: SnowflakeTimeType) -> Tuple[str, tuple]:
        if data_type.precision is not None:
            return f"TIME({data_type.precision})", ()
        return "TIME", ()

    def format_data_type_snowflake_binary(self, data_type: SnowflakeBinaryType) -> Tuple[str, tuple]:
        if data_type._length is not None:
            return f"BINARY({data_type._length})", ()
        return "BINARY", ()

    def format_data_type_snowflake_variant(self, data_type: SnowflakeVariantType) -> Tuple[str, tuple]:
        return "VARIANT", ()

    def format_data_type_snowflake_object(self, data_type: SnowflakeObjectType) -> Tuple[str, tuple]:
        return "OBJECT", ()

    def format_data_type_snowflake_array(self, data_type: SnowflakeArrayType) -> Tuple[str, tuple]:
        return "ARRAY", ()

    def format_data_type_snowflake_geography(self, data_type: SnowflakeGeographyType) -> Tuple[str, tuple]:
        return "GEOGRAPHY", ()

    def format_data_type_snowflake_geometry(self, data_type: SnowflakeGeometryType) -> Tuple[str, tuple]:
        return "GEOMETRY", ()

    # ------------------------------------------------------------------
    # DDLTypeSupport — parsing
    # ------------------------------------------------------------------

    _SNOW_INTEGER_TYPES = re.compile(r"^(?:INT|INTEGER|BIGINT|SMALLINT|TINYINT|BYTEINT)\b", re.IGNORECASE)
    _SNOW_FLOAT_TYPES = re.compile(r"^(?:FLOAT|FLOAT4|FLOAT8|DOUBLE|DOUBLE\s+PRECISION|REAL)\b", re.IGNORECASE)
    _SNOW_DECIMAL_TYPES = re.compile(r"^(?:NUMBER|DECIMAL|NUMERIC)\b", re.IGNORECASE)
    _SNOW_STRING_TYPES = re.compile(r"^(?:VARCHAR|CHAR|CHARACTER|STRING|TEXT)\b", re.IGNORECASE)
    _SNOW_BINARY_TYPES = re.compile(r"^(?:BINARY|VARBINARY)\b", re.IGNORECASE)
    _SNOW_DATE_TYPES = re.compile(r"^(?:DATETIME|TIMESTAMP(?:_[A-Z]+)?|DATE|TIME)\b", re.IGNORECASE)
    _SNOW_BOOLEAN_TYPES = re.compile(r"^(?:BOOLEAN)\b", re.IGNORECASE)
    _SNOW_VARIANT_TYPES = re.compile(r"^(?:VARIANT|OBJECT|ARRAY)\b", re.IGNORECASE)

    def parse_type(self, raw: str) -> DataType:
        stripped = raw.strip()
        upper = stripped.upper()

        if self._SNOW_INTEGER_TYPES.match(upper):
            if upper.startswith("BIGINT"):
                return BigIntType(dialect=self)
            if upper.startswith("SMALLINT"):
                return SmallIntType(dialect=self)
            return IntegerType(dialect=self)

        if self._SNOW_FLOAT_TYPES.match(upper):
            if "DOUBLE" in upper or "REAL" in upper:
                return DoubleType(dialect=self)
            return FloatType(dialect=self)

        if self._SNOW_DECIMAL_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            if len(nums) >= 2:
                return DecimalType(dialect=self, precision=int(nums[0]), scale=int(nums[1]))
            if len(nums) == 1:
                return DecimalType(dialect=self, precision=int(nums[0]))
            return DecimalType(dialect=self)

        if self._SNOW_STRING_TYPES.match(upper):
            if "TEXT" in upper or "STRING" in upper:
                return TextType(dialect=self)
            length_match = re.search(r"\((\d+)", stripped)
            length = int(length_match.group(1)) if length_match else None
            if "VARCHAR" in upper:
                return VarCharType(dialect=self, length=length or 255)
            return CharType(dialect=self, length=length or 1)

        if self._SNOW_BINARY_TYPES.match(upper):
            return BlobType(dialect=self)

        if self._SNOW_DATE_TYPES.match(upper):
            if "TIMESTAMP" in upper:
                return DateTimeType(dialect=self)
            if upper.startswith("TIME"):
                return TimeType(dialect=self)
            if upper.startswith("DATE"):
                if upper.strip() == "DATE":
                    return DateType(dialect=self)
                return DateTimeType(dialect=self)
            return DateTimeType(dialect=self)

        if self._SNOW_BOOLEAN_TYPES.match(upper):
            return BooleanType(dialect=self)

        if self._SNOW_VARIANT_TYPES.match(upper):
            return JsonType(dialect=self)

        return CustomType(dialect=self, raw=stripped)
