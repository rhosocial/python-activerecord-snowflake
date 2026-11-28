# tests/rhosocial/activerecord_snowflake_test/feature/backend/types/test_data_type_parsing.py
"""Tests for Snowflake DataType parsing (introspection-only type parser)."""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.introspection.type_parser import (
    SnowflakeTypeParser,
)
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


def _parse(dialect, raw):
    """Read a type spelling through the backend's introspection-only parser."""
    return SnowflakeTypeParser(dialect).parse(raw)


class TestSnowflakeParseType:
    """Test Snowflake type string parsing."""

    def test_parse_integer_types(self, dialect):
        assert isinstance(_parse(dialect, "INTEGER"), IntegerType)
        assert isinstance(_parse(dialect, "INT"), IntegerType)
        assert isinstance(_parse(dialect, "BIGINT"), BigIntType)
        assert isinstance(_parse(dialect, "SMALLINT"), SmallIntType)
        assert isinstance(_parse(dialect, "TINYINT"), IntegerType)
        assert isinstance(_parse(dialect, "BYTEINT"), IntegerType)

    def test_parse_float_types(self, dialect):
        assert isinstance(_parse(dialect, "FLOAT"), FloatType)
        assert isinstance(_parse(dialect, "FLOAT4"), FloatType)
        assert isinstance(_parse(dialect, "FLOAT8"), FloatType)
        assert isinstance(_parse(dialect, "DOUBLE"), DoubleType)
        assert isinstance(_parse(dialect, "DOUBLE PRECISION"), DoubleType)
        assert isinstance(_parse(dialect, "REAL"), DoubleType)

    def test_parse_decimal_types(self, dialect):
        """Declared parameters are kept; a bare word keeps none.

        ``DECIMAL``/``NUMERIC`` are documented as synonymous with ``NUMBER``,
        and a bare ``NUMBER`` is ``NUMBER(38, 0)`` by the manual's own words —
        "By default, precision is 38, and scale is 0". Core no longer resolves
        default parameters from the dialect, so the parser reports exactly what
        the spelling declared: the server applies its own default on write.
        """
        dt = _parse(dialect, "NUMBER(38, 2)")
        assert isinstance(dt, DecimalType)
        assert dt.precision == 38
        assert dt.scale == 2

        dt = _parse(dialect, "DECIMAL(10)")
        assert isinstance(dt, DecimalType)
        assert dt.precision == 10
        assert dt.scale is None

        dt = _parse(dialect, "NUMERIC")
        assert isinstance(dt, DecimalType)
        assert dt.precision is None
        assert dt.scale is None
        assert dt == _parse(dialect, "NUMBER")

    def test_parse_string_types(self, dialect):
        assert isinstance(_parse(dialect, "VARCHAR(100)"), VarCharType)
        assert isinstance(_parse(dialect, "VARCHAR"), VarCharType)
        assert isinstance(_parse(dialect, "CHAR(10)"), CharType)
        assert isinstance(_parse(dialect, "CHARACTER(10)"), CharType)
        assert isinstance(_parse(dialect, "TEXT"), TextType)
        assert isinstance(_parse(dialect, "STRING"), TextType)

    @pytest.mark.parametrize("word", ["TEXT", "STRING"])
    def test_a_sized_text_word_is_the_sized_string_the_manual_says_it_is(self, dialect, word):
        """The size decides, because ``TEXT`` is a synonym of ``VARCHAR``.

        The manual files ``STRING``, ``TEXT``, ``VARCHAR2``, ``NVARCHAR``,
        ``NVARCHAR2``, ``CHAR VARYING`` and ``NCHAR VARYING`` all under
        "Synonymous with VARCHAR" -- there is no separate unbounded text
        storage on this server.  So ``TEXT(50)`` **is** a 50-character
        variable-length string.

        It used to parse as the unbounded concept whatever the size said,
        which dropped the width outright and is not cosmetic: the catalog's
        own ``DATA_TYPE`` word is ``TEXT`` for every string column until
        behaviour-change bundle BCR-1960 lands, and that bundle is
        **postponed with no new release date**, so a ``VARCHAR(50)`` column
        on such an account came back with no width at all.
        https://docs.snowflake.com/en/release-notes/bcr-bundles/un-bundled/bcr-1960
        https://docs.snowflake.com/en/sql-reference/data-types-text
        """
        parsed = _parse(dialect, f"{word}(50)")
        assert isinstance(parsed, VarCharType)
        assert not isinstance(parsed, TextType)
        assert parsed.length == 50

    @pytest.mark.parametrize("word", ["TEXT", "STRING"])
    def test_a_bare_text_word_is_still_the_unbounded_concept(self, dialect, word):
        """The counterpart, so the fix above did not swallow the bare form.

        ``TextType`` carries no width at all, so the bare word is the only
        honest reading of a bare ``TEXT`` -- and this is the branch that
        every unsized string column still needs.
        """
        assert isinstance(_parse(dialect, word), TextType)

    def test_a_sized_text_word_round_trips_to_the_same_width(self, dialect):
        """Rendering the parsed type and parsing it again keeps the width.

        Both halves have to hold, or the width is lost somewhere rather than
        recovered: ``VARCHAR(50)`` renders back to ``VARCHAR(50)``.
        """
        first = _parse(dialect, "TEXT(50)")
        sql, _ = dialect.format_data_type(first)
        assert sql == "VARCHAR(50)"
        assert _parse(dialect, sql) == first

    def test_character_varying_is_variable_length(self, dialect):
        """D8: ``CHARACTER VARYING`` is the long form of ``VARCHAR``.

        It used to come back as a fixed-length ``CharType``, which is the exact
        opposite of what the word says — and worse than not recognising it,
        because the schema differ would then compare a variable-length column
        and a fixed-length one as the same column.
        """
        parsed = _parse(dialect, "CHARACTER VARYING(200)")
        assert isinstance(parsed, VarCharType)
        assert not isinstance(parsed, CharType)
        assert parsed.length == 200
        assert parsed.spelling == "character varying"

    def test_char_varying_is_variable_length(self, dialect):
        """Snowflake's own spelling of the same thing, from the same manual."""
        parsed = _parse(dialect, "CHAR VARYING(80)")
        assert isinstance(parsed, VarCharType)
        assert not isinstance(parsed, CharType)
        assert parsed.length == 80

    def test_character_stays_fixed_length(self, dialect):
        """The counterpart, so the fix above did not simply flip both words."""
        parsed = _parse(dialect, "CHARACTER(10)")
        assert isinstance(parsed, CharType)
        assert not isinstance(parsed, VarCharType)
        assert parsed.length == 10
        assert parsed.spelling == "character"

    def test_char_stays_fixed_length(self, dialect):
        parsed = _parse(dialect, "CHAR(10)")
        assert isinstance(parsed, CharType)
        assert not isinstance(parsed, VarCharType)
        assert parsed.length == 10

    def test_parser_round_trip_preserves_string_width(self, dialect):
        """A parsed type must render back to the *same kind* of column.

        Rendering a concept as the word Snowflake prefers is normalisation and
        is expected — ``TEXT`` becomes ``VARCHAR(16777216)``, because that is
        literally what a Snowflake ``TEXT`` column is. What must never happen is
        a **reversal**: a variable-length string coming back fixed-length or the
        reverse. That is the defect D8 is about, and it is invisible to a plain
        "does it render" check because both render fine.
        """
        cases = {
            "VARCHAR(100)": VarCharType,
            "VARCHAR": VarCharType,
            "CHARACTER VARYING(200)": VarCharType,
            "CHAR VARYING(80)": VarCharType,
            "CHAR(10)": CharType,
            "CHARACTER(10)": CharType,
        }
        for raw, expected in cases.items():
            parsed = _parse(dialect, raw)
            assert isinstance(parsed, expected), f"{raw} -> {type(parsed).__name__}"
            sql, _ = dialect.format_data_type(parsed)
            reparsed = _parse(dialect, sql)
            assert isinstance(reparsed, expected), (
                f"{raw} -> {type(parsed).__name__} -> {sql} -> "
                f"{type(reparsed).__name__}: the round trip changed the width class"
            )

    def test_every_parsed_type_renders_to_real_snowflake_sql(self, dialect):
        """Nothing parsed may render a word Snowflake does not have.

        This is why ``character varying`` must not fall through to
        ``CustomType``: the raw name would then be written out verbatim, and
        ``CHARACTER VARYING`` is not a Snowflake type name.
        """
        known = {
            "VARCHAR", "CHAR", "NUMBER", "FLOAT", "DOUBLE", "REAL", "BOOLEAN",
            "DATE", "TIME", "TIMESTAMP_NTZ", "BINARY", "VARIANT", "OBJECT",
            "ARRAY", "TEXT", "STRING",
        }
        for raw in [
            "VARCHAR(100)", "CHAR(10)", "CHARACTER VARYING(20)", "CHAR VARYING(9)",
            "TEXT", "STRING", "NUMBER(10,2)", "FLOAT", "DOUBLE PRECISION", "REAL",
            "BOOLEAN", "DATE", "TIME", "TIMESTAMP_NTZ", "BINARY", "VARBINARY",
            "VARIANT", "OBJECT", "ARRAY",
        ]:
            sql, _ = dialect.format_data_type(_parse(dialect, raw))
            head = sql.split("(")[0]
            assert head in known, f"{raw} rendered {sql!r}, head not a Snowflake type"

    def test_parse_date_time_types(self, dialect):
        assert isinstance(_parse(dialect, "DATE"), DateType)
        assert isinstance(_parse(dialect, "TIME"), TimeType)
        assert isinstance(_parse(dialect, "TIMESTAMP"), DateTimeType)
        assert isinstance(_parse(dialect, "TIMESTAMP_NTZ"), DateTimeType)
        assert isinstance(_parse(dialect, "DATETIME"), DateTimeType)

    def test_parse_boolean_type(self, dialect):
        assert isinstance(_parse(dialect, "BOOLEAN"), BooleanType)

    def test_parse_binary_types(self, dialect):
        assert isinstance(_parse(dialect, "BINARY"), BlobType)
        assert isinstance(_parse(dialect, "VARBINARY"), BlobType)

    def test_parse_variant_types(self, dialect):
        assert isinstance(_parse(dialect, "VARIANT"), JsonType)
        assert isinstance(_parse(dialect, "OBJECT"), JsonType)
        assert isinstance(_parse(dialect, "ARRAY"), JsonType)

    def test_parse_returns_only_core_classes(self, dialect):
        """A parsed type is a concept, not a backend spelling of one.

        Returning ``SnowflakeVarcharType`` here would make parsing ``VARCHAR``
        and ``TEXT`` two different classes for one storage and force
        the differ to carry a table of strings.  100% core classes is what keeps
        introspection results comparable across backends.

        ``UUID`` is deliberately **not** in the list below: it parses to this
        dialect's own ``SnowflakeUuidType``, because the word identifies the
        backend's native storage rather than a core concept reachable through
        another spelling — the same shape PostgreSQL's ``UUID`` column parses to.
        See :class:`TestParseUuid` below.
        """
        for raw in [
            "VARCHAR(100)", "CHAR(10)", "CHARACTER VARYING(20)", "TEXT", "STRING",
            "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "NUMBER(10,2)", "FLOAT",
            "DOUBLE PRECISION", "REAL", "BOOLEAN", "DATE", "TIME", "TIMESTAMP_NTZ",
            "BINARY", "VARBINARY", "VARIANT", "OBJECT", "ARRAY", "SOMETHING_ELSE",
        ]:
            parsed = _parse(dialect, raw)
            assert type(parsed).__module__.startswith(
                "rhosocial.activerecord.backend.expression.types"
            ), f"{raw} parsed to backend class {type(parsed).__module__}.{type(parsed).__name__}"

    def test_parse_unknown_type(self, dialect):
        assert isinstance(_parse(dialect, "CUSTOM_TYPE"), CustomType)


