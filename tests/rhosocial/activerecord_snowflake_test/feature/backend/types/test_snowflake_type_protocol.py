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
    SnowflakeUserDefinedType,
    SnowflakeUuidType,
    SnowflakeVariantType,
    SnowflakeVarcharType,
)
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
    BooleanType,
    CharType,
    CustomType,
    DataType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    IntervalType,
    JsonType,
    RealType,
    SmallIntType,
    TextType,
    TimeTzType,
    TimestampTzType,
    TinyIntType,
    UUIDType,
    VarCharType,
)
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins.types import (
    SNOWFLAKE_UUID_TYPE_MIN_VERSION,
)
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeTypeSupport,
)

#: The first server release with a native ``UUID`` column type.  10.2's release
#: notes, Jan 26-30 2026, under "SQL updates": "New UUID data type — This
#: release adds support for the UUID data type."
#: https://docs.snowflake.com/en/release-notes/2026/10_2
UUID_SERVER_VERSION = (10, 2, 0)

SNOWFLAKE_TYPES = [
    SnowflakeVarcharType, SnowflakeNumberType, SnowflakeFloatType,
    SnowflakeBooleanType,
    SnowflakeTimestampLtzType, SnowflakeTimestampNtzType,
    SnowflakeTimestampTzType,
    SnowflakeDateType, SnowflakeTimeType, SnowflakeBinaryType,
    SnowflakeUuidType,
    SnowflakeVariantType, SnowflakeObjectType, SnowflakeArrayType,
    SnowflakeGeographyType, SnowflakeGeometryType,
]

