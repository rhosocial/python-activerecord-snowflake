# src/rhosocial/activerecord/backend/impl/snowflake/mixins/types.py
"""Snowflake DataType formatting and parsing mixin.

Uses DDLTypeMixin registry-based dispatch for Snowflake-specific type SQL.
"""

from __future__ import annotations

import re
from typing import Tuple

from rhosocial.activerecord.backend.dialect.mixins import DDLTypeMixin
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


class SnowflakeTypeSupportMixin(DDLTypeMixin, DDLTypeSupport):

    @DDLTypeMixin.handles(IntegerType)
    def format_data_type_integer(self, data_type: IntegerType) -> Tuple[str, tuple]:
        return "INTEGER", ()

    @DDLTypeMixin.handles(BigIntType)
    def format_data_type_bigint(self, data_type: BigIntType) -> Tuple[str, tuple]:
        return "BIGINT", ()

    @DDLTypeMixin.handles(SmallIntType)
    def format_data_type_smallint(self, data_type: SmallIntType) -> Tuple[str, tuple]:
        return "SMALLINT", ()

    @DDLTypeMixin.handles(FloatType)
    def format_data_type_float(self, data_type: FloatType) -> Tuple[str, tuple]:
        return "FLOAT", ()

    @DDLTypeMixin.handles(DoubleType)
    def format_data_type_double(self, data_type: DoubleType) -> Tuple[str, tuple]:
        return "DOUBLE", ()

    @DDLTypeMixin.handles(DecimalType)
    def format_data_type_decimal(self, data_type: DecimalType) -> Tuple[str, tuple]:
        if data_type.precision is not None and data_type.scale is not None:
            return f"NUMBER({data_type.precision}, {data_type.scale})", ()
        if data_type.precision is not None:
            return f"NUMBER({data_type.precision})", ()
        return "NUMBER", ()

    @DDLTypeMixin.handles(BooleanType)
    def format_data_type_boolean(self, data_type: BooleanType) -> Tuple[str, tuple]:
        return "BOOLEAN", ()

    @DDLTypeMixin.handles(VarCharType)
    def format_data_type_varchar(self, data_type: VarCharType) -> Tuple[str, tuple]:
        if data_type.length is not None:
            return f"VARCHAR({data_type.length})", ()
        return "VARCHAR", ()

    @DDLTypeMixin.handles(CharType)
    def format_data_type_char(self, data_type: CharType) -> Tuple[str, tuple]:
        return (f"CHAR({data_type.length})" if data_type.length is not None else "CHAR(1)"), ()

    @DDLTypeMixin.handles(TextType)
    def format_data_type_text(self, data_type: TextType) -> Tuple[str, tuple]:
        return "VARCHAR(16777216)", ()

    @DDLTypeMixin.handles(BlobType)
    def format_data_type_blob(self, data_type: BlobType) -> Tuple[str, tuple]:
        return "BINARY", ()

    @DDLTypeMixin.handles(DateTimeType)
    def format_data_type_datetime(self, data_type: DateTimeType) -> Tuple[str, tuple]:
        return "TIMESTAMP_NTZ", ()

    @DDLTypeMixin.handles(DateType)
    def format_data_type_date(self, data_type: DateType) -> Tuple[str, tuple]:
        return "DATE", ()

    @DDLTypeMixin.handles(TimeType)
    def format_data_type_time(self, data_type: TimeType) -> Tuple[str, tuple]:
        return "TIME", ()

    @DDLTypeMixin.handles(TimestampType)
    def format_data_type_timestamp(self, data_type: TimestampType) -> Tuple[str, tuple]:
        return "TIMESTAMP_NTZ", ()

    @DDLTypeMixin.handles(JsonType)
    def format_data_type_json(self, data_type: JsonType) -> Tuple[str, tuple]:
        return "VARIANT", ()

    # --- Parsing ---

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
                return BigIntType()
            if upper.startswith("SMALLINT"):
                return SmallIntType()
            return IntegerType()

        if self._SNOW_FLOAT_TYPES.match(upper):
            if "DOUBLE" in upper or "REAL" in upper:
                return DoubleType()
            return FloatType()

        if self._SNOW_DECIMAL_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            if len(nums) >= 2:
                return DecimalType(int(nums[0]), int(nums[1]))
            if len(nums) == 1:
                return DecimalType(int(nums[0]))
            return DecimalType()

        if self._SNOW_STRING_TYPES.match(upper):
            if "TEXT" in upper or "STRING" in upper:
                return TextType()
            length_match = re.search(r"\((\d+)", stripped)
            length = int(length_match.group(1)) if length_match else None
            if "VARCHAR" in upper:
                return VarCharType(length or 255)
            return CharType(length or 1)

        if self._SNOW_BINARY_TYPES.match(upper):
            return BlobType()

        if self._SNOW_DATE_TYPES.match(upper):
            if "TIMESTAMP" in upper:
                return DateTimeType()
            if upper.startswith("TIME"):
                return TimeType()
            if upper.startswith("DATE"):
                if upper.strip() == "DATE":
                    return DateType()
                return DateTimeType()
            return DateTimeType()

        if self._SNOW_BOOLEAN_TYPES.match(upper):
            return BooleanType()

        if self._SNOW_VARIANT_TYPES.match(upper):
            return JsonType()

        return CustomType(stripped)