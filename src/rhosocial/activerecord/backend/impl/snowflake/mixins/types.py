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

    def format_data_type_integer(self, expr: IntegerType) -> Tuple[str, tuple]:
        return "INTEGER", ()

    def format_data_type_bigint(self, expr: BigIntType) -> Tuple[str, tuple]:
        return "BIGINT", ()

    def format_data_type_smallint(self, expr: SmallIntType) -> Tuple[str, tuple]:
        return "SMALLINT", ()

    def format_data_type_float(self, expr: FloatType) -> Tuple[str, tuple]:
        return "FLOAT", ()

    def format_data_type_double(self, expr: DoubleType) -> Tuple[str, tuple]:
        return "DOUBLE", ()

    def format_data_type_decimal(self, expr: DecimalType) -> Tuple[str, tuple]:
        if expr.precision is not None and expr.scale is not None:
            return f"NUMBER({expr.precision}, {expr.scale})", ()
        if expr.precision is not None:
            return f"NUMBER({expr.precision})", ()
        return "NUMBER", ()

    def format_data_type_boolean(self, expr: BooleanType) -> Tuple[str, tuple]:
        return "BOOLEAN", ()

    def format_data_type_varchar(self, expr: VarCharType) -> Tuple[str, tuple]:
        if expr.length is not None:
            return f"VARCHAR({expr.length})", ()
        return "VARCHAR", ()

    def format_data_type_char(self, expr: CharType) -> Tuple[str, tuple]:
        return (f"CHAR({expr.length})" if expr.length is not None else "CHAR(1)"), ()

    def format_data_type_text(self, expr: TextType) -> Tuple[str, tuple]:
        return "VARCHAR(16777216)", ()

    def format_data_type_blob(self, expr: BlobType) -> Tuple[str, tuple]:
        return "BINARY", ()

    def format_data_type_datetime(self, expr: DateTimeType) -> Tuple[str, tuple]:
        return "TIMESTAMP_NTZ", ()

    def format_data_type_date(self, expr: DateType) -> Tuple[str, tuple]:
        return "DATE", ()

    def format_data_type_time(self, expr: TimeType) -> Tuple[str, tuple]:
        return "TIME", ()

    def format_data_type_timestamp(self, expr: TimestampType) -> Tuple[str, tuple]:
        return "TIMESTAMP_NTZ", ()

    def format_data_type_json(self, expr: JsonType) -> Tuple[str, tuple]:
        return "VARIANT", ()

    # --- Snowflake-specific type formatters (dispatch key = type name) ---

    def format_data_type_snowflake_varchar(self, expr: SnowflakeVarcharType) -> Tuple[str, tuple]:
        if expr.length is not None:
            return f"VARCHAR({expr.length})", ()
        return "VARCHAR", ()

    def format_data_type_snowflake_number(self, expr: SnowflakeNumberType) -> Tuple[str, tuple]:
        if expr.precision is not None and expr.scale is not None:
            return f"NUMBER({expr.precision}, {expr.scale})", ()
        if expr.precision is not None:
            return f"NUMBER({expr.precision})", ()
        return "NUMBER", ()

    def format_data_type_snowflake_boolean(self, expr: SnowflakeBooleanType) -> Tuple[str, tuple]:
        return "BOOLEAN", ()

    def format_data_type_snowflake_timestamp_ltz(self, expr: SnowflakeTimestampLtzType) -> Tuple[str, tuple]:
        if expr.precision is not None:
            return f"TIMESTAMP_LTZ({expr.precision})", ()
        return "TIMESTAMP_LTZ", ()

    def format_data_type_snowflake_timestamp_ntz(self, expr: SnowflakeTimestampNtzType) -> Tuple[str, tuple]:
        if expr.precision is not None:
            return f"TIMESTAMP_NTZ({expr.precision})", ()
        return "TIMESTAMP_NTZ", ()

    def format_data_type_snowflake_timestamp_tz(self, expr: SnowflakeTimestampTzType) -> Tuple[str, tuple]:
        if expr.precision is not None:
            return f"TIMESTAMP_TZ({expr.precision})", ()
        return "TIMESTAMP_TZ", ()

    def format_data_type_snowflake_date(self, expr: SnowflakeDateType) -> Tuple[str, tuple]:
        return "DATE", ()

    def format_data_type_snowflake_time(self, expr: SnowflakeTimeType) -> Tuple[str, tuple]:
        if expr.precision is not None:
            return f"TIME({expr.precision})", ()
        return "TIME", ()

    def format_data_type_snowflake_binary(self, expr: SnowflakeBinaryType) -> Tuple[str, tuple]:
        if expr._length is not None:
            return f"BINARY({expr._length})", ()
        return "BINARY", ()

    def format_data_type_snowflake_variant(self, expr: SnowflakeVariantType) -> Tuple[str, tuple]:
        return "VARIANT", ()

    def format_data_type_snowflake_object(self, expr: SnowflakeObjectType) -> Tuple[str, tuple]:
        return "OBJECT", ()

    def format_data_type_snowflake_array(self, expr: SnowflakeArrayType) -> Tuple[str, tuple]:
        return "ARRAY", ()

    def format_data_type_snowflake_geography(self, expr: SnowflakeGeographyType) -> Tuple[str, tuple]:
        return "GEOGRAPHY", ()

    def format_data_type_snowflake_geometry(self, expr: SnowflakeGeometryType) -> Tuple[str, tuple]:
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