TYPES_WITHOUT_CUSTOM_EQ = [
    SnowflakeVarcharType, SnowflakeNumberType, SnowflakeFloatType,
    SnowflakeBooleanType,
    SnowflakeTimestampLtzType, SnowflakeTimestampNtzType,
    SnowflakeTimestampTzType,
    SnowflakeDateType, SnowflakeTimeType, SnowflakeBinaryType,
    SnowflakeUuidType,
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
                      "snowflake_date", "snowflake_time", "snowflake_blob",
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


class TestNoRenderingOnTypes:
    """A DataType must not render itself.

    The 16 Snowflake types used to inherit a mixin that gave them
    ``format_type()`` / ``ddl()``.  Those methods had no callers: rendering goes
    ``DataType.to_sql()`` → ``dialect.format_data_type(self)`` →
    ``format_data_type_<name>``.  They were also a second copy of every
    formatter, written with f-strings instead of ``dialect.format_*()``.

    The guard is here so nobody re-attaches render logic to a type: a type that
    renders itself is a second source of truth for the same SQL, and it cannot
    be told to write a different spelling.
    """

    def test_types_have_no_format_type(self):
        for cls in SNOWFLAKE_TYPES:
            assert not hasattr(cls, "format_type"), (
                f"{cls.__name__}.format_type exists — rendering belongs on the "
                f"dialect (format_data_type_<name>), not on the type"
            )

    def test_types_have_no_ddl(self):
        for cls in SNOWFLAKE_TYPES:
            assert not hasattr(cls, "ddl"), (
                f"{cls.__name__}.ddl exists — rendering belongs on the dialect "
                f"(format_data_type_<name>), not on the type"
            )

    def test_dead_mixin_is_gone(self):
        import rhosocial.activerecord.backend.impl.snowflake.expression as expr_pkg

        assert not hasattr(expr_pkg, "SnowflakeDataTypeMixin"), (
            "SnowflakeDataTypeMixin is dead code — it existed only to supply "
            "format_type()/ddl(), which nothing called"
        )


class TestSingleInheritance:
    """D1: inheritance means identity, so the chain is linear.

    A second base turns a class into a *category* ("this is a Snowflake type AND
    a varchar"), and the category has to be re-derived at every use.  This
    backend used 16 such classes; it is the guard that keeps them single-base.
    """

    @staticmethod
    def _all_snowflake_types():
        from rhosocial.activerecord.backend.impl.snowflake.expression import types as t

        return [
            value
            for value in vars(t).values()
            if isinstance(value, type)
            and value.__module__ == t.__name__
            and issubclass(value, DataType)
        ]

    def test_the_family_is_not_empty(self):
        """Guard the guard: an empty scan would pass every assertion below.

        Sixteen of these used to be ``(SnowflakeDataTypeMixin, CoreType)``;
        ``SnowflakeUserDefinedType`` already sat directly on ``DataType``, and
        ``SnowflakeUuidType`` was added for the native ``UUID`` that arrived in
        server release 10.2 — both are here to keep the count honest.
        """
        found = self._all_snowflake_types()
        assert len(found) == 18
        assert SnowflakeUserDefinedType in found
        assert SnowflakeUuidType in found

    def test_every_type_has_exactly_one_base(self):
        for cls in self._all_snowflake_types():
            assert len(cls.__bases__) == 1, (
                f"{cls.__name__} has bases {cls.__bases__}; multiple inheritance "
                f"mixes two independent reasons for existing, and the diamond "
                f"edges make the identity of the class ambiguous"
            )

    def test_no_type_inherits_from_object_directly(self):
        for cls in self._all_snowflake_types():
            assert cls.__bases__[0] is not object, (
                f"{cls.__name__} sits directly on object; every data type must "
                f"go through DataType so it is rendered and compared alike"
            )

    def test_no_mixin_remains_in_the_mro(self):
        for cls in self._all_snowflake_types():
            for klass in cls.__mro__:
                assert klass is not object or cls.__bases__ != (object,)
                assert not klass.__name__.endswith("Mixin"), (
                    f"{cls.__name__} inherits {klass.__name__}; a mixin on a "
                    f"DataType adds behaviour that is not the type's identity"
                )


class TestSnowflakeTypeSupportProtocol:
    """The backend's own type family states its non-conventional members."""

    def test_dialect_satisfies_the_protocol(self):
        assert isinstance(SnowflakeDialect(), SnowflakeTypeSupport)

    def test_protocol_declares_the_version_gated_udt_gate(self):
        assert "supports_data_type_snowflake_user_defined" in vars(
            SnowflakeTypeSupport
        )

    def test_udt_gate_is_version_gated(self):
        assert SnowflakeDialect(version=(8, 0, 0)).supports_data_type_snowflake_user_defined() is False
        assert SnowflakeDialect(version=(10, 8, 0)).supports_data_type_snowflake_user_defined() is True

    def test_protocol_declares_the_version_gated_uuid_gate(self):
        """Two conditional members now, so both must be stated.

        The naming convention can express "this dialect renders UUID", which is
        what ``format_data_type_snowflake_uuid`` already says.  It cannot express
        "…except below 10.2", so the gate is the part a reader has to be told
        about, and the protocol is where this dialect states it.
        """
        assert "supports_data_type_snowflake_uuid" in vars(SnowflakeTypeSupport)

    def test_uuid_gate_is_version_gated(self):
        for version, expected in [
            ((8, 0, 0), False),
            ((10, 1, 0), False),
            (UUID_SERVER_VERSION, True),
            ((10, 8, 0), True),
        ]:
            dialect = SnowflakeDialect(version=version)
            assert dialect.supports_data_type_snowflake_uuid() is expected, (
                f"{version} -> {expected}"
            )

    def test_uuid_gate_agrees_with_the_documented_release(self):
        """The constant and the 10.2 announcement must not drift apart."""
        assert SNOWFLAKE_UUID_TYPE_MIN_VERSION == (10, 2, 0)


class TestNativeUuidType:
    """Snowflake has had a native ``UUID`` column type since server 10.2.

    Before this, ``suggested_data_types()["uuid"]`` was ``VarCharType``
    unconditionally, with the claim that "Snowflake has no UUID type: a UUID is
    a 36-character string".  That was true of every release before 10.2 and is
    false of 10.2 onwards, where the manual says "The UUID data type stores
    universally unique identifiers (UUIDs). A UUID is a 128-bit binary value"
    and the 10.2 release notes announce "This release adds support for the UUID
    data type".  Both halves of the fix are asserted here: the native type on a
    new server, the unchanged old behaviour on an old one.
    """

    def setup_method(self):
        self.dialect = SnowflakeDialect(version=UUID_SERVER_VERSION)

    def test_it_renders_the_documented_word(self):
        """``<column_name> UUID`` — the whole of the type's grammar."""
        sql, params = self.dialect.format_data_type(SnowflakeUuidType(self.dialect))
        assert (sql, params) == ("UUID", ())

    def test_it_is_a_kind_of_the_core_uuid_concept(self):
        """Not a lookalike: Snowflake's ``UUID`` *is* a UUID column."""
        assert issubclass(SnowflakeUuidType, UUIDType)
        assert SnowflakeUuidType(self.dialect).name == "snowflake_uuid"

    def test_it_declares_no_parameters(self):
        """The syntax takes no length, precision or scale, so there is nothing
        that could be dropped and nothing to distinguish two of these."""
        assert SnowflakeUuidType.PARAMETERS == ()

    def test_two_of_them_are_the_same_column(self):
        assert SnowflakeUuidType(self.dialect) == SnowflakeUuidType(self.dialect)
        assert hash(SnowflakeUuidType(self.dialect)) == hash(
            SnowflakeUuidType(self.dialect)
        )

    def test_the_uuid_concept_switches_substitute_on_a_10_2_server(self):
        """``uuid`` stays substituted on both sides of 10.2 — the core name is
        not a Snowflake word either way — but the storage it names changes."""
        suggested = self.dialect.suggested_data_types()
        assert suggested["uuid"] is SnowflakeUuidType
        assert "snowflake_uuid" in self.dialect.supports_data_types()

    def test_the_uuid_concept_keeps_varchar_on_an_older_server(self):
        """Byte-identical to what this backend has always suggested."""
        old = SnowflakeDialect(version=(10, 1, 0))
        assert old.suggested_data_types()["uuid"] is VarCharType
        assert "snowflake_uuid" not in old.supports_data_types()

    def test_an_older_server_refuses_the_native_type_by_version(self):
        """A refusal with no version in it is indistinguishable from "never
        considered"; the caller cannot act on it."""
        old = SnowflakeDialect(version=(10, 1, 0))
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            old.format_data_type(SnowflakeUuidType(old))
        message = str(excinfo.value)
        assert "10.2" in message
        assert "VarCharType" in message

    def test_the_suggested_substitute_renders(self):
        """Whatever the suggestion names must produce SQL, or the advice in the
        error message is worthless.

        A bare ``VARCHAR`` substitute now renders ``VARCHAR(16777216)``, which is
        the same column: an unsized ``VARCHAR`` on Snowflake *is* that length, per
        the manual's own "If no length is specified, the default is 16777216".
        """
        for version in ((8, 0, 0), UUID_SERVER_VERSION, (10, 8, 0)):
            dialect = SnowflakeDialect(version=version)
            substitute = dialect.suggested_data_types()["uuid"]
            sql, _ = dialect.format_data_type(substitute(dialect))
            assert sql in ("UUID", "VARCHAR", "VARCHAR(16777216)"), f"{version} -> {sql!r}"

    def test_suggested_and_rendered_stay_disjoint_on_both_sides(self):
        """The two declarations must not collide on either server."""
        for version in ((8, 0, 0), UUID_SERVER_VERSION):
            dialect = SnowflakeDialect(version=version)
            overlap = set(dialect.supports_data_types()) & set(
                dialect.suggested_data_types()
            )
            assert not overlap, f"{version}: {overlap}"

    def test_parse_type_recognises_the_word(self):
        """Introspection used to hand this back as ``CustomType``, which then
        rendered the raw name — right SQL by accident, for the wrong reason."""
        parsed = self.dialect.parse_type("UUID")
        assert isinstance(parsed, SnowflakeUuidType)
        assert self.dialect.format_data_type(parsed)[0] == "UUID"

    def test_parse_type_round_trips(self):
        parsed = self.dialect.parse_type("UUID")
        sql, _ = self.dialect.format_data_type(parsed)
        assert isinstance(self.dialect.parse_type(sql), SnowflakeUuidType)

    def test_the_capability_list_gains_the_type_only_at_10_2(self):
        assert "snowflake_uuid" in SnowflakeDialect(
            version=UUID_SERVER_VERSION
        ).supports_data_types()
        assert "snowflake_uuid" not in SnowflakeDialect(
            version=(10, 1, 0)
        ).supports_data_types()


class TestSuggestedDataTypes:
    def test_returns_a_dict_of_classes(self):
        dialect = SnowflakeDialect()
        result = dialect.suggested_data_types()
        assert isinstance(result, dict)
        for name, klass in result.items():
            assert isinstance(klass, type), f"{name}: value is not a class"
            assert issubclass(klass, DataType), f"{name}: value is not a DataType"

    def test_enum_is_stored_as_varchar(self):
        """Snowflake has no enum type, so the core one has to be refused with
        a way forward rather than with nothing.

        This was an empty dict, which left the core's refusal with no
        substitute to name.
        """
        dialect = SnowflakeDialect()
        assert dialect.suggested_data_types()["enum"] is VarCharType

    def test_keys_are_disjoint_from_supported(self):
        dialect = SnowflakeDialect()
        overlap = set(dialect.supports_data_types()) & set(dialect.suggested_data_types())
        assert not overlap, f"overlap between supported and suggested: {overlap}"

    def test_suggested_advice_is_named_in_the_refusal(self):
        """The whole point of the hook: a caller who asks for a concept this
        backend cannot spell is told what to use instead."""
        dialect = SnowflakeDialect()
        with pytest.raises(TypeError, match="DecimalType"):
            dialect.format_data_type(IntervalType(dialect))

    def test_every_suggested_substitute_is_renderable(self):
        """A suggestion the dialect cannot render is worse than none.

        The message tells the caller "use X instead", so X has to produce SQL.
        """
        dialect = SnowflakeDialect()
        for name, klass in dialect.suggested_data_types().items():
            sql, _ = dialect.format_data_type(klass(dialect))
            assert sql, f"{name} -> {klass.__name__} rendered empty SQL"

    def test_concepts_snowflake_has_no_type_for_are_suggested(self):
        """The 12 concepts Snowflake genuinely has no type for.

        Each is either rendered by this dialect or named here — silence is the
        one answer D9 forbids, because the caller is then told "unsupported" and
        nothing more.
        """
        dialect = SnowflakeDialect()
        supported = dialect.supports_data_types()
        suggested = dialect.suggested_data_types()
        for name in [
            "array", "binary", "custom", "interval", "jsonb", "real",
            "timestamptz", "timetz", "tinyint", "uuid", "varbinary", "xml",
        ]:
            assert name in supported or name in suggested, (
                f"{name} is neither rendered nor suggested"
            )

    def test_binary_and_varbinary_fall_back_to_the_one_byte_string_type(self):
        """Snowflake documents VARBINARY as *synonymous* with BINARY.

        So there is no fixed-length/variable-length pair here, and the honest
        answer is the byte storage that does exist rather than a fake length.
        """
        dialect = SnowflakeDialect()
        suggested = dialect.suggested_data_types()
        assert suggested["binary"] is BlobType
        assert suggested["varbinary"] is BlobType

    def test_xml_falls_back_to_object_not_text(self):
        """PARSE_XML returns an OBJECT, per the Snowflake manual.

        Core's XmlType docstring records TEXT/VARIANT for this backend, which
        disagrees with the manual; the manual is what the server does.
        """
        dialect = SnowflakeDialect()
        assert dialect.suggested_data_types()["xml"] is SnowflakeObjectType

    def test_interval_falls_back_to_exact_numeric(self):
        """Snowflake has no INTERVAL: a time span is a NUMBER of units, and the
        unit is a function argument rather than a column property."""
        dialect = SnowflakeDialect()
        assert dialect.suggested_data_types()["interval"] is DecimalType

    def test_array_falls_back_to_snowflakes_own_array(self):
        """A bare Snowflake ARRAY is the semi-structured form — elements are
        VARIANT and no element type is declared — so it is the substitute for a
        parameterised T[], not a rendering of one."""
        dialect = SnowflakeDialect()
        assert dialect.suggested_data_types()["array"] is SnowflakeArrayType

    def test_uuid_and_jsonb_fall_back_to_what_snowflake_stores(self):
        """The pre-10.2 answer, pinned.

        ``SnowflakeDialect()`` defaults to server 8.0.0, which predates the
        native ``UUID``, so ``VARCHAR`` is still right here — and unchanged.
        :class:`TestNativeUuidType` covers what 10.2 does instead.
        """
        dialect = SnowflakeDialect()
        assert dialect.version < SNOWFLAKE_UUID_TYPE_MIN_VERSION
        suggested = dialect.suggested_data_types()
        assert suggested["uuid"] is VarCharType
        assert suggested["jsonb"] is JsonType


class TestNewCoreRenderers:
    """Concepts this dialect had no answer for at all.

    Before these, ``TinyIntType(dialect).to_sql()`` raised — the dialect had no
    ``format_data_type_tinyint`` — which meant the concept was unconstructible
    here and a caller had nothing to fall back on.
    """

    def setup_method(self):
        self.dialect = SnowflakeDialect()

    def test_tinyint_renders_snowflakes_own_word(self):
        """TINYINT is one of Snowflake's five integer names.

        The manual says they are all NUMBER(38, 0) and that the names exist
        "to suggest the expected range" — so the word renders and the column is
        not eight bits wide.  Refusing it would leave the concept's default
        spelling unusable here.
        """
        sql, _ = self.dialect.format_data_type(TinyIntType(self.dialect))
        assert sql == "TINYINT"

    def test_int1_is_refused_because_snowflake_has_no_such_word(self):
        with pytest.raises(TypeError, match="'int1'"):
            self.dialect.format_data_type(TinyIntType(self.dialect, spelling="int1"))

    def test_real_renders_real(self):
        sql, _ = self.dialect.format_data_type(RealType(self.dialect))
        assert sql == "REAL"

    def test_timestamptz_renders_timestamp_tz(self):
        """TIMESTAMP_TZ keeps the offset with the value, which is what a
        timestamp-with-zone means here."""
        sql, _ = self.dialect.format_data_type(TimestampTzType(self.dialect))
        assert sql == "TIMESTAMP_TZ"

    def test_timestamptz_precision_is_validated(self):
        with pytest.raises(ValueError, match="precision"):
            self.dialect.format_data_type(
                TimestampTzType(self.dialect, precision=10)
            )

    def test_timetz_falls_back_to_time_at_max_precision(self):
        """Snowflake has no TIME WITH TIME ZONE.

        The zone cannot be stored, so it is dropped — but TIME's own default is
        precision 0 and silently discarding the requested fraction is the one
        loss the column cannot recover, so the maximum (9) is written out.
        """
        sql, _ = self.dialect.format_data_type(TimeTzType(self.dialect))
        assert sql == "TIME(9)"

    def test_timetz_keeps_a_requested_precision(self):
        sql, _ = self.dialect.format_data_type(
            TimeTzType(self.dialect, precision=3)
        )
        assert sql == "TIME(3)"

    def test_timetz_precision_is_validated(self):
        with pytest.raises(ValueError, match="precision"):
            self.dialect.format_data_type(
                TimeTzType(self.dialect, precision=10)
            )

    def test_custom_writes_the_validated_name_back_out(self):
        """The escape hatch parse_type() falls back to has to be renderable, or
        a round trip through introspection loses the name it just read."""
        sql, _ = self.dialect.format_data_type(
            CustomType(self.dialect, raw="MY_EXTENSION_TYPE")
        )
        assert sql == "MY_EXTENSION_TYPE"

    def test_custom_cannot_carry_sql(self):
        """The raw name lands where no bound parameter can go, so it is validated
        at construction — which is what makes rendering it safe."""
        with pytest.raises(Exception):
            CustomType(self.dialect, raw="VARCHAR(10)); DROP TABLE t --")


class TestSpellingGates:
    """D9: a backend states which spellings of a concept it writes.

    The closed list is what makes this safe: an unknown spelling is a TypeError
    naming the accepted set, never a string interpolated into SQL.
    """

    def setup_method(self):
        self.dialect = SnowflakeDialect()

    def test_unsupported_spelling_is_refused_and_named(self):
        with pytest.raises(TypeError, match="no_such_spelling"):
            self.dialect.format_data_type(
                IntegerType(self.dialect, spelling="no_such_spelling")
            )

    def test_every_default_spelling_renders(self):
        """The invariant that makes a concept usable on a backend: the spelling
        a bare constructor carries must never be refused."""
        from rhosocial.activerecord.backend.expression import types as core_types
        import inspect

        for name, klass in core_types.__dict__.items():
            if not inspect.isclass(klass) or not issubclass(klass, DataType):
                continue
            spellings = getattr(klass, "SPELLINGS", ())
            if not spellings:
                continue
            try:
                self.dialect.format_data_type(klass(self.dialect))
            except TypeError as exc:
                raise AssertionError(
                    f"{klass.__name__} default spelling was refused: {exc}"
                ) from exc
            # and the concept is declared either way
            assert (
                klass.name in self.dialect.supports_data_types()
                or klass.name in self.dialect.suggested_data_types()
            ), f"{klass.__name__} is neither rendered nor suggested"

    @pytest.mark.parametrize(
        "klass,spelling,expected",
        [
            (IntegerType, "int", "INTEGER"),
            (BigIntType, "int8", "BIGINT"),
            (SmallIntType, "int2", "SMALLINT"),
            (TinyIntType, "tinyint", "TINYINT"),
            (CharType, "character", "CHAR(1)"),
            # An undeclared width renders Snowflake's own default, 16777216, so
            # this row moved from a bare "VARCHAR" when the default became a
            # declared value on the type.  The *word* is unmoved — the spelling
            # gate is not what changed it, the resolved width is — and the
            # column is the same one.
            (VarCharType, "character varying", "VARCHAR(16777216)"),
            (TextType, "clob", "VARCHAR(16777216)"),
            # The same move for the numeric concept, now that core resolves the
            # declared precision and scale: the word is still the one the gate
            # checks, and the resolved pair is what the server stores for a bare
            # ``NUMBER`` — "that is, NUMBER(38, 0)".
            (DecimalType, "dec", "NUMBER(38, 0)"),
            (DecimalType, "numeric", "NUMBER(38, 0)"),
            (DoubleType, "double precision", "DOUBLE"),
            (BooleanType, "bool", "BOOLEAN"),
            (BlobType, "bytea", "BINARY"),
        ],
    )
    def test_accepted_spelling_still_renders_the_same_sql(self, klass, spelling, expected):
        """These renderings predate the gates and must not move.

        A gate that changed the SQL would be a silent rewrite of the caller's
        request, which is the thing the gate exists to prevent.
        """
        sql, _ = self.dialect.format_data_type(klass(self.dialect, spelling=spelling))
        assert sql == expected


# Each core integer width, with the word Snowflake writes for it.  The manual
# puts all six of its integer names (INT, INTEGER, BIGINT, SMALLINT, TINYINT,
# BYTEINT) under one entry: "Synonymous with NUMBER, except that precision and
# scale can't be specified (that is, it always defaults to NUMBER(38, 0))", and
# gives them one shared range, "for all INTEGER data types, the range of values
# is all integer values from -99999999999999999999999999999999999999 to
# +99999999999999999999999999999999999999 (inclusive)".
# https://docs.snowflake.com/en/sql-reference/data-types-numeric
INTEGER_WIDTHS = [
    (TinyIntType, "TINYINT"),
    (SmallIntType, "SMALLINT"),
    (IntegerType, "INTEGER"),
    (BigIntType, "BIGINT"),
]

INTEGER_WIDTH_IDS = [c.__name__ for c, _ in INTEGER_WIDTHS]


class TestIntegerSignedness:
    """``unsigned`` is a field on the integer concepts, and it is not dropped.

    The four formatters used to never read it: ``TinyIntType(unsigned=True)``
    rendered a plain ``TINYINT``, so the constructor accepted a signedness and
    the render threw it away.  That is silent data loss — the column is created
    able to hold the negatives the caller declared it would not, and nothing
    reports it — so the honest behaviour is a refusal that names the width.
    """

    def setup_method(self):
        self.dialect = SnowflakeDialect()

    @pytest.mark.parametrize("klass,expected", INTEGER_WIDTHS, ids=INTEGER_WIDTH_IDS)
    def test_signed_renders_the_snowflake_word(self, klass, expected):
        """The rendering the four formatters have always produced, pinned here so
        the refusal below cannot be paid for by moving it."""
        sql, params = self.dialect.format_data_type(klass(self.dialect))
        assert (sql, params) == (expected, ())

    @pytest.mark.parametrize("klass,expected", INTEGER_WIDTHS, ids=INTEGER_WIDTH_IDS)
    def test_an_explicit_signed_flag_renders_identically(self, klass, expected):
        sql, _ = self.dialect.format_data_type(klass(self.dialect, unsigned=False))
        assert sql == expected

    @pytest.mark.parametrize("klass,expected", INTEGER_WIDTHS, ids=INTEGER_WIDTH_IDS)
    def test_unsigned_is_refused_not_rendered_signed(self, klass, expected):
        """The defect itself.

        The caller is asking for the width's *unsigned* form.  The old
        behaviour returned the signed word and reported success; the message
        must now name the width that has no unsigned form and say why.
        """
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            self.dialect.format_data_type(klass(self.dialect, unsigned=True))
        message = str(excinfo.value)
        assert expected in message, f"{message!r} does not name the width"
        assert "no unsigned integer type" in message

    @pytest.mark.parametrize("klass,expected", INTEGER_WIDTHS, ids=INTEGER_WIDTH_IDS)
    def test_the_refusal_says_what_to_do_instead(self, klass, expected):
        """A refusal with no route forward is the same as silence, only louder."""
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            self.dialect.format_data_type(klass(self.dialect, unsigned=True))
        assert "CHECK constraint" in str(excinfo.value)

    @pytest.mark.parametrize("klass,expected", INTEGER_WIDTHS, ids=INTEGER_WIDTH_IDS)
    def test_no_spelling_produces_an_unsigned_column(self, klass, expected):
        """Every spelling of a concept reaches the same formatter.

        Some this dialect refuses outright (``int1`` for ``TinyIntType``) and
        some it accepts; either way no spelling may yield SQL for an unsigned
        request, so there is no word to reach the same column through.
        """
        for spelling in klass.SPELLINGS:
            try:
                self.dialect.format_data_type(klass(self.dialect, spelling=spelling))
            except TypeError:
                # A refused spelling: the gate fires before the signedness
                # check, and there is nothing to render either way.
                with pytest.raises(TypeError):
                    self.dialect.format_data_type(
                        klass(self.dialect, spelling=spelling, unsigned=True)
                    )
                continue
            with pytest.raises(UnsupportedFeatureError):
                self.dialect.format_data_type(
                    klass(self.dialect, spelling=spelling, unsigned=True)
                )

    @pytest.mark.parametrize("klass,expected", INTEGER_WIDTHS, ids=INTEGER_WIDTH_IDS)
    def test_signedness_still_participates_in_equality(self, klass, expected):
        """Worth stating because it is *why* refusing is the right answer.

        The two declarations are genuinely different types — core puts
        ``unsigned`` in ``PARAMETERS`` — so the differ can see that a caller
        changed its mind.  Refusing at render time stops the DDL from lying
        about that; it must not flatten the model instead.
        """
        signed = klass(self.dialect)
        unsigned = klass(self.dialect, unsigned=True)
        assert signed != unsigned
        assert hash(signed) != hash(unsigned)

    def test_no_width_has_an_unsigned_form(self):
        """Guards the conclusion, not the code.

        If a future Snowflake release documents an unsigned integer, this fails
        and the four formatters have to learn its spelling instead of refusing.
        As of the manual the numeric inventory has no unsigned entry
        (https://docs.snowflake.com/en/sql-reference/intro-summary-data-types),
        the column grammar has no ``UNSIGNED`` attribute after ``<col_type>``
        (https://docs.snowflake.com/en/sql-reference/sql/create-table), and
        "Unsigned integer types (INT(signed = false))" is listed among the
        Parquet features that "aren't supported"
        (https://docs.snowflake.com/en/user-guide/tables-iceberg-data-types).
        """
        documented_words = {
            "NUMBER", "DECIMAL", "DEC", "NUMERIC",
            "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "BYTEINT",
            "FLOAT", "FLOAT4", "FLOAT8",
            "DOUBLE", "REAL", "DECFLOAT",
        }
        for _klass, word in INTEGER_WIDTHS:
            assert word in documented_words
            assert not word.startswith("U"), word


class TestNumericSignedness:
    """``unsigned`` reaches Snowflake through **two** class hierarchies, and every
    one of the six classes that carry it must refuse it.

    The four core concepts — ``DecimalType``, ``FloatType``, ``DoubleType`` and
    ``RealType`` — got the field from core, where it is in ``PARAMETERS`` and
    ``isinstance(unsigned, bool)`` is checked.  The two Snowflake-named classes
    :class:`SnowflakeNumberType` and :class:`SnowflakeFloatType` declare it
    themselves, in the same appended position, because they are **the same two
    Snowflake columns under Snowflake's own words** with their own dispatch keys and
    their own formatters — so the core refusal is not on their path, and leaving
    the field off them would mean one column refused through one name and silently
    written signed through the other.

    Why a refusal rather than a rendering: the manual's summary table of every
    numeric data type Snowflake has — ``NUMBER``, ``DECIMAL``/``NUMERIC``, the six
    integer names, ``FLOAT``/``FLOAT4``/``FLOAT8``,
    ``DOUBLE``/``DOUBLE PRECISION``/``REAL``, ``DECFLOAT`` — has **no unsigned
    row** (https://docs.snowflake.com/en/sql-reference/intro-summary-data-types);
    "Unsigned integer types (INT(signed = false))" is on the manual's own list of
    Parquet features that "aren't supported"
    (https://docs.snowflake.com/en/user-guide/tables-iceberg-data-types); and the
    column grammar is ``<col_name> <col_type>`` followed only by
    ``GENERATED``/``inlineConstraint``/``NOT NULL``/``COLLATE``/``DEFAULT``/
    ``AUTOINCREMENT``/policies/``TAG``/``COMMENT``, so there is not even a spelling
    that would parse
    (https://docs.snowflake.com/en/sql-reference/sql/create-table).

    Snowflake has no local server, so unlike Oracle, ClickHouse and MariaDB these
    are **documentation-based** and are labelled as such in the formatter.
    """

    #: ``(label, class, builder, signed SQL, the word the refusal names)``.
    _NUMERICS = [
        ("decimal", DecimalType,
         lambda d, u: DecimalType(d, 10, 2, unsigned=u),
         "NUMBER(10, 2)", "NUMBER"),
        ("float", FloatType,
         lambda d, u: FloatType(d, 24, unsigned=u),
         "FLOAT(24)", "FLOAT"),
        ("double", DoubleType,
         lambda d, u: DoubleType(d, unsigned=u),
         "DOUBLE", "DOUBLE"),
        ("real", RealType,
         lambda d, u: RealType(d, unsigned=u),
         "REAL", "REAL"),
        ("snowflake_number", SnowflakeNumberType,
         lambda d, u: SnowflakeNumberType(d, precision=10, scale=2, unsigned=u),
         "NUMBER(10, 2)", "NUMBER"),
        ("snowflake_float", SnowflakeFloatType,
         lambda d, u: SnowflakeFloatType(d, precision=24, unsigned=u),
         "FLOAT(24)", "FLOAT"),
    ]
    _IDS = [row[0] for row in _NUMERICS]

    def setup_method(self):
        self.dialect = SnowflakeDialect()

    @pytest.mark.parametrize("label,klass,build,signed_sql,word", _NUMERICS,
                             ids=_IDS)
    def test_unsigned_is_refused_by_name(self, label, klass,
                                         build, signed_sql, word):
        """The rule: the field is in ``PARAMETERS``, so it must reach the SQL or
        flip must raise. Byte-identical SQL for both signs is the violation — and
        it is what all six of these formatters used to produce."""
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            self.dialect.format_data_type(build(self.dialect, True))
        message = str(excinfo.value)
        assert "unsigned" in message
        assert word in message
        assert "no unsigned numeric type" in message

    @pytest.mark.parametrize("label,klass,build,signed_sql,word", _NUMERICS,
                             ids=_IDS)
    def test_the_refusal_says_what_to_do_instead(self, label,
                                                 klass, build, signed_sql, word):
        """A refusal with no route forward is the same as silence, only louder."""
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            self.dialect.format_data_type(build(self.dialect, True))
        assert "CHECK constraint" in str(excinfo.value)

    @pytest.mark.parametrize("label,klass,build,signed_sql,word", _NUMERICS,
                             ids=_IDS)
    def test_the_signed_form_is_byte_identical_to_what_it_was(self,
                                                              label, klass, build,
                                                              signed_sql, word):
        """The refusal is the whole change; nothing else moved."""
        assert self.dialect.format_data_type(
            build(self.dialect, False)) == (signed_sql, ())
        assert self.dialect.format_data_type(
            build(self.dialect, False)) == (signed_sql, ())

    @pytest.mark.parametrize("label,klass,build,signed_sql,word", _NUMERICS,
                             ids=_IDS)
    def test_signedness_still_participates_in_equality(self,
                                                       label, klass, build,
                                                       signed_sql, word):
        """Worth stating because it is *why* refusing is the right answer: the two
        declarations are genuinely different types, so the differ can see that a
        caller changed its mind. Refusing at render time stops the DDL lying about
        that; it must not flatten the model instead."""
        signed, unsigned = build(self.dialect, False), build(self.dialect, True)
        assert signed != unsigned
        assert hash(signed) != hash(unsigned)

    def test_unsigned_is_appended_so_hashes_are_stable(self):
        """Appended, never inserted: the order of ``PARAMETERS`` is what
        ``identity()`` reads, so it is what ``__eq__`` and ``__hash__`` read.

        The two Snowflake-named classes are pinned for the same reason and in the
        same position as their bases: ``("precision", "scale", "unsigned")`` and
        ``("precision", "unsigned")``.  ``spelling`` is *not* declared on either —
        Snowflake writes ``NUMBER`` and ``FLOAT`` and never a synonym as a column
        type, so narrowing it out is correct there, whereas narrowing a field core
        declares as identity is what this class exists to stop doing.
        """
        assert DecimalType.PARAMETERS == ("precision", "scale", "unsigned")
        assert FloatType.PARAMETERS == ("precision", "unsigned")
        assert DoubleType.PARAMETERS == ("unsigned",)
        assert RealType.PARAMETERS == ("unsigned",)
        assert SnowflakeNumberType.PARAMETERS == ("precision", "scale", "unsigned")
        assert SnowflakeFloatType.PARAMETERS == ("precision", "unsigned")

    def test_the_snowflake_classes_really_can_be_given_the_field(self):
        """The point of declaring it on them: before, ``unsigned=True`` on either
        was a ``TypeError`` naming an unexpected keyword, which refuses without
        telling the caller anything about why this backend cannot."""
        for klass, kwargs in ((SnowflakeNumberType, {"precision": 10, "scale": 2}),
                              (SnowflakeFloatType, {"precision": 24})):
            assert klass(**kwargs, unsigned=True).unsigned is True
            assert klass(**kwargs, unsigned=False).unsigned is False

    def test_a_type_string_carrying_unsigned_is_refused_rather_than_read(self):
        """The same rule in the *reading* direction.

        Every ``parse_type`` branch matches on the word in front of the attribute, so
        without a check ``"NUMBER(10,2) UNSIGNED"`` came back as a **signed**
        ``DecimalType(10, 2)`` — a value object ``==`` calls equal to the signed
        column, and the differ would report no change for the one change the string
        describes.
        """
        for raw in ("NUMBER(10,2) UNSIGNED", "FLOAT UNSIGNED", "DOUBLE UNSIGNED",
                    "REAL UNSIGNED", "INTEGER UNSIGNED", "NUMBER UNSIGNED"):
            with pytest.raises(UnsupportedFeatureError) as excinfo:
                self.dialect.parse_type(raw)
            assert "UNSIGNED" in str(excinfo.value), raw
        # ... and unsigned-free strings of the same shapes are untouched.
        assert self.dialect.parse_type("NUMBER(10,2)") == DecimalType(
            self.dialect, 10, 2)
        assert self.dialect.parse_type("DOUBLE") == DoubleType(self.dialect)

    @pytest.mark.parametrize("case,expected", [
        # the pre-existing ValueErrors, still firing for a *signed* declaration
        ("number_precision", ValueError),
        ("number_scale", ValueError),
        ("float_precision", ValueError),
        # ... and the scale-without-precision refusal, also a ValueError
        ("number_scale_without_precision", ValueError),
        # ... and the spelling gate, a TypeError
        ("decimal_bad_spelling", TypeError),
        ("double_bad_spelling", TypeError),
    ])
    def test_every_pre_existing_check_still_fires_for_a_signed_declaration(
            self, case, expected):
        """Nothing moved except the signedness refusal.

        Pinned by *type*, because the point is that each of these still raises what
        it always raised — in particular the "scale requires a precision" refusal,
        which is the one the signedness gate sits in front of.  That refusal is
        now reached only when the bound dialect supplies no precision (core fills
        in the declared 38 on the real dialect), so its case is built against
        :class:`_SnowflakeWithoutNumericDefaults` while the formatter under test
        stays the real dialect's.
        """
        built = {
            "number_precision": DecimalType(self.dialect, precision=99),
            "number_scale": DecimalType(self.dialect, scale=99),
            "float_precision": FloatType(self.dialect, precision=999),
            "number_scale_without_precision": DecimalType(
                _SnowflakeWithoutNumericDefaults(), scale=2),
            "decimal_bad_spelling": DecimalType(self.dialect, precision=10,
                                                spelling="fixed"),
            "double_bad_spelling": DoubleType(self.dialect, spelling="float"),
        }[case]
        with pytest.raises(expected):
            self.dialect.format_data_type(built)

    @pytest.mark.parametrize("case", [
        "number_precision", "number_scale", "float_precision",
        "number_scale_without_precision", "decimal_bad_spelling",
        "double_bad_spelling",
    ])
    def test_the_signedness_gate_runs_before_those_checks(self, case):
        """A request wrong in two ways is told about the right one first.

        Signedness is a declaration this grammar cannot express **at all**, which is
        a stronger and less recoverable statement than an out-of-range number, so
        the refusal comes first. Not observable any other way: every assertion above
        passes with either order.
        """
        built = {
            "number_precision": DecimalType(self.dialect, precision=99,
                                            unsigned=True),
            "number_scale": DecimalType(self.dialect, scale=99, unsigned=True),
            "float_precision": FloatType(self.dialect, precision=999,
                                         unsigned=True),
            "number_scale_without_precision": DecimalType(self.dialect, scale=2,
                                                           unsigned=True),
            "decimal_bad_spelling": DecimalType(self.dialect, precision=10,
                                                spelling="fixed", unsigned=True),
            "double_bad_spelling": DoubleType(self.dialect, spelling="float",
                                              unsigned=True),
        }[case]
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            self.dialect.format_data_type(built)
        assert "unsigned" in str(excinfo.value)

    def test_the_refusal_is_not_a_value_error(self):
        """The cross-backend exception convention, stated as a test: a wrong value
        is ``ValueError``; a declaration this grammar cannot express at all is
        ``UnsupportedFeatureError``; the two do not share a base class."""
        assert not issubclass(UnsupportedFeatureError, ValueError)
        with pytest.raises(UnsupportedFeatureError):
            self.dialect.format_data_type(
                DecimalType(self.dialect, unsigned=True))


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

    def test_number_scale_at_the_documented_maximum(self):
        """"The *maximum scale* ... is 37."

        37, not 38: a NUMBER holds 38 digits in total and at least one of them
        is to the left of the point.
        https://docs.snowflake.com/en/sql-reference/data-types-numeric
        """
        dialect = SnowflakeDialect()
        sql, _ = SnowflakeNumberType(
            dialect, precision=38, scale=37
        ).to_sql()
        assert sql == "NUMBER(38, 37)"

    def test_number_scale_one_past_the_documented_maximum_is_refused(self):
        """The old limit here was 38, so ``NUMBER(10, 38)`` was written out.

        That is a value the manual does not document, and the error must name the
        value *and* the limit so the caller can see which one to move.
        """
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError) as excinfo:
            SnowflakeNumberType(dialect, precision=10, scale=38).to_sql()
        message = str(excinfo.value)
        assert "0-37" in message
        assert "38" in message

    def test_number_scale_negative_is_refused(self):
        dialect = SnowflakeDialect()
        with pytest.raises(ValueError, match="scale must be"):
            SnowflakeNumberType(dialect, precision=10, scale=-1).to_sql()


