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


class TestDialectOptionsForwarding:
    def test_varchar_forwards_dialect_options(self):
        opts = {"max_length": 100}
        t = SnowflakeVarcharType(dialect_options=opts)
        assert t.dialect_options == opts

    def test_number_forwards_dialect_options(self):
        opts = {"unsigned": True}
        t = SnowflakeNumberType(precision=10, dialect_options=opts)
        assert t.dialect_options == opts

    def test_float_forwards_dialect_options(self):
        opts = {"storage": "8bytes"}
        t = SnowflakeFloatType(precision=53, dialect_options=opts)
        assert t.dialect_options == opts

    def test_timestamp_ltz_forwards_dialect_options(self):
        opts = {"tz": "PST"}
        t = SnowflakeTimestampLtzType(dialect_options=opts)
        assert t.dialect_options == opts

    def test_timestamp_ntz_default_dialect_options(self):
        t = SnowflakeTimestampNtzType()
        assert t.dialect_options == {}

    def test_time_forwards_dialect_options(self):
        t = SnowflakeTimeType(precision=3, dialect_options={"utc": True})
        assert t.dialect_options == {"utc": True}

    def test_binary_forwards_dialect_options(self):
        t = SnowflakeBinaryType(length=1024, dialect_options={"compress": True})
        assert t.dialect_options == {"compress": True}

    def test_array_forwards_dialect_options(self):
        t = SnowflakeArrayType(dialect_options={"max_items": 100})
        assert t.dialect_options == {"max_items": 100}


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

    def test_dialect_options_participate_in_eq(self):
        a = SnowflakeVarcharType(length=100, dialect_options={"x": 1})
        b = SnowflakeVarcharType(length=100, dialect_options={"x": 2})
        assert a != b

    def test_dialect_options_not_in_hash(self):
        a = SnowflakeVarcharType(length=100, dialect_options={"x": 1})
        b = SnowflakeVarcharType(length=100, dialect_options={"x": 2})
        assert hash(a) == hash(b)


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
        sql, _ = dialect.format_data_type(
            SnowflakeNumberType(precision=38, scale=0))
        assert sql == "NUMBER(38, 0)"

    def test_number_precision_too_high(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision must be"):
            dialect.format_data_type(SnowflakeNumberType(precision=39))

    def test_number_precision_zero(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision must be"):
            dialect.format_data_type(SnowflakeNumberType(precision=0))

    def test_number_scale_too_high(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="scale must be"):
            dialect.format_data_type(
                SnowflakeNumberType(precision=10, scale=39))

    def test_float_precision_valid(self):
        dialect = SnowflakeDialect()
        sql, _ = dialect.format_data_type(SnowflakeFloatType(precision=126))
        assert sql == "FLOAT(126)"

    def test_float_precision_too_high(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision"):
            dialect.format_data_type(SnowflakeFloatType(precision=127))

    def test_float_precision_zero(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision"):
            dialect.format_data_type(SnowflakeFloatType(precision=0))

    def test_timestamp_precision_valid(self):
        dialect = SnowflakeDialect()
        sql, _ = dialect.format_data_type(
            SnowflakeTimestampLtzType(precision=9))
        assert sql == "TIMESTAMP_LTZ(9)"

    def test_timestamp_precision_too_high(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision"):
            dialect.format_data_type(SnowflakeTimestampNtzType(precision=10))

    def test_timestamp_precision_zero(self):
        dialect = SnowflakeDialect()
        sql, _ = dialect.format_data_type(
            SnowflakeTimestampTzType(precision=0))
        assert sql == "TIMESTAMP_TZ(0)"

    def test_time_precision_valid(self):
        dialect = SnowflakeDialect()
        sql, _ = dialect.format_data_type(SnowflakeTimeType(precision=9))
        assert sql == "TIME(9)"

    def test_time_precision_too_high(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="precision"):
            dialect.format_data_type(SnowflakeTimeType(precision=10))

    def test_time_precision_zero(self):
        dialect = SnowflakeDialect()
        sql, _ = dialect.format_data_type(SnowflakeTimeType(precision=0))
        assert sql == "TIME(0)"


class TestFormatting:
    def setup_method(self):
        self.dialect = SnowflakeDialect()

    def test_varchar_no_length(self):
        sql, _ = self.dialect.format_data_type(SnowflakeVarcharType())
        assert sql == "VARCHAR"

    def test_varchar_with_length(self):
        sql, _ = self.dialect.format_data_type(
            SnowflakeVarcharType(length=255))
        assert sql == "VARCHAR(255)"

    def test_number_no_params(self):
        sql, _ = self.dialect.format_data_type(SnowflakeNumberType())
        assert sql == "NUMBER"

    def test_number_precision_only(self):
        sql, _ = self.dialect.format_data_type(
            SnowflakeNumberType(precision=10))
        assert sql == "NUMBER(10)"

    def test_number_precision_scale(self):
        sql, _ = self.dialect.format_data_type(
            SnowflakeNumberType(precision=10, scale=2))
        assert sql == "NUMBER(10, 2)"

    def test_float_no_precision(self):
        sql, _ = self.dialect.format_data_type(SnowflakeFloatType())
        assert sql == "FLOAT"

    def test_float_with_precision(self):
        sql, _ = self.dialect.format_data_type(
            SnowflakeFloatType(precision=53))
        assert sql == "FLOAT(53)"

    def test_boolean(self):
        sql, _ = self.dialect.format_data_type(SnowflakeBooleanType())
        assert sql == "BOOLEAN"

    def test_timestamp_ltz(self):
        sql, _ = self.dialect.format_data_type(SnowflakeTimestampLtzType())
        assert sql == "TIMESTAMP_LTZ"

    def test_timestamp_ltz_precision(self):
        sql, _ = self.dialect.format_data_type(
            SnowflakeTimestampLtzType(precision=3))
        assert sql == "TIMESTAMP_LTZ(3)"

    def test_timestamp_ntz(self):
        sql, _ = self.dialect.format_data_type(SnowflakeTimestampNtzType())
        assert sql == "TIMESTAMP_NTZ"

    def test_timestamp_tz(self):
        sql, _ = self.dialect.format_data_type(SnowflakeTimestampTzType())
        assert sql == "TIMESTAMP_TZ"

    def test_date(self):
        sql, _ = self.dialect.format_data_type(SnowflakeDateType())
        assert sql == "DATE"

    def test_time(self):
        sql, _ = self.dialect.format_data_type(SnowflakeTimeType())
        assert sql == "TIME"

    def test_time_precision(self):
        sql, _ = self.dialect.format_data_type(
            SnowflakeTimeType(precision=6))
        assert sql == "TIME(6)"

    def test_binary(self):
        sql, _ = self.dialect.format_data_type(SnowflakeBinaryType())
        assert sql == "BINARY"

    def test_binary_length(self):
        sql, _ = self.dialect.format_data_type(
            SnowflakeBinaryType(length=1024))
        assert sql == "BINARY(1024)"

    def test_variant(self):
        sql, _ = self.dialect.format_data_type(SnowflakeVariantType())
        assert sql == "VARIANT"

    def test_object(self):
        sql, _ = self.dialect.format_data_type(SnowflakeObjectType())
        assert sql == "OBJECT"

    def test_array(self):
        sql, _ = self.dialect.format_data_type(SnowflakeArrayType())
        assert sql == "ARRAY"

    def test_geography(self):
        sql, _ = self.dialect.format_data_type(SnowflakeGeographyType())
        assert sql == "GEOGRAPHY"

    def test_geometry(self):
        sql, _ = self.dialect.format_data_type(SnowflakeGeometryType())
        assert sql == "GEOMETRY"
