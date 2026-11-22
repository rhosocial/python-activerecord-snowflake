# src/rhosocial/activerecord/backend/impl/snowflake/introspection/type_parser.py
"""Snowflake's type-spelling parser (read direction, introspection-only).

Parsing a server-reported type spelling back into a ``DataType`` is not an
expression-construction concern and is no longer a dialect protocol member:
core's ``DataType.parse_data_type_str`` is a fallback that returns
``CustomType``. This backend keeps its real parser here, under introspection,
and uses it only when reading a catalog row back into a column declaration.
"""
import re

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
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
    TimestampTzType,
    VarCharType,
)
from ..expression.types import (
    SnowflakeGeographyType,
    SnowflakeGeometryType,
    SnowflakeTimestampLtzType,
    SnowflakeUserDefinedType,
    SnowflakeUuidType,
)


class SnowflakeTypeParser:
    """Parse a raw Snowflake type spelling into a ``DataType``, bound to a dialect."""

    _SNOW_INTEGER_TYPES = re.compile(r"^(?:INT|INTEGER|BIGINT|SMALLINT|TINYINT|BYTEINT)\b", re.IGNORECASE)
    _SNOW_FLOAT_TYPES = re.compile(r"^(?:FLOAT|FLOAT4|FLOAT8|DOUBLE|DOUBLE\s+PRECISION|REAL)\b", re.IGNORECASE)
    _SNOW_DECIMAL_TYPES = re.compile(r"^(?:NUMBER|DECIMAL|NUMERIC)\b", re.IGNORECASE)
    _SNOW_STRING_TYPES = re.compile(r"^(?:VARCHAR|CHAR|CHARACTER|STRING|TEXT)\b", re.IGNORECASE)
    _SNOW_BINARY_TYPES = re.compile(r"^(?:BINARY|VARBINARY)\b", re.IGNORECASE)
    _SNOW_DATE_TYPES = re.compile(r"^(?:DATETIME|TIMESTAMP(?:_[A-Z]+)?|DATE|TIME)\b", re.IGNORECASE)
    _SNOW_BOOLEAN_TYPES = re.compile(r"^(?:BOOLEAN)\b", re.IGNORECASE)
    _SNOW_VARIANT_TYPES = re.compile(r"^(?:VARIANT|OBJECT|ARRAY)\b", re.IGNORECASE)
    _SNOW_UUID_TYPES = re.compile(r"^UUID\b", re.IGNORECASE)
    _SNOW_GEO_TYPES = re.compile(r"^(?:GEOGRAPHY|GEOMETRY)\b", re.IGNORECASE)
    # ``UNSIGNED`` as a whole word anywhere in a type string. Snowflake has no
    # unsigned type and no attribute slot to write one in, so no catalog row can
    # carry this; the parser is also the reader for caller-supplied DDL, and
    # reading the attribute off there would hand back a signed value object for a
    # declaration that says otherwise. Refused by name instead.
    _UNSIGNED_ATTRIBUTE = re.compile(r"\bUNSIGNED\b", re.IGNORECASE)

    def __init__(self, dialect):
        self.dialect = dialect

    def _refuse_unsigned_type_string(self, raw: str) -> None:
        """Refuse a type string carrying an ``UNSIGNED`` attribute.

        Reading the attribute off and returning a signed type would compare
        equal to the signed column — the silent loss this refuses. Snowflake's
        numeric inventory has no unsigned row, so no catalog row can carry it;
        this guards the caller-supplied DDL path.
        """
        raise UnsupportedFeatureError(
            self.dialect.name,
            f"an UNSIGNED attribute in a type string ({raw!r}) "
            f"(Snowflake has no unsigned numeric type, so no declaration and no "
            f"catalog row can carry UNSIGNED; reading the attribute off and "
            f"returning a signed type would compare equal to the signed column, "
            f"which is the silent loss this refuses.)",
            suggestion=(
                "Declare the column signed and enforce the range with a CHECK "
                "constraint if negatives must be rejected."
            ),
        )

    def parse(self, raw: str) -> DataType:
        dialect = self.dialect
        stripped = raw.strip()
        upper = stripped.upper()

        if self._UNSIGNED_ATTRIBUTE.search(stripped):
            self._refuse_unsigned_type_string(stripped)

        if self._SNOW_INTEGER_TYPES.match(upper):
            if upper.startswith("BIGINT"):
                return BigIntType(dialect=dialect)
            if upper.startswith("SMALLINT"):
                return SmallIntType(dialect=dialect)
            return IntegerType(dialect=dialect)

        if self._SNOW_FLOAT_TYPES.match(upper):
            if "DOUBLE" in upper or "REAL" in upper:
                return DoubleType(dialect=dialect)
            return FloatType(dialect=dialect)

        if self._SNOW_DECIMAL_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            if len(nums) >= 2:
                return DecimalType(dialect=dialect, precision=int(nums[0]), scale=int(nums[1]))
            if len(nums) == 1:
                return DecimalType(dialect=dialect, precision=int(nums[0]))
            return DecimalType(dialect=dialect)

        if self._SNOW_STRING_TYPES.match(upper):
            length_match = re.search(r"\((\d+)", stripped)
            length = int(length_match.group(1)) if length_match else None
            # An unsized declaration is completed from the dialect's documented
            # default rather than from a number invented here. A *sized* TEXT is
            # a variable-length string (TEXT is a documented synonym of VARCHAR),
            # while a bare TEXT stays the unbounded TextType concept.
            varchar_default = dialect._SNOW_VARCHAR_DEFAULT_LENGTH
            char_default = dialect._SNOW_CHAR_DEFAULT_LENGTH
            # ``VARYING`` has to be decided first: both ``CHARACTER VARYING`` and
            # Snowflake's own ``CHAR VARYING`` name the variable-length string.
            if upper.startswith("CHARACTER VARYING") or upper.startswith("CHAR VARYING"):
                return VarCharType(
                    dialect=dialect,
                    length=length or varchar_default,
                    spelling="character varying",
                )
            if "VARCHAR" in upper:
                return VarCharType(dialect=dialect, length=length or varchar_default)
            if ("TEXT" in upper or "STRING" in upper) and length is not None:
                return VarCharType(dialect=dialect, length=length)
            if "TEXT" in upper or "STRING" in upper:
                return TextType(dialect=dialect)
            if upper.startswith("CHARACTER"):
                return CharType(
                    dialect=dialect,
                    length=length or char_default,
                    spelling="character",
                )
            return CharType(dialect=dialect, length=length or char_default)

        if self._SNOW_BINARY_TYPES.match(upper):
            return BlobType(dialect=dialect)

        if self._SNOW_DATE_TYPES.match(upper):
            # The three TIMESTAMP_* words are three storages and each parses to
            # its own class; collapsing them made the differ blind to a change
            # between TIMESTAMP_LTZ/TZ/NTZ columns.
            if "TIMESTAMP" in upper:
                if "TIMESTAMP_LTZ" in upper:
                    return SnowflakeTimestampLtzType(dialect=dialect)
                if "TIMESTAMP_TZ" in upper:
                    return TimestampTzType(dialect=dialect)
                return DateTimeType(dialect=dialect)
            if upper.startswith("TIME"):
                nums = re.findall(r"\d+", stripped)
                precision = int(nums[0]) if nums else None
                return TimeType(dialect=dialect, precision=precision)
            if upper.startswith("DATE"):
                if upper.strip() == "DATE":
                    return DateType(dialect=dialect)
                return DateTimeType(dialect=dialect)
            return DateTimeType(dialect=dialect)

        if self._SNOW_BOOLEAN_TYPES.match(upper):
            return BooleanType(dialect=dialect)

        # Semi-structured: VARIANT, OBJECT and ARRAY share one concept (JsonType).
        if self._SNOW_VARIANT_TYPES.match(upper):
            return JsonType(dialect=dialect)

        # Geospatial: own words with own classes, each catalog-reported verbatim.
        if self._SNOW_GEO_TYPES.match(upper):
            if upper.startswith("GEOGRAPHY"):
                return SnowflakeGeographyType(dialect=dialect)
            return SnowflakeGeometryType(dialect=dialect)

        if self._SNOW_UUID_TYPES.match(upper):
            return SnowflakeUuidType(dialect=dialect)

        # A user-defined type reference renders as its quoted, optionally
        # database- and schema-qualified name, and the catalog reports the same.
        udt_match = re.match(r'^(?:"[^"]+"\s*\.\s*){0,2}"[^"]+"$', stripped)
        if udt_match is not None:
            parts = re.findall(r'"([^"]+)"', stripped)
            if len(parts) == 1:
                return SnowflakeUserDefinedType(dialect=dialect, type_name=parts[0])
            if len(parts) == 2:
                return SnowflakeUserDefinedType(
                    dialect=dialect, type_name=parts[1], schema_name=parts[0])
            return SnowflakeUserDefinedType(
                dialect=dialect, type_name=parts[2], schema_name=parts[1],
                database_name=parts[0])

        return CustomType(dialect=dialect, raw=stripped)


__all__ = ["SnowflakeTypeParser"]