class _SnowflakeWithoutNumericDefaults(SnowflakeDialect):
    """This dialect minus the numeric entry, so the fallback refusal stays testable.

    On the real dialect the missing precision is resolved to 38 in core before
    the formatter runs, which is the desired behaviour — but it leaves the
    "scale with no precision" guard with no way to fire.  The guard still
    protects a type bound to a dialect that supplies no precision, so it is
    exercised here through the ordinary formatter path rather than deleted
    along with its old pin.
    """

    def type_parameter_defaults(self):
        return {}


class TestNumberScaleIsNotDropped:
    """``scale`` is in ``PARAMETERS``, so it is part of the type's identity.

    Constructing ``SnowflakeNumberType`` with a different ``scale`` produced
    byte-identical SQL when ``precision`` was absent: ``scale=2`` and ``scale=7``
    both rendered a bare ``NUMBER``, which is ``NUMBER(38, 0)`` — a column with
    no fractional digits at all, for a declaration that asked for two or for
    seven, and ``__eq__`` had just said the two declarations are different
    columns.  Snowflake supports the scale fully ("Number of digits allowed to
    the right of the decimal point", maximum 37), so this one is *honoured*, not
    refused.

    A scale with no declared precision is now honoured too.  Core resolves the
    missing precision to the documented default of 38 before the formatter sees
    it, so ``SnowflakeNumberType(dialect, scale=2)`` renders ``NUMBER(38, 2)``
    — which is the column the server stores for a declaration whose precision
    the default supplies.  The refusal that remains in ``_format_number`` fires
    only for a type bound to a dialect that supplies no precision at all.
    """

    def setup_method(self):
        self.dialect = SnowflakeDialect()

    def test_two_scales_without_a_precision_now_render_differently(self):
        """The defect, stated as the measurement that found it.

        Before the scale was honoured at all, both declarations rendered a bare
        ``NUMBER`` — one column, for two declarations ``==`` called different.
        Before the dialect default was resolved onto the type they both raised
        instead.  The documented default precision of 38 is what fills the
        missing half now, so each renders the column the server would store.
        """
        two, _ = self.dialect.format_data_type(
            SnowflakeNumberType(self.dialect, scale=2)
        )
        seven, _ = self.dialect.format_data_type(
            SnowflakeNumberType(self.dialect, scale=7)
        )
        assert two == "NUMBER(38, 2)"
        assert seven == "NUMBER(38, 7)"
        assert two != seven

    @pytest.mark.parametrize("scale", [0, 1, 2, 10, 37])
    def test_a_declared_scale_is_written_out(self, scale):
        sql, _ = self.dialect.format_data_type(
            SnowflakeNumberType(self.dialect, precision=20, scale=scale)
        )
        assert sql == f"NUMBER(20, {scale})"

    def test_different_scales_now_render_differently(self):
        """The point of the fix: flipping the field changes the SQL."""
        two = self.dialect.format_data_type(
            SnowflakeNumberType(self.dialect, precision=20, scale=2)
        )
        seven = self.dialect.format_data_type(
            SnowflakeNumberType(self.dialect, precision=20, scale=7)
        )
        assert two != seven

    def test_the_core_decimal_concept_is_honoured_the_same_way(self):
        """``DECIMAL``/``DEC``/``NUMERIC`` are documented as synonymous with
        ``NUMBER``, so they cannot answer differently about the same syntax."""
        sql, _ = self.dialect.format_data_type(
            DecimalType(self.dialect, precision=20, scale=2)
        )
        assert sql == "NUMBER(20, 2)"
        sql, _ = self.dialect.format_data_type(
            DecimalType(self.dialect, scale=2)
        )
        assert sql == "NUMBER(38, 2)"

    def test_a_scale_without_a_precision_is_refused_when_nothing_supplies_one(self):
        """Snowflake's grammar is ``NUMBER [ ( precision [, scale] ) ]``.

        The scale is the optional *second* argument inside the parenthesis; there
        is no ``NUMBER(scale)`` form.  Core fills the missing precision from this
        dialect's declaration, so on the real backend the combination renders
        ``NUMBER(38, 2)``; when the bound dialect declares no precision there is
        nothing to fill in, and writing a bare ``NUMBER`` would silently decide
        ``NUMBER(38, 0)``.  So the formatter refuses and names the field.
        """
        dialect = _SnowflakeWithoutNumericDefaults()
        with pytest.raises(ValueError) as excinfo:
            dialect.format_data_type(
                SnowflakeNumberType(dialect, scale=2)
            )
        message = str(excinfo.value)
        assert "scale=2" in message, message
        assert "precision" in message, message
        assert "NUMBER" in message, message

    def test_the_refusal_says_what_to_declare_instead(self):
        """A refusal with no route forward is the same as silence, only louder."""
        dialect = _SnowflakeWithoutNumericDefaults()
        with pytest.raises(ValueError) as excinfo:
            dialect.format_data_type(
                SnowflakeNumberType(dialect, scale=4)
            )
        assert "precision=38" in str(excinfo.value)

    def test_the_suggested_precision_actually_renders(self):
        """The advice names a declaration; check it is one this dialect accepts."""
        dialect = _SnowflakeWithoutNumericDefaults()
        with pytest.raises(ValueError) as excinfo:
            dialect.format_data_type(
                SnowflakeNumberType(dialect, scale=4)
            )
        assert "NUMBER(38, 4)" in str(excinfo.value)
        sql, _ = self.dialect.format_data_type(
            SnowflakeNumberType(self.dialect, precision=38, scale=4)
        )
        assert sql == "NUMBER(38, 4)"

    def test_scale_still_participates_in_equality(self):
        """Worth stating because it is *why* refusing is the right answer: the
        two declarations are genuinely different types, so the differ can see a
        caller change its mind.  Refusing at render time must not flatten it."""
        a = SnowflakeNumberType(self.dialect, precision=10, scale=2)
        b = SnowflakeNumberType(self.dialect, precision=10, scale=3)
        assert a != b
        assert hash(a) != hash(b)

    def test_precision_only_now_writes_the_servers_scale_too(self):
        """``NUMBER(10)`` is stored as ``NUMBER(10, 0)``, and now says so.

        The manual gives the defaults as "precision is 38, and scale is 0; that
        is, NUMBER(38, 0)", and a declaration that names a precision and no
        scale is still a column with scale 0.  Core resolves the declared scale
        onto the type, so the formatter writes the pair out.  The two spellings
        are one column; the explicit one is what the catalog reports.
        """
        sql, _ = self.dialect.format_data_type(
            SnowflakeNumberType(self.dialect, precision=10)
        )
        assert sql == "NUMBER(10, 0)"

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