class TestParseUuid:
    """``UUID`` is a real column type on Snowflake 10.2 and newer.

    Before it was recognised, parsing ``UUID`` fell through to the
    ``CustomType`` escape hatch — which happened to render the right word,
    because ``CustomType`` writes the raw name back out verbatim.  That is right
    SQL for the wrong reason, and it hid the fact that this backend had a type
    it was not modelling: a catalog reporting ``UUID`` produced a type object
    that no ``format_data_type_<name>`` could be asked about, and the word
    existed in the manual's inventory without appearing anywhere in this dialect.

    Note the parse is **not** version-gated.  A pre-10.2 server cannot report a
    ``UUID`` column — the type did not exist — so the catalog seeing the word is
    itself the evidence that the server is new enough, and gating the parse would
    only make introspection lossy on exactly the servers it is meant to describe.
    """

    @pytest.fixture
    def modern(self):
        return SnowflakeDialect(version=(10, 2, 0))

    def test_parse_uuid(self, modern):
        from rhosocial.activerecord.backend.impl.snowflake.expression.types import (
            SnowflakeUuidType,
        )

        parsed = _parse(modern, "UUID")
        assert isinstance(parsed, SnowflakeUuidType)
        assert not isinstance(parsed, CustomType)

    def test_parse_uuid_is_case_insensitive(self, modern):
        from rhosocial.activerecord.backend.impl.snowflake.expression.types import (
            SnowflakeUuidType,
        )

        for raw in ("UUID", "uuid", "Uuid"):
            assert isinstance(_parse(modern, raw), SnowflakeUuidType)

    def test_parse_uuid_round_trips_to_the_same_class(self, modern):
        parsed = _parse(modern, "UUID")
        sql, _ = modern.format_data_type(parsed)
        assert sql == "UUID"
        assert isinstance(_parse(modern, sql), type(parsed))

    def test_uuid_is_not_confused_with_a_string_type(self, modern):
        """A UUID column is not a VARCHAR column with a convention on it.

        The reference page says a UUID "is a 128-bit binary value"; the character
        storage this dialect used to substitute holds 36 bytes of it.  Parsing the
        word back as ``VarCharType`` would make the differ blind to the difference.
        """
        from rhosocial.activerecord.backend.impl.snowflake.expression.types import (
            SnowflakeUuidType,
        )

        assert not isinstance(_parse(modern, "UUID"), VarCharType)
        assert _parse(modern, "UUID") != VarCharType(dialect=modern)
        assert SnowflakeUuidType(dialect=modern) != VarCharType(dialect=modern)

    def test_the_pre_10_2_server_still_parses_the_word_to_the_same_class(self):
        """Parsing is unconditional; only rendering is gated.

        A server that reports ``UUID`` is 10.2 or newer by definition, so the
        parse never has to guess.
        """
        from rhosocial.activerecord.backend.impl.snowflake.expression.types import (
            SnowflakeUuidType,
        )

        assert isinstance(_parse(SnowflakeDialect(), "UUID"), SnowflakeUuidType)


