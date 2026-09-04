# tests/rhosocial/activerecord_snowflake_test/feature/backend/types/test_data_type_parsing.py
"""Tests for Snowflake DataType parsing (parse_type)."""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BooleanType,
    CharType,
    CustomType,
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
    VarCharType,
    BlobType,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeParseType:
    """Test Snowflake type string parsing."""

    def test_parse_integer_types(self, dialect):
        assert isinstance(dialect.parse_type("INTEGER"), IntegerType)
        assert isinstance(dialect.parse_type("INT"), IntegerType)
        assert isinstance(dialect.parse_type("BIGINT"), BigIntType)
        assert isinstance(dialect.parse_type("SMALLINT"), SmallIntType)
        assert isinstance(dialect.parse_type("TINYINT"), IntegerType)
        assert isinstance(dialect.parse_type("BYTEINT"), IntegerType)

    def test_parse_float_types(self, dialect):
        assert isinstance(dialect.parse_type("FLOAT"), FloatType)
        assert isinstance(dialect.parse_type("FLOAT4"), FloatType)
        assert isinstance(dialect.parse_type("FLOAT8"), FloatType)
        assert isinstance(dialect.parse_type("DOUBLE"), DoubleType)
        assert isinstance(dialect.parse_type("DOUBLE PRECISION"), DoubleType)
        assert isinstance(dialect.parse_type("REAL"), DoubleType)

    def test_parse_decimal_types(self, dialect):
        dt = dialect.parse_type("NUMBER(38, 2)")
        assert isinstance(dt, DecimalType)
        assert dt.precision == 38
        assert dt.scale == 2

        dt = dialect.parse_type("DECIMAL(10)")
        assert isinstance(dt, DecimalType)
        assert dt.precision == 10
        assert dt.scale is None

        dt = dialect.parse_type("NUMERIC")
        assert isinstance(dt, DecimalType)
        assert dt.precision is None
        assert dt.scale is None

    def test_parse_string_types(self, dialect):
        assert isinstance(dialect.parse_type("VARCHAR(100)"), VarCharType)
        assert isinstance(dialect.parse_type("VARCHAR"), VarCharType)
        assert isinstance(dialect.parse_type("CHAR(10)"), CharType)
        assert isinstance(dialect.parse_type("CHARACTER(10)"), CharType)
        assert isinstance(dialect.parse_type("TEXT"), TextType)
        assert isinstance(dialect.parse_type("STRING"), TextType)

    def test_parse_date_time_types(self, dialect):
        assert isinstance(dialect.parse_type("DATE"), DateType)
        assert isinstance(dialect.parse_type("TIME"), TimeType)
        assert isinstance(dialect.parse_type("TIMESTAMP"), DateTimeType)
        assert isinstance(dialect.parse_type("TIMESTAMP_NTZ"), DateTimeType)
        assert isinstance(dialect.parse_type("DATETIME"), DateTimeType)

    def test_parse_boolean_type(self, dialect):
        assert isinstance(dialect.parse_type("BOOLEAN"), BooleanType)

    def test_parse_binary_types(self, dialect):
        assert isinstance(dialect.parse_type("BINARY"), BlobType)
        assert isinstance(dialect.parse_type("VARBINARY"), BlobType)

    def test_parse_variant_types(self, dialect):
        assert isinstance(dialect.parse_type("VARIANT"), JsonType)
        assert isinstance(dialect.parse_type("OBJECT"), JsonType)
        assert isinstance(dialect.parse_type("ARRAY"), JsonType)

    def test_parse_unknown_type(self, dialect):
        assert isinstance(dialect.parse_type("CUSTOM_TYPE"), CustomType)