class TestDeclaredParameterDefaults:
    """What this server supplies for a declaration that named nothing.

    Core resolves a declared default onto the type at read time, keyed by the
    type's own ``name`` — so the declaration has to be right for the concept it
    is filed under, and a backend type reached through this dialect's own entry
    point has to declare under its own name too.
    https://docs.snowflake.com/en/sql-reference/data-types-text
    https://docs.snowflake.com/en/sql-reference/data-types-numeric
    """

    def setup_method(self):
        self.dialect = SnowflakeDialect()

    def test_the_widths_are_the_manuals_own_numbers(self):
        declared = self.dialect.type_parameter_defaults()
        # "If no length is specified, the default is 16777216."
        assert declared["varchar"] == {"length": 16777216}
        # "CHAR ... except that if the length is not specified, CHAR(1) is the
        # default."
        assert declared["char"] == {"length": 1}
        # A backend type is the same concept through its own entry point, so it
        # declares under its own dispatch key. Two names, one width — declared
        # side by side because a dialect that let them drift would be describing
        # one storage two ways.
        assert declared["snowflake_varchar"] == declared["varchar"]

    def test_the_numeric_default_is_the_manuals_own_pair(self):
        declared = self.dialect.type_parameter_defaults()
        # "By default, precision is 38, and scale is 0; that is, NUMBER(38, 0)."
        assert declared["decimal"] == {"precision": 38, "scale": 0}
        assert declared["snowflake_number"] == declared["decimal"]

    def test_declaring_the_numeric_default_now_reaches_the_formatter(self):
        """The resolved default is what the server stores, so it is what is written.

        ``DecimalType.precision``/``scale`` now resolve at read time exactly as
        ``VarCharType.length`` does, so the declaration added to stop the
        introspector dropping a sized NUMBER's precision and scale is
        load-bearing in the other direction too: a bare declaration renders
        ``NUMBER(38, 0)`` rather than a bare ``NUMBER``.  That is a rendering
        change and it is the correct one — "By default, precision is 38, and
        scale is 0; that is, NUMBER(38, 0)" — and ``NUMBER(38, 0)`` is
        semantically the same column as ``NUMBER``, which ``DESC TABLE`` renders
        identically.  The explicit pair is also what the catalog reports, so
        writing it is what makes a bare declaration compare equal to its own
        round trip.
        """
        assert DecimalType(self.dialect).precision == 38
        assert DecimalType(self.dialect).scale == 0
        sql, _ = DecimalType(self.dialect).to_sql()
        assert sql == "NUMBER(38, 0)"
        assert DecimalType(self.dialect) == DecimalType(
            self.dialect, precision=38, scale=0
        )
        sql, _ = SnowflakeNumberType(self.dialect).to_sql()
        assert sql == "NUMBER(38, 0)"
        # ...while the declared width reaches the formatter, as it always did.
        assert VarCharType(self.dialect).length == 16777216

    def test_concepts_the_manual_defines_without_parameters_are_not_declared(self):
        """Declaring a parameter the type refuses to accept would be inventing it.

        * the integer names: "Synonymous with NUMBER, except precision and scale
          can't be specified" — there is nothing to supply.
        * the float family: ``DESC TABLE`` renders a bare ``FLOAT``.
        * ``text``: ``VARCHAR(16777216)`` is written out by its own formatter, so
          it is not a bare form with a default to fill in.
        * ``blob``: ``BINARY``'s length is in **bytes** and ``BlobType`` carries
          no width at all, so there is no field for the framework to resolve.
        """
        declared = self.dialect.type_parameter_defaults()
        for absent in ("integer", "bigint", "smallint", "tinyint",
                       "float", "snowflake_float", "double", "real",
                       "text", "blob", "snowflake_blob"):
            assert absent not in declared, f"{absent} should declare nothing"


