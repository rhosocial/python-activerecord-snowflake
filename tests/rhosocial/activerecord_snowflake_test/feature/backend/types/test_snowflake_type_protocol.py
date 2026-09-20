# tests/rhosocial/activerecord_snowflake_test/feature/backend/types/test_snowflake_type_protocol.py
"""Tests for Snowflake type protocol conformance."""
import re

import pytest

from rhosocial.activerecord.backend.impl.snowflake.expression.types import (
    SnowflakeArrayType,
    SnowflakeBinaryType,
    SnowflakeBooleanType,
    SnowflakeDateType,
    SnowflakeFloatType,
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
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect

SNOWFLAKE_TYPES = [
    SnowflakeVarcharType, SnowflakeNumberType, SnowflakeFloatType,
    SnowflakeBooleanType,
    SnowflakeTimestampLtzType, SnowflakeTimestampNtzType,
    SnowflakeTimestampTzType,
    SnowflakeDateType, SnowflakeTimeType, SnowflakeBinaryType,
    SnowflakeVariantType, SnowflakeObjectType, SnowflakeArrayType,
    SnowflakeGeographyType, SnowflakeGeometryType,
]

TYPES_WITHOUT_CUSTOM_EQ = [
    SnowflakeVarcharType, SnowflakeNumberType, SnowflakeFloatType,
    SnowflakeBooleanType,
    SnowflakeTimestampLtzType, SnowflakeTimestampNtzType,
    SnowflakeTimestampTzType,
    SnowflakeDateType, SnowflakeTimeType, SnowflakeBinaryType,
    SnowflakeVariantType, SnowflakeObjectType,
    SnowflakeGeographyType, SnowflakeGeometryType,
]


class TestNamespacePrefix:
    def test_all_types_have_snowflake_prefix(self):
        for cls in SNOWFLAKE_TYPES:
            assert cls.name.startswith("snowflake_"), (
                f"{cls.__name__}.name = {cls.name!r} must start with 'snowflake_'"
            )

    def test_all_names_match_regex(self):
        pattern = re.compile(r"^[a-z][a-z0-9_]*$")
        for cls in SNOWFLAKE_TYPES:
            assert pattern.match(cls.name), (
                f"{cls.__name__}.name = {cls.name!r} invalid format"
            )


class TestDialectOptionsRemoved:
    def test_constructor_rejects_dialect_options(self):
        with pytest.raises(TypeError):
            SnowflakeVarcharType(length=100, dialect_options={"x": 1})









class TestTypeParams:
    def test_varchar_equality(self):
        a = SnowflakeVarcharType(length=100)
        b = SnowflakeVarcharType(length=100)
        assert a == b
        assert hash(a) == hash(b)

    def test_varchar_inequality(self):
        a = SnowflakeVarcharType(length=100)
        b = SnowflakeVarcharType(length=200)
        assert a != b

    def test_number_equality(self):
        a = SnowflakeNumberType(precision=10, scale=2)
        b = SnowflakeNumberType(precision=10, scale=2)
        assert a == b
        assert hash(a) == hash(b)

    def test_number_inequality(self):
        a = SnowflakeNumberType(precision=10, scale=2)
        b = SnowflakeNumberType(precision=10, scale=3)
        assert a != b

    def test_float_equality(self):
        a = SnowflakeFloatType(precision=53)
        b = SnowflakeFloatType(precision=53)
        assert a == b
        assert hash(a) == hash(b)

    def test_timestamp_ltz_equality(self):
        a = SnowflakeTimestampLtzType(precision=3)
        b = SnowflakeTimestampLtzType(precision=3)
        assert a == b
        assert hash(a) == hash(b)

    def test_timestamp_ntz_equality(self):
        a = SnowflakeTimestampNtzType(precision=6)
        b = SnowflakeTimestampNtzType(precision=6)
        assert a == b

    def test_timestamp_tz_equality(self):
        a = SnowflakeTimestampTzType(precision=9)
        b = SnowflakeTimestampTzType(precision=9)
        assert a == b

    def test_time_equality(self):
        a = SnowflakeTimeType(precision=3)
        b = SnowflakeTimeType(precision=3)
        assert a == b

    def test_binary_equality(self):
        a = SnowflakeBinaryType(length=512)
        b = SnowflakeBinaryType(length=512)
        assert a == b
        assert hash(a) == hash(b)

    def test_type_mismatch_not_equal(self):
        a = SnowflakeVarcharType(length=100)
        b = SnowflakeNumberType(precision=100)
        assert a != b




class TestNoHandWrittenEqHash:
    def test_no_custom_eq(self):
        for cls in TYPES_WITHOUT_CUSTOM_EQ:
            assert "__eq__" not in cls.__dict__, (
                f"{cls.__name__} should not define __eq__"
            )

    def test_no_custom_hash(self):
        for cls in TYPES_WITHOUT_CUSTOM_EQ:
            assert "__hash__" not in cls.__dict__, (
                f"{cls.__name__} should not define __hash__"
            )


class TestSupportsDataTypes:
    def test_returns_dict(self):
        dialect = SnowflakeDialect()
        result = dialect.supports_data_types()
        assert isinstance(result, dict)

    def test_dict_values_are_types(self):
        dialect = SnowflakeDialect()
        result = dialect.supports_data_types()
        for name, cls in result.items():
            assert isinstance(name, str)
            assert isinstance(cls, type)

    def test_contains_core_types(self):
        dialect = SnowflakeDialect()
        result = dialect.supports_data_types()
        for name in ["integer", "bigint", "smallint", "float", "double",
                      "decimal", "boolean", "varchar", "char", "text",
                      "blob", "datetime", "date", "time", "timestamp", "json"]:
            assert name in result, f"Missing core type: {name}"

    def test_contains_snowflake_types(self):
        dialect = SnowflakeDialect()
        result = dialect.supports_data_types()
        for name in ["snowflake_varchar", "snowflake_number", "snowflake_float",
                      "snowflake_boolean", "snowflake_timestamp_ltz",
                      "snowflake_timestamp_ntz", "snowflake_timestamp_tz",
                      "snowflake_date", "snowflake_time", "snowflake_binary",
                      "snowflake_variant", "snowflake_object", "snowflake_array",
                      "snowflake_geography", "snowflake_geometry"]:
            assert name in result, f"Missing Snowflake type: {name}"


class TestSupportsFormat1To1:
    def test_1_to_1_correspondence(self):
        dialect = SnowflakeDialect()
        format_methods = set()
        supports_methods = set()
        for attr in dir(type(dialect)):
            m = re.match(r"^format_data_type_([a-z][a-z0-9_]*)$", attr)
            if m:
                format_methods.add(m.group(1))
            m = re.match(r"^supports_data_type_([a-z][a-z0-9_]*)$", attr)
            if m:
                supports_methods.add(m.group(1))
        missing_supports = format_methods - supports_methods
        missing_format = supports_methods - format_methods
        assert not missing_supports, f"Missing supports: {missing_supports}"
        assert not missing_format, f"Missing format: {missing_format}"


class TestSuggestedDataTypes:
    def test_returns_empty_dict(self):
        dialect = SnowflakeDialect()
        result = dialect.suggested_data_types()
        assert isinstance(result, dict)
        assert result == {}


class TestPrecisionValidation:
    def test_number_precision_valid(self):
        dialect = SnowflakeDialect()
        sql, _ = SnowflakeNumberType(
            dialect, precision=38, scale=0
        ).to_sql()
        assert sql == "NUMBER(38, 0)"

    def test_number_precision_too_high(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision must be"):
            SnowflakeNumberType(dialect, precision=39).to_sql()

    def test_number_precision_zero(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision must be"):
            SnowflakeNumberType(dialect, precision=0).to_sql()

    def test_number_scale_too_high(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="scale must be"):
            SnowflakeNumberType(dialect, precision=10, scale=39).to_sql()

    def test_float_precision_valid(self):
        dialect = SnowflakeDialect()
        sql, _ = SnowflakeFloatType(dialect, precision=126).to_sql()
        assert sql == "FLOAT(126)"

    def test_float_precision_too_high(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision"):
            SnowflakeFloatType(dialect, precision=127).to_sql()

    def test_float_precision_zero(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision"):
            SnowflakeFloatType(dialect, precision=0).to_sql()

    def test_timestamp_precision_valid(self):
        dialect = SnowflakeDialect()
        sql, _ = SnowflakeTimestampLtzType(dialect, precision=9).to_sql()
        assert sql == "TIMESTAMP_LTZ(9)"

    def test_timestamp_precision_too_high(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision"):
            SnowflakeTimestampNtzType(dialect, precision=10).to_sql()

    def test_timestamp_precision_zero(self):
        dialect = SnowflakeDialect()
        sql, _ = SnowflakeTimestampTzType(dialect, precision=0).to_sql()
        assert sql == "TIMESTAMP_TZ(0)"

    def test_time_precision_valid(self):
        dialect = SnowflakeDialect()
        sql, _ = SnowflakeTimeType(dialect, precision=9).to_sql()
        assert sql == "TIME(9)"

    def test_time_precision_too_high(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision"):
            SnowflakeTimeType(dialect, precision=10).to_sql()

    def test_time_precision_zero(self):
        dialect = SnowflakeDialect()
        sql, _ = SnowflakeTimeType(dialect, precision=0).to_sql()
        assert sql == "TIME(0)"


class TestFormatting:
    def setup_method(self):
        self.dialect = SnowflakeDialect()

    def test_varchar_no_length(self):
        sql, _ = SnowflakeVarcharType(self.dialect).to_sql()
        assert sql == "VARCHAR"

    def test_varchar_with_length(self):
        sql, _ = SnowflakeVarcharType(self.dialect, length=255).to_sql()
        assert sql == "VARCHAR(255)"

    def test_number_no_params(self):
        sql, _ = SnowflakeNumberType(self.dialect).to_sql()
        assert sql == "NUMBER"

    def test_number_precision_only(self):
        sql, _ = SnowflakeNumberType(self.dialect, precision=10).to_sql()
        assert sql == "NUMBER(10)"

    def test_number_precision_scale(self):
        sql, _ = SnowflakeNumberType(
            self.dialect, precision=10, scale=2
        ).to_sql()
        assert sql == "NUMBER(10, 2)"

    def test_float_no_precision(self):
        sql, _ = SnowflakeFloatType(self.dialect).to_sql()
        assert sql == "FLOAT"

    def test_float_with_precision(self):
        sql, _ = SnowflakeFloatType(self.dialect, precision=53).to_sql()
        assert sql == "FLOAT(53)"

    def test_boolean(self):
        sql, _ = SnowflakeBooleanType(self.dialect).to_sql()
        assert sql == "BOOLEAN"

    def test_timestamp_ltz(self):
        sql, _ = SnowflakeTimestampLtzType(self.dialect).to_sql()
        assert sql == "TIMESTAMP_LTZ"

    def test_timestamp_ltz_precision(self):
        sql, _ = SnowflakeTimestampLtzType(
            self.dialect, precision=3
        ).to_sql()
        assert sql == "TIMESTAMP_LTZ(3)"

    def test_timestamp_ntz(self):
        sql, _ = SnowflakeTimestampNtzType(self.dialect).to_sql()
        assert sql == "TIMESTAMP_NTZ"

    def test_timestamp_tz(self):
        sql, _ = SnowflakeTimestampTzType(self.dialect).to_sql()
        assert sql == "TIMESTAMP_TZ"

    def test_date(self):
        sql, _ = SnowflakeDateType(self.dialect).to_sql()
        assert sql == "DATE"

    def test_time(self):
        sql, _ = SnowflakeTimeType(self.dialect).to_sql()
        assert sql == "TIME"

    def test_time_precision(self):
        sql, _ = SnowflakeTimeType(self.dialect, precision=6).to_sql()
        assert sql == "TIME(6)"

    def test_binary(self):
        sql, _ = SnowflakeBinaryType(self.dialect).to_sql()
        assert sql == "BINARY"

    def test_binary_length(self):
        sql, _ = SnowflakeBinaryType(self.dialect, length=1024).to_sql()
        assert sql == "BINARY(1024)"

    def test_variant(self):
        sql, _ = SnowflakeVariantType(self.dialect).to_sql()
        assert sql == "VARIANT"

    def test_object(self):
        sql, _ = SnowflakeObjectType(self.dialect).to_sql()
        assert sql == "OBJECT"

    def test_array(self):
        sql, _ = SnowflakeArrayType(self.dialect).to_sql()
        assert sql == "ARRAY"

    def test_geography(self):
        sql, _ = SnowflakeGeographyType(self.dialect).to_sql()
        assert sql == "GEOGRAPHY"

    def test_geometry(self):
        sql, _ = SnowflakeGeometryType(self.dialect).to_sql()
        assert sql == "GEOMETRY"