# ---------------------------------------------------------------------------
# The render-parse-re-render sweep: the registry-wide round trip, and the
# defects it found
# ---------------------------------------------------------------------------


class TestTimestampVariantsStayDistinct:
    """The three TIMESTAMP_* words are three storages, not one.

    The branch used to answer DateTimeType for all three, which collapsed a
    ``TIMESTAMP_LTZ`` column and a ``TIMESTAMP_TZ`` column into the NTZ
    concept -- a difference the differ could not see, because both sides of
    a diff are introspected and so both took the same wrong branch.
    ``TIMESTAMP_TZ`` is exactly what core's :class:`TimestampTzType` renders
    here, so the core-class design answers with it; ``TIMESTAMP_LTZ`` has no
    core rendering and follows the UUID exception's shape: a backend-native
    word with no core spelling parses to the backend's own class.
    """

    def test_timestamp_tz_parses_to_the_core_tz_concept(self, dialect):
        from rhosocial.activerecord.backend.expression.types import (
            TimestampTzType,
        )

        parsed = _parse(dialect, "TIMESTAMP_TZ")
        assert isinstance(parsed, TimestampTzType)
        sql, _ = dialect.format_data_type(parsed)
        assert sql == "TIMESTAMP_TZ"

    def test_timestamp_ltz_parses_to_its_own_class(self, dialect):
        from rhosocial.activerecord.backend.impl.snowflake.expression.types import (
            SnowflakeTimestampLtzType,
        )

        parsed = _parse(dialect, "TIMESTAMP_LTZ")
        assert isinstance(parsed, SnowflakeTimestampLtzType)
        sql, _ = dialect.format_data_type(parsed)
        assert sql == "TIMESTAMP_LTZ"

    def test_timestamp_ntz_is_the_datetime_concept_still(self, dialect):
        parsed = _parse(dialect, "TIMESTAMP_NTZ")
        assert isinstance(parsed, DateTimeType)

    def test_the_three_are_three_classes_now(self, dialect):
        ltz = _parse(dialect, "TIMESTAMP_LTZ")
        ntz = _parse(dialect, "TIMESTAMP_NTZ")
        tz = _parse(dialect, "TIMESTAMP_TZ")
        assert ltz != ntz
        assert tz != ntz