class TestFormatting:
    def setup_method(self):
        self.dialect = SnowflakeDialect()

    def test_varchar_no_length(self):
        """No declared width means Snowflake's default, written out.

        "If no length is specified, the default is 16777216."
        (https://docs.snowflake.com/en/sql-reference/data-types-text)
        """
        sql, _ = SnowflakeVarcharType(self.dialect).to_sql()
        assert sql == "VARCHAR(16777216)"
        assert SnowflakeVarcharType(self.dialect).length == 16777216
        # and the declared width is the one the catalog's word parses back to.
        # The classes stay apart on purpose — ``parse_type`` yields core classes
        # only, see ``test_parse_returns_only_core_classes`` — so this compares
        # the widths, which is what the differ compares within one concept.
        assert self.dialect.parse_type("VARCHAR").length == 16777216
        assert VarCharType(self.dialect) == self.dialect.parse_type("VARCHAR")

    def test_varchar_with_length(self):
        sql, _ = SnowflakeVarcharType(self.dialect, length=255).to_sql()
        assert sql == "VARCHAR(255)"

    def test_number_no_params(self):
        """A bare ``NUMBER`` is ``NUMBER(38, 0)``, and the default is now resolved.

        "By default, precision is 38, and scale is 0; that is, NUMBER(38, 0)"
        and ``DESC TABLE`` renders both spellings identically — core resolves
        the dialect's declared pair onto the type, so the rendering carries it.
        """
        sql, _ = SnowflakeNumberType(self.dialect).to_sql()
        assert sql == "NUMBER(38, 0)"

    def test_number_precision_only(self):
        sql, _ = SnowflakeNumberType(self.dialect, precision=10).to_sql()
        assert sql == "NUMBER(10, 0)"

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
