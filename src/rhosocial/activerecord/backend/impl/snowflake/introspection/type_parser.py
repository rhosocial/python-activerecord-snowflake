# src/rhosocial/activerecord/backend/impl/snowflake/introspection/type_parser.py
"""Snowflake's type-spelling parser (read direction, introspection-only).

Parsing a server-reported type spelling back into a ``DataType`` is not an
expression-construction concern and is no longer a dialect protocol member:
core's ``DataType.parse_data_type_str`` is a fallback that returns
``CustomType``. This backend keeps its real parser here, under introspection,
and uses it only when reading a catalog row back into a column declaration.
"""
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

from .._scan import (
    contains_word,
    decimal_runs,
    first_decimal_after_open_paren,
    leading_word,
    quoted_qualified_name,
    skip_whitespace,
)
from ..expression.types import (
    SnowflakeGeographyType,
    SnowflakeGeometryType,
    SnowflakeTimestampLtzType,
    SnowflakeUserDefinedType,
    SnowflakeUuidType,
)

_TIMESTAMP_PREFIX = "TIMESTAMP_"


def _is_timestamp_variant(word: str) -> bool:
    """Return whether ``word`` is ``TIMESTAMP`` plus an ``_WORD`` suffix.

    ``TIMESTAMP_LTZ``, ``_TZ`` and ``_NTZ`` are one word each, so a suffix that
    runs beyond the word's end -- ``TIMESTAMP_NTZ9`` -- is a different word and
    is not read here.
    """
    if not word.startswith(_TIMESTAMP_PREFIX):
        return False
    suffix = word[len(_TIMESTAMP_PREFIX):]
    return bool(suffix) and all("A" <= ch <= "Z" for ch in suffix)


def _is_double_precision(upper: str, word: str, word_end: int) -> bool:
    """Return whether ``upper`` opens with the two words ``DOUBLE PRECISION``.

    Whitespace alone may separate them.  ``DOUBLEPRECISION`` is one word and
    ``DOUBLE.PRECISION`` is not the spelling the manual uses for one type.
    """
    if word != "DOUBLE":
        return False
    second_start = skip_whitespace(upper, word_end)
    if second_start == word_end:
        return False
    second, _ = leading_word(upper, second_start)
    return second == "PRECISION"


class SnowflakeTypeParser:
    """Parse a raw Snowflake type spelling into a ``DataType``, bound to a dialect."""

    #: The leading word of each family.  The word is compared whole, never as a
    #: prefix: ``INT64`` is not ``INT``, and a family is never matched out of a
    #: parameter that happens to spell it.  Only ``DOUBLE PRECISION`` and the
    #: ``TIMESTAMP_*`` variants span more than one bare word, and each has its
    #: own reader below.
    _SNOW_INTEGER_WORDS = frozenset(
        {"INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "BYTEINT"})
    _SNOW_FLOAT_WORDS = frozenset({"FLOAT", "FLOAT4", "FLOAT8", "DOUBLE", "REAL"})
    _SNOW_DECIMAL_WORDS = frozenset({"NUMBER", "DECIMAL", "NUMERIC"})
    _SNOW_STRING_WORDS = frozenset({"VARCHAR", "CHAR", "CHARACTER", "STRING", "TEXT"})
    _SNOW_BINARY_WORDS = frozenset({"BINARY", "VARBINARY"})
    _SNOW_DATE_WORDS = frozenset({"DATETIME", "TIMESTAMP", "DATE", "TIME"})
    _SNOW_BOOLEAN_WORDS = frozenset({"BOOLEAN"})
    _SNOW_VARIANT_WORDS = frozenset({"VARIANT", "OBJECT", "ARRAY"})
    _SNOW_UUID_WORDS = frozenset({"UUID"})
    _SNOW_GEO_WORDS = frozenset({"GEOGRAPHY", "GEOMETRY"})
    # ``UNSIGNED`` as a whole word anywhere in a type string. Snowflake has no
    # unsigned type and no attribute slot to write one in, so no catalog row can
    # carry this; the parser is also the reader for caller-supplied DDL, and
    # reading the attribute off there would hand back a signed value object for a
    # declaration that says otherwise. Refused by name instead.
    _UNSIGNED_ATTRIBUTE = "UNSIGNED"

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
        # The family is decided by the whole leading word, so a word that only
        # begins the same way -- ``INT64``, ``DATE_XYZ`` -- reads as what it is.
        word, word_end = leading_word(upper)

        if contains_word(stripped, self._UNSIGNED_ATTRIBUTE):
            self._refuse_unsigned_type_string(stripped)

        if word in self._SNOW_INTEGER_WORDS:
            if word == "BIGINT":
                return BigIntType(dialect=dialect)
            if word == "SMALLINT":
                return SmallIntType(dialect=dialect)
            return IntegerType(dialect=dialect)

        if word in self._SNOW_FLOAT_WORDS or _is_double_precision(upper, word, word_end):
            if "DOUBLE" in upper or "REAL" in upper:
                return DoubleType(dialect=dialect)
            return FloatType(dialect=dialect)

        if word in self._SNOW_DECIMAL_WORDS:
            nums = decimal_runs(stripped)
            if len(nums) >= 2:
                return DecimalType(dialect=dialect, precision=int(nums[0]), scale=int(nums[1]))
            if len(nums) == 1:
                return DecimalType(dialect=dialect, precision=int(nums[0]))
            return DecimalType(dialect=dialect)

        if word in self._SNOW_STRING_WORDS:
            length_text = first_decimal_after_open_paren(stripped)
            length = int(length_text) if length_text is not None else None
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

        if word in self._SNOW_BINARY_WORDS:
            return BlobType(dialect=dialect)

        if word in self._SNOW_DATE_WORDS or _is_timestamp_variant(word):
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
                nums = decimal_runs(stripped)
                precision = int(nums[0]) if nums else None
                return TimeType(dialect=dialect, precision=precision)
            if upper.startswith("DATE"):
                if upper.strip() == "DATE":
                    return DateType(dialect=dialect)
                return DateTimeType(dialect=dialect)
            return DateTimeType(dialect=dialect)

        if word in self._SNOW_BOOLEAN_WORDS:
            return BooleanType(dialect=dialect)

        # Semi-structured: VARIANT, OBJECT and ARRAY share one concept (JsonType).
        if word in self._SNOW_VARIANT_WORDS:
            return JsonType(dialect=dialect)

        # Geospatial: own words with own classes, each catalog-reported verbatim.
        if word in self._SNOW_GEO_WORDS:
            if word == "GEOGRAPHY":
                return SnowflakeGeographyType(dialect=dialect)
            return SnowflakeGeometryType(dialect=dialect)

        if word in self._SNOW_UUID_WORDS:
            return SnowflakeUuidType(dialect=dialect)

        # A user-defined type reference renders as its quoted, optionally
        # database- and schema-qualified name, and the catalog reports the same.
        parts = quoted_qualified_name(stripped)
        if parts is not None:
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