class TestTemporalPrecisionIsKept:
    """``TIME(9)`` used to parse to a bare ``TimeType`` that re-rendered "TIME".

    The precision is part of the column's identity, and dropping it turned
    the round trip into a silent widening.
    """

    def test_the_fractional_seconds_precision_is_read_back(self, dialect):
        parsed = _parse(dialect, "TIME(9)")
        assert isinstance(parsed, TimeType)
        assert parsed.precision == 9
        sql, _ = dialect.format_data_type(parsed)
        assert sql == "TIME(9)"
        assert _parse(dialect, sql) == parsed


class TestOwnGeospatialWordsParseBackAsTheirOwnShapes:
    """GEOGRAPHY and GEOMETRY are backend-native words with backend classes.

    They fell through to ``CustomType`` -- the same shape mariadb fixed for
    its eight spatial words, found here by the sweep: the dialect rendered a
    word its own parse did not model.
    """

    @pytest.mark.parametrize(
        "word,expected_module",
        [
            ("GEOGRAPHY", "SnowflakeGeographyType"),
            ("GEOMETRY", "SnowflakeGeometryType"),
        ],
    )
    def test_each_word_reads_back_as_its_own_shape(self, dialect, word, expected_module):
        parsed = _parse(dialect, word)
        assert type(parsed).__name__ == expected_module, word
        assert dialect.format_data_type(parsed) == (word.upper(), ())


