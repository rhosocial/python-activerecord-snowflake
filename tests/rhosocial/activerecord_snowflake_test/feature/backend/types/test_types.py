# tests/rhosocial/activerecord_snowflake_test/feature/backend/types/test_types.py
"""Tests for Snowflake type helper classes."""
import pytest

from rhosocial.activerecord.backend.impl.snowflake.types import (
    SnowflakeVariant,
    SnowflakeArray,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
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


class TestSnowflakeVariant:
    def test_create_with_dict(self):
        v = SnowflakeVariant({"key": "value"})
        assert v.value == {"key": "value"}

    def test_create_with_list(self):
        v = SnowflakeVariant([1, 2, 3])
        assert v.value == [1, 2, 3]

    def test_create_with_none(self):
        v = SnowflakeVariant(None)
        assert v.value is None

    def test_create_default(self):
        v = SnowflakeVariant()
        assert v.value is None

    def test_to_database(self):
        data = {"a": 1}
        v = SnowflakeVariant(data)
        assert v.to_database() == data

    def test_repr(self):
        v = SnowflakeVariant({"key": "value"})
        assert "SnowflakeVariant" in repr(v)
        assert "key" in repr(v)

    def test_equality_same_type(self):
        v1 = SnowflakeVariant({"key": "value"})
        v2 = SnowflakeVariant({"key": "value"})
        assert v1 == v2

    def test_equality_different_type(self):
        v = SnowflakeVariant({"key": "value"})
        assert v == {"key": "value"}

    def test_inequality(self):
        v1 = SnowflakeVariant({"a": 1})
        v2 = SnowflakeVariant({"b": 2})
        assert v1 != v2

    def test_hash(self):
        v1 = SnowflakeVariant({"key": "value"})
        v2 = SnowflakeVariant({"key": "value"})
        assert hash(v1) == hash(v2)


class TestSnowflakeArray:
    def test_create_with_list(self):
        a = SnowflakeArray([1, 2, 3])
        assert a.elements == [1, 2, 3]

    def test_create_empty(self):
        a = SnowflakeArray()
        assert a.elements == []

    def test_create_with_none(self):
        a = SnowflakeArray(None)
        assert a.elements == []

    def test_to_database(self):
        a = SnowflakeArray([1, 2, 3])
        assert a.to_database() == [1, 2, 3]

    def test_len(self):
        a = SnowflakeArray([1, 2, 3])
        assert len(a) == 3

    def test_getitem(self):
        a = SnowflakeArray([10, 20, 30])
        assert a[0] == 10
        assert a[2] == 30

    def test_getitem_slice(self):
        a = SnowflakeArray([10, 20, 30, 40])
        assert a[1:3] == [20, 30]

    def test_repr(self):
        a = SnowflakeArray([1, 2])
        assert "SnowflakeArray" in repr(a)

    def test_equality_same_type(self):
        a1 = SnowflakeArray([1, 2])
        a2 = SnowflakeArray([1, 2])
        assert a1 == a2

    def test_equality_different_type(self):
        a = SnowflakeArray([1, 2])
        assert a == [1, 2]

    def test_inequality(self):
        a1 = SnowflakeArray([1, 2])
        a2 = SnowflakeArray([3, 4])
        assert a1 != a2


# The construction-parameter matrix below is the "before" snapshot: every one of
# these types used to declare its own ``format_type()`` that returned exactly
# these strings, and 15 of them also declared their own identity.  Both were
# deleted — the renderers were dead code with no callers, and the params tuples
# were identical to the base class's.  This module is what proves the deletion
# changed neither the SQL nor equality.
TYPE_MATRIX = [
    # An undeclared width is Snowflake's own default, 16777216 — "If no length
    # is specified, the default is 16777216"
    # (https://docs.snowflake.com/en/sql-reference/data-types-text) — so the
    # snapshot is ``VARCHAR(16777216)``, not a bare ``VARCHAR``.  The same now
    # holds for the numeric rows, because core resolves ``DecimalType``'s
    # declared precision and scale the way it resolves ``length``: a bare
    # ``NUMBER`` is the ``NUMBER(38, 0)`` the manual documents and the server
    # stores, and ``NUMBER(10)`` is ``NUMBER(10, 0)``.  Writing the server's own
    # values out is what makes a bare declaration equal to what the catalog
    # reports; the storage is the same column either way.
    (SnowflakeVarcharType, {}, "VARCHAR(16777216)", (16777216,)),
    (SnowflakeVarcharType, {"length": 100}, "VARCHAR(100)", (100,)),
    (SnowflakeVarcharType, {"length": 255}, "VARCHAR(255)", (255,)),
    # ``unsigned`` is in the identity of both, appended after ``precision`` and
    # ``scale`` in core's order, so every signed snapshot below carries a trailing
    # ``False``.  It is *refused* rather than rendered
    # (``_refuse_unsigned_numeric``), so no ``expected_sql`` in this matrix has an
    # unsigned form: Snowflake's numeric inventory has no unsigned row and its
    # column grammar has no modifier after ``<col_type>``.  See
    # ``test_snowflake_type_protocol.py::TestNumericSignedness``.
    (SnowflakeNumberType, {}, "NUMBER(38, 0)", (38, 0, False)),
    (SnowflakeNumberType, {"precision": 10}, "NUMBER(10, 0)", (10, 0, False)),
    (SnowflakeNumberType, {"precision": 10, "scale": 2},
     "NUMBER(10, 2)", (10, 2, False)),
    (SnowflakeFloatType, {}, "FLOAT", (None, False)),
    (SnowflakeFloatType, {"precision": 53}, "FLOAT(53)", (53, False)),
    (SnowflakeBooleanType, {}, "BOOLEAN", ()),
    (SnowflakeTimestampLtzType, {}, "TIMESTAMP_LTZ", (None,)),
    (SnowflakeTimestampLtzType, {"precision": 3}, "TIMESTAMP_LTZ(3)", (3,)),
    (SnowflakeTimestampNtzType, {}, "TIMESTAMP_NTZ", (None,)),
    (SnowflakeTimestampNtzType, {"precision": 6}, "TIMESTAMP_NTZ(6)", (6,)),
    (SnowflakeTimestampTzType, {}, "TIMESTAMP_TZ", (None,)),
    (SnowflakeTimestampTzType, {"precision": 9}, "TIMESTAMP_TZ(9)", (9,)),
    (SnowflakeDateType, {}, "DATE", ()),
    (SnowflakeTimeType, {}, "TIME", (None,)),
    (SnowflakeTimeType, {"precision": 3}, "TIME(3)", (3,)),
    (SnowflakeBinaryType, {}, "BINARY", (None,)),
    (SnowflakeBinaryType, {"length": 512}, "BINARY(512)", (512,)),
    (SnowflakeVariantType, {}, "VARIANT", ()),
    (SnowflakeObjectType, {}, "OBJECT", ()),
    (SnowflakeArrayType, {}, "ARRAY", None),
    (SnowflakeGeographyType, {}, "GEOGRAPHY", ()),
    (SnowflakeGeometryType, {}, "GEOMETRY", ()),
]

# ``snowflake_user_defined`` renders a qualified name and is version-gated, so it
# is snapshot separately rather than through the shared matrix.
UDT_MATRIX = [
    ({"type_name": "my_type"}, '"my_type"'),
    ({"type_name": "t", "schema_name": "s"}, '"s"."t"'),
    (
        {"type_name": "t", "schema_name": "s", "database_name": "db"},
        '"db"."s"."t"',
    ),
]

# ``snowflake_uuid`` is version-gated too — the native ``UUID`` arrived in server
# release 10.2 — so it is snapshotted on a dialect that claims to have it.  There
# is no pre-refactor rendering to compare against here: this type is new, and the
# word is the whole of Snowflake's documented grammar for it
# (``<column_name> UUID``).
# https://docs.snowflake.com/en/sql-reference/data-types-uuid
UUID_MATRIX = [
    ({}, "UUID"),
]


class TestRenderedSqlIsUnchanged:
    """This refactor is structural; not one byte of SQL may move."""

    def setup_method(self):
        self.dialect = SnowflakeDialect()

    @pytest.mark.parametrize(
        "cls,kwargs,expected_sql,expected_params",
        TYPE_MATRIX,
        ids=[f"{c.__name__}-{sorted(k)}" for c, k, _, _ in TYPE_MATRIX],
    )
    def test_sql_matches_the_pre_refactor_snapshot(
        self, cls, kwargs, expected_sql, expected_params
    ):
        sql, _ = self.dialect.format_data_type(cls(self.dialect, **kwargs))
        assert sql == expected_sql

    @pytest.mark.parametrize("kwargs,expected_sql", UDT_MATRIX,
                             ids=[str(sorted(k)) for k, _ in UDT_MATRIX])
    def test_user_defined_sql_is_unchanged(self, kwargs, expected_sql):
        # 10.8 is where CREATE TYPE — and therefore any reference to one — exists.
        dialect = SnowflakeDialect(version=(10, 8, 0))
        sql, _ = dialect.format_data_type(
            SnowflakeUserDefinedType(dialect, **kwargs)
        )
        assert sql == expected_sql

    @pytest.mark.parametrize("kwargs,expected_sql", UUID_MATRIX,
                             ids=[str(sorted(k)) for k, _ in UUID_MATRIX])
    def test_uuid_sql(self, kwargs, expected_sql):
        # 10.2 is where the native UUID arrived.
        dialect = SnowflakeDialect(version=(10, 2, 0))
        sql, _ = dialect.format_data_type(SnowflakeUuidType(dialect, **kwargs))
        assert sql == expected_sql

    def test_every_type_in_the_matrix_is_covered(self):
        """A snapshot that quietly stops covering a type proves nothing."""
        covered = {cls for cls, _, _, _ in TYPE_MATRIX} | {SnowflakeUuidType}
        from rhosocial.activerecord.backend.impl.snowflake.expression import (
            types as t,
        )

        declared = {
            value
            for value in vars(t).values()
            if isinstance(value, type)
            and value.__module__ == t.__name__
            and value.name.startswith("snowflake_")
        }
        assert declared - covered == {SnowflakeUserDefinedType}


class TestTypeParamsUnchanged:
    """Deleting a redundant identity declaration must not change equality.

    ``PARAMETERS`` feeds both ``__eq__`` and ``__hash__``, so getting this
    wrong would silently make two identical columns compare unequal.  The
    tuples are the declared identity, and hash equality is checked *within* a
    run (Python randomises string hashing per process, so absolute hash values
    are not stable and must not be asserted).

    These tuples deliberately carry **no spelling**. A spelling is a rendering
    choice, not part of the value: the same column introspects as
    ``character varying(30)`` whichever word created it, so counting it would
    make every introspected type unequal to its own declaration.  The declared
    word is asserted through ``expected_sql`` in the same matrix instead.
    """

    def setup_method(self):
        self.dialect = SnowflakeDialect()

    @pytest.mark.parametrize(
        "cls,kwargs,expected_sql,expected_params",
        TYPE_MATRIX,
        ids=[f"{c.__name__}-{sorted(k)}" for c, k, _, _ in TYPE_MATRIX],
    )
    def test_type_params_match_the_pre_refactor_snapshot(
        self, cls, kwargs, expected_sql, expected_params
    ):
        if expected_params is None:
            pytest.skip("SnowflakeArrayType compares element types, not params")
        instance = cls(self.dialect, **kwargs)
        assert instance.identity() == expected_params

    @pytest.mark.parametrize(
        "cls,kwargs,expected_sql,expected_params",
        TYPE_MATRIX,
        ids=[f"{c.__name__}-{sorted(k)}" for c, k, _, _ in TYPE_MATRIX],
    )
    def test_two_instances_with_the_same_params_are_equal_and_hash_equal(
        self, cls, kwargs, expected_sql, expected_params
    ):
        a = cls(self.dialect, **kwargs)
        b = cls(self.dialect, **kwargs)
        assert a == b, f"{cls.__name__}({kwargs}) no longer equals itself"
        assert hash(a) == hash(b)

    @pytest.mark.parametrize(
        "cls,kwargs,expected_sql,expected_params",
        TYPE_MATRIX,
        ids=[f"{c.__name__}-{sorted(k)}" for c, k, _, _ in TYPE_MATRIX],
    )
    def test_a_different_dialect_does_not_affect_equality(
        self, cls, kwargs, expected_sql, expected_params
    ):
        """A DataType is a value object: the dialect is not part of its identity.

        Worth keeping explicit because the re-parenting moved these classes one
        level further from ``DataType``, and a copy of ``__eq__`` appearing
        anywhere in the chain would reintroduce the dialect into comparison.
        """
        a = cls(self.dialect, **kwargs)
        b = cls(SnowflakeDialect(), **kwargs)
        assert a == b
        assert hash(a) == hash(b)


class TestDistinctParamsAreUnequal:
    """The converse: parameters that differ must still produce distinct types.

    A snapshot of the equal cases alone would pass even if ``PARAMETERS``
    returned a constant, so the differing cases are asserted too.
    """

    def setup_method(self):
        self.dialect = SnowflakeDialect()

    def test_varchar_lengths_differ(self):
        assert SnowflakeVarcharType(self.dialect, length=100) != SnowflakeVarcharType(
            self.dialect, length=200
        )

    def test_number_precision_and_scale_differ(self):
        assert SnowflakeNumberType(
            self.dialect, precision=10, scale=2
        ) != SnowflakeNumberType(self.dialect, precision=10, scale=3)
        assert SnowflakeNumberType(
            self.dialect, precision=10
        ) != SnowflakeNumberType(self.dialect, precision=11)

    def test_a_precisionless_number_is_the_documented_default_pair(self):
        """``NUMBER`` **is** ``NUMBER(38, 0)`` on this server, so they are equal.

        "By default, precision is 38, and scale is 0; that is, NUMBER(38, 0)",
        and ``DESC TABLE`` renders both spellings identically.  Core resolves
        the dialect's declared pair onto the bare type, which is what makes the
        declaration and the catalog's explicit pair one value object.  This is
        not a general conflation of "absent" with "zero": a dialect that
        declares no default keeps the two distinct, which is what the stub
        dialects in core's declared-parameter suite pin.
        """
        assert SnowflakeNumberType(self.dialect) == SnowflakeNumberType(
            self.dialect, precision=38, scale=0
        )
        # ...and a different scale is still a different column.
        assert SnowflakeNumberType(self.dialect) != SnowflakeNumberType(
            self.dialect, precision=38, scale=2
        )

    def test_float_precisions_differ(self):
        assert SnowflakeFloatType(
            self.dialect, precision=53
        ) != SnowflakeFloatType(self.dialect, precision=24)

    def test_timestamp_precisions_differ(self):
        for cls in (
            SnowflakeTimestampLtzType,
            SnowflakeTimestampNtzType,
            SnowflakeTimestampTzType,
        ):
            assert cls(self.dialect, precision=3) != cls(self.dialect, precision=6)

    def test_the_three_timestamp_flavours_are_three_types(self):
        """Same value, different behaviour — LTZ converts to the session zone,
        NTZ never does, TZ keeps the offset.  Equal columns would make the
        differ blind to a real semantic change."""
        assert SnowflakeTimestampLtzType(
            self.dialect
        ) != SnowflakeTimestampNtzType(self.dialect)
        assert SnowflakeTimestampNtzType(
            self.dialect
        ) != SnowflakeTimestampTzType(self.dialect)
        assert SnowflakeTimestampLtzType(
            self.dialect
        ) != SnowflakeTimestampTzType(self.dialect)

    def test_binary_lengths_differ(self):
        assert SnowflakeBinaryType(
            self.dialect, length=512
        ) != SnowflakeBinaryType(self.dialect, length=1024)
        assert SnowflakeBinaryType(self.dialect) != SnowflakeBinaryType(
            self.dialect, length=1024
        )

    def test_time_precisions_differ(self):
        assert SnowflakeTimeType(self.dialect, precision=3) != SnowflakeTimeType(
            self.dialect, precision=6
        )

    def test_distinct_classes_are_never_equal(self):
        instances = [
            cls(self.dialect, **kwargs)
            for cls, kwargs, _, _ in TYPE_MATRIX
            if cls is not SnowflakeArrayType
        ]
        for i, a in enumerate(instances):
            for b in instances[i + 1:]:
                if type(a) is not type(b):
                    assert a != b, f"{type(a).__name__} == {type(b).__name__}"


class TestArrayEqualityIsElementBased:
    """``SnowflakeArrayType`` is the one class that compares deliberately.

    It does not use the base ``__eq__``: an array is equal when it stores the
    same kind of thing, so the element *type* is compared rather than the
    element instance, and ``dimensions`` is ignored because Snowflake's ARRAY
    has no such axis.
    """

    def setup_method(self):
        self.dialect = SnowflakeDialect()

    def test_same_element_type_is_equal(self):
        from rhosocial.activerecord.backend.expression.types import (
            IntegerType,
            VarCharType,
        )

        a = SnowflakeArrayType(self.dialect, element_type=IntegerType())
        b = SnowflakeArrayType(self.dialect, element_type=IntegerType())
        assert a == b
        assert hash(a) == hash(b)

    def test_different_element_type_is_not_equal(self):
        from rhosocial.activerecord.backend.expression.types import (
            IntegerType,
            VarCharType,
        )

        a = SnowflakeArrayType(self.dialect, element_type=IntegerType())
        b = SnowflakeArrayType(self.dialect, element_type=VarCharType())
        assert a != b

    def test_element_type_defaults_to_integer(self):
        from rhosocial.activerecord.backend.expression.types import IntegerType

        assert SnowflakeArrayType(self.dialect).element_type == IntegerType()

    def test_is_not_equal_to_a_plain_json_type(self):
        """It is an array, not a document, despite sharing a base with the
        semi-structured types — sharing a base must not mean equal."""
        from rhosocial.activerecord.backend.expression.types import JsonType

        assert SnowflakeArrayType(self.dialect) != JsonType(self.dialect)
        assert SnowflakeVariantType(self.dialect) != SnowflakeObjectType(
            self.dialect
        )