class TestUserDefinedTypeReferenceParsesBack:
    """A UDT renders as its quoted, optionally qualified name, and the same

    quoted form is what the catalog reports. The type-name validation that
    guards ``CustomType`` refuses a quoted name by design, so the quoted
    forms are recognised and rebuilt: answering a bare word instead would
    have been a different name, and answering ``CustomType`` raised on this
    dialect's own rendering.
    """

    def test_a_bare_quoted_name_parses_back(self, dialect):
        from rhosocial.activerecord.backend.impl.snowflake.expression.types import (
            SnowflakeUserDefinedType,
        )

        parsed = _parse(dialect, '"my_udt"')
        assert isinstance(parsed, SnowflakeUserDefinedType)
        assert parsed.type_name == "my_udt"

    def test_a_qualified_reference_keeps_its_namespace(self, dialect):
        from rhosocial.activerecord.backend.impl.snowflake.expression.types import (
            SnowflakeUserDefinedType,
        )

        parsed = _parse(dialect, '"db"."s"."my_udt"')
        assert isinstance(parsed, SnowflakeUserDefinedType)
        assert parsed.type_name == "my_udt"
        assert parsed.schema_name == "s"
        assert parsed.database_name == "db"


class TestParseRoundTripSweep:
    """The shared sweep across this backend's whole declared surface.

    Asserts the two invariants everywhere at once: **string stability** --
    parsing a rendering and re-rendering the answer produces the identical
    string -- and **class honesty** -- the answer is the declared instance,
    or the documented widening answer recorded below with its reason. The
    tuple entries pin the documented answers whose re-render deliberately
    differs: the documented synonyms (TINYINT is INTEGER; REAL is DOUBLE)
    and this backend's one semi-structured concept, into which its own
    ARRAY/OBJECT words are normalised.
    """

    #: The documented widening answers: core-concept declarations are
    #: widened onto the storage this backend holds (the datetime concept is
    #: TIMESTAMP_NTZ here; TEXT is VARCHAR; NUMBER carries its documented
    #: default), and the backend's own classes parse back to the core
    #: concept they are the entry point of.
    WIDENING_ANSWERS = {
        "TimeTzType": "TimeType",
        "TimestampType": "DateTimeType",
        "SnowflakeVariantType": "JsonType",
        # Core no longer resolves widths onto bare declarations: the parser
        # fills the server's documented default on read, so these re-render at
        # the default width rather than as the bare word that was read.
        "CharType": ("CharType", "CHAR(1)"),
        "VarCharType": ("VarCharType", "VARCHAR(16777216)"),
        "TextType": "VarCharType",
        "SnowflakeBinaryType": "BlobType",
        "SnowflakeBooleanType": "BooleanType",
        "SnowflakeDateType": "DateType",
        "SnowflakeFloatType": "FloatType",
        "SnowflakeNumberType": "DecimalType",
        "SnowflakeTimeType": "TimeType",
        "SnowflakeTimestampNtzType": "DateTimeType",
        "SnowflakeTimestampTzType": "TimestampTzType",
        "SnowflakeVarcharType": ("VarCharType", "VARCHAR(16777216)"),
        # TINYINT is the manual's documented synonym of INTEGER, and REAL
        # of DOUBLE: the answer class is the concept, and the re-render is
        # the canonical word rather than the synonym.
        "TinyIntType": ("IntegerType", "INTEGER"),
        "RealType": ("DoubleType", "DOUBLE"),
        # The semi-structured family is one concept here: VARIANT serves
        # JSON, OBJECT and ARRAY alike, so the own classes' words parse to
        # it and re-render as VARIANT.
        "SnowflakeArrayType": ("JsonType", "VARIANT"),
        "SnowflakeObjectType": ("JsonType", "VARIANT"),
    }

    @pytest.fixture(scope="class")
    @classmethod
    def roundtrip_module(cls):
        """The round-trip module, loaded from the sibling ``expression`` directory.

        Loading it has no registration side effects: the module builds a
        registry in a fixture instead of mutating a module global at import.
        """
        import importlib.util
        from pathlib import Path

        path = (
            Path(__file__).resolve().parent.parent
            / "expression"
            / "test_expression_roundtrip_all.py"
        )
        spec = importlib.util.spec_from_file_location(
            "snowflake_rt_registry",
            path,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @pytest.fixture(scope="class")
    @classmethod
    def registry(cls, roundtrip_module):
        """The class registry the sweep walks."""
        registry = getattr(roundtrip_module, "ALL_CLASSES", None) or roundtrip_module.REGISTERED
        assert registry, "the round-trip module exposes no registry"
        return registry

    @pytest.fixture(scope="class")
    @classmethod
    def special_registry(cls, roundtrip_module):
        """The round-trip module's special constructors, built on demand.

        The sweep must not depend on another module having registered them at
        import time, so this fixture creates a private registry and fills it
        explicitly before handing it to the sweep.
        """
        from expression_roundtrip_harness import SpecialConstructorRegistry

        registry = SpecialConstructorRegistry()
        roundtrip_module.register_specials(registry)
        return registry

    def test_every_rendered_type_parses_back_coherently(self, registry, special_registry):
        # The sweep is vendored beside the matrix: the testsuite deleted its
        # shared one together with its round-trip harness, when round-trip
        # coverage moved to each backend (mysql did the same).
        from expression_roundtrip_harness import parse_roundtrip_failures
        from rhosocial.activerecord.backend.impl.snowflake.dialect import (
            SnowflakeDialect as _SweepDialect,
        )

        dialect = _SweepDialect(version=(10, 8, 0))
        failures = parse_roundtrip_failures(
            dialect,
            registry,
            special_registry=special_registry,
            widening=self.WIDENING_ANSWERS,
        )
        assert failures == [], "\n".join(failures)
