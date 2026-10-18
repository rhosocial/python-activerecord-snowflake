"""Snowflake schema-level user-defined TYPE DDL unit tests."""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.protocols import (
    AlterTypeSupport,
    CreateTypeSupport,
    DropTypeSupport,
    TypeObjectSupport,
)
from rhosocial.activerecord.backend.expression.objects import Type
from rhosocial.activerecord.backend.expression.serialization import (
    default_registry,
    deserialize,
    deserialize_json,
    deserialize_xml,
    serialize,
    serialize_json,
    serialize_xml,
)
from rhosocial.activerecord.backend.expression.statements.ddl_type import (
    AlterTypeStatement,
    CreateTypeStatement,
    DropTypeStatement,
    TypeAlterAction,
    TypeDefinition,
)
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeAlterTypeExpression,
    SnowflakeCreateTypeExpression,
    SnowflakeDropTypeExpression,
    SnowflakeObjectTypeDefinition,
    SnowflakeScalarTypeDefinition,
    SnowflakeSetTypeCommentAction,
    SnowflakeTypeField,
    SnowflakeUnsetTypeCommentAction,
    SnowflakeUserDefinedType,
)
from rhosocial.activerecord.backend.impl.snowflake.mixins import SnowflakeTypeDDLMixin
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
    SnowflakeVariantType,
    SnowflakeVarcharType,
)


def _dialect(version=(10, 8, 0)):
    return SnowflakeDialect(version=version)


#: Every expression class this backend's type DDL defines. Deserialising one
#: of these kinds needs it in the registry the read goes through, and the
#: framework's default registry holds only the packages the framework itself
#: ships -- nothing registers this backend's classes on import any more. This
#: file is the reader, so it assembles the classes it round-trips into that
#: registry once; the resolution test below then pins the assembly.
_SNOWFLAKE_TYPE_EXPRESSIONS = (
    SnowflakeVarcharType,
    SnowflakeNumberType,
    SnowflakeFloatType,
    SnowflakeBooleanType,
    SnowflakeTimestampLtzType,
    SnowflakeTimestampNtzType,
    SnowflakeTimestampTzType,
    SnowflakeDateType,
    SnowflakeTimeType,
    SnowflakeBinaryType,
    SnowflakeVariantType,
    SnowflakeObjectType,
    SnowflakeArrayType,
    SnowflakeGeographyType,
    SnowflakeGeometryType,
    SnowflakeUserDefinedType,
    SnowflakeTypeField,
    SnowflakeScalarTypeDefinition,
    SnowflakeObjectTypeDefinition,
    SnowflakeSetTypeCommentAction,
    SnowflakeUnsetTypeCommentAction,
    SnowflakeCreateTypeExpression,
    SnowflakeAlterTypeExpression,
    SnowflakeDropTypeExpression,
)

for _cls in _SNOWFLAKE_TYPE_EXPRESSIONS:
    default_registry().register_node(_cls)


def _snowflake_data_types(dialect):
    return (
        SnowflakeVarcharType(dialect, length=64),
        SnowflakeNumberType(dialect, precision=12, scale=2),
        SnowflakeFloatType(dialect, precision=53),
        SnowflakeBooleanType(dialect),
        SnowflakeTimestampLtzType(dialect, precision=3),
        SnowflakeTimestampNtzType(dialect, precision=6),
        SnowflakeTimestampTzType(dialect, precision=9),
        SnowflakeDateType(dialect),
        SnowflakeTimeType(dialect, precision=3),
        SnowflakeBinaryType(dialect, length=1024),
        SnowflakeVariantType(dialect),
        SnowflakeObjectType(dialect),
        SnowflakeArrayType(
            dialect,
            element_type=SnowflakeVarcharType(dialect, length=32),
        ),
        SnowflakeGeographyType(dialect),
        SnowflakeGeometryType(dialect),
        SnowflakeUserDefinedType(
            dialect,
            database_name="DB",
            schema_name="APP",
            type_name="label_type",
        ),
    )


def test_capabilities_protocol_and_mro():
    dialect = _dialect()

    assert dialect.supports_type_objects() is True
    assert dialect.supports_create_type() is True
    assert dialect.supports_alter_type() is True
    assert dialect.supports_drop_type() is True
    assert dialect.supports_create_type_if_not_exists() is True
    assert dialect.supports_create_type_or_replace() is True
    assert dialect.supports_alter_type_if_exists() is True
    assert dialect.supports_drop_type_if_exists() is False
    assert dialect.supports_multiple_type_alter_actions() is False
    assert dialect.supported_type_definitions() == (
        SnowflakeScalarTypeDefinition,
        SnowflakeObjectTypeDefinition,
    )
    # Naming the type is one protocol; declaring it is one per statement.
    assert isinstance(dialect, TypeObjectSupport)
    assert isinstance(dialect, CreateTypeSupport)
    assert isinstance(dialect, AlterTypeSupport)
    assert isinstance(dialect, DropTypeSupport)
    assert SnowflakeDialect.format_type_definition is SnowflakeTypeDDLMixin.format_type_definition

    mro = SnowflakeDialect.__mro__
    assert mro.index(SnowflakeTypeDDLMixin) < mro.index(CreateTypeSupport)


def test_version_boundary_and_low_version_fail_fast():
    dialect = _dialect((10, 7, 99))
    scalar = SnowflakeScalarTypeDefinition(
        dialect,
        SnowflakeNumberType(dialect, precision=3, scale=0),
    )
    object_definition = SnowflakeObjectTypeDefinition(
        dialect,
        {"street": SnowflakeVarcharType(dialect, length=100)},
    )
    field = SnowflakeTypeField(
        dialect,
        "street",
        SnowflakeVarcharType(dialect, length=100),
    )
    set_action = SnowflakeSetTypeCommentAction(dialect, "comment")
    reference = SnowflakeUserDefinedType(dialect, type_name="age")
    statements = [
        CreateTypeStatement(dialect, Type(dialect, "age"), scalar),
        AlterTypeStatement(dialect, Type(dialect, "age"), [set_action]),
        DropTypeStatement(dialect, Type(dialect, "age")),
    ]

    assert dialect.supports_type_objects() is False
    assert dialect.supports_create_type() is False
    assert dialect.supports_alter_type() is False
    assert dialect.supports_drop_type() is False
    assert dialect.supported_type_definitions() == ()
    assert dialect.supports_data_type_snowflake_user_defined() is False

    for expression in [
        scalar,
        object_definition,
        field,
        set_action,
        reference,
        *statements,
    ]:
        with pytest.raises(UnsupportedFeatureError):
            expression.to_sql()


def test_scalar_create_type_renders_schema_qualification():
    dialect = _dialect()
    definition = SnowflakeScalarTypeDefinition(
        dialect,
        SnowflakeNumberType(dialect, precision=3, scale=0),
    )

    expression = CreateTypeStatement(
        dialect,
        Type(dialect, "age", schema_name="app"),
        definition,
    )

    assert definition.to_sql() == ("AS NUMBER(3, 0)", ())
    assert expression.to_sql() == (
        'CREATE TYPE "app"."age" AS NUMBER(3, 0)',
        (),
    )


def test_create_options_are_rendered_in_snowflake_order():
    dialect = _dialect()
    definition = SnowflakeScalarTypeDefinition(
        dialect,
        # A bare ``SnowflakeVarcharType`` carries Snowflake's documented default
        # width of 16777216, so the type it renders as is ``VARCHAR(16777216)``.
        # The options ordering is what this test is about; the width follows from
        # ``type_parameter_defaults()``.
        SnowflakeVarcharType(dialect),
    )

    replace = SnowflakeCreateTypeExpression(
        dialect,
        Type(dialect, "label"),
        definition,
        or_replace=True,
    )
    create_if_missing = SnowflakeCreateTypeExpression(
        dialect,
        Type(dialect, "label"),
        definition,
        if_not_exists=True,
    )

    assert replace.to_sql() == (
        'CREATE OR REPLACE TYPE "label" AS VARCHAR(16777216)',
        (),
    )
    assert create_if_missing.to_sql() == (
        'CREATE TYPE IF NOT EXISTS "label" AS VARCHAR(16777216)',
        (),
    )
    with pytest.raises(ValueError, match="mutually exclusive"):
        SnowflakeCreateTypeExpression(
            dialect,
            Type(dialect, "label"),
            definition,
            if_not_exists=True,
            or_replace=True,
        )


def test_create_type_qualification_and_comment_are_safely_quoted():
    dialect = _dialect()
    definition = SnowflakeScalarTypeDefinition(
        dialect,
        SnowflakeNumberType(dialect, precision=3, scale=0),
    )
    expression = SnowflakeCreateTypeExpression(
        dialect,
        Type(
            dialect,
            "age type",
            catalog_name='DB"name',
            schema_name='S"chema',
        ),
        definition,
        comment="owner's type",
    )

    assert expression.to_sql() == (
        'CREATE TYPE "DB""name"."S""chema"."age type" AS NUMBER(3, 0) COMMENT = \'owner\'\'s type\'',
        (),
    )


def test_object_type_definition_renders_typed_object_fields():
    dialect = _dialect()
    definition = SnowflakeObjectTypeDefinition(
        dialect,
        {
            "street": SnowflakeVarcharType(dialect, length=100),
            "segments": SnowflakeArrayType(dialect),
        },
    )
    expression = SnowflakeCreateTypeExpression(
        dialect,
        Type(dialect, "address", catalog_name="DB", schema_name="APP"),
        definition,
    )

    assert definition.to_sql() == (
        'AS OBJECT("street" VARCHAR(100), "segments" ARRAY)',
        (),
    )
    assert expression.to_sql() == (
        'CREATE TYPE "DB"."APP"."address" AS OBJECT("street" VARCHAR(100), "segments" ARRAY)',
        (),
    )


def test_object_type_field_validation_and_type_kind_separation():
    dialect = _dialect()
    data_type = SnowflakeVarcharType(dialect, length=20)

    with pytest.raises(ValueError, match="at least one field"):
        SnowflakeObjectTypeDefinition(dialect, [])
    with pytest.raises(ValueError, match="unique"):
        SnowflakeObjectTypeDefinition(
            dialect,
            [("name", data_type), {"name": data_type}],
        )
    with pytest.raises(TypeError, match="DataType"):
        SnowflakeObjectTypeDefinition(dialect, [("name", object())])

    assert isinstance(SnowflakeObjectType(dialect), TypeDefinition) is False
    assert isinstance(SnowflakeArrayType(dialect), TypeDefinition) is False
    assert isinstance(SnowflakeObjectTypeDefinition(dialect, [("name", data_type)]), TypeDefinition)


def test_scalar_udt_rejects_another_udt_as_base_type():
    dialect = _dialect()
    reference = SnowflakeUserDefinedType(
        dialect,
        type_name="age",
        database_name="DB",
        schema_name="APP",
    )
    definition = SnowflakeScalarTypeDefinition(dialect, reference)

    assert reference.to_sql() == (
        '"DB"."APP"."age"',
        (),
    )
    with pytest.raises(UnsupportedFeatureError, match="another UDT"):
        definition.to_sql()


def test_alter_type_set_and_unset_comment_actions():
    dialect = _dialect()
    set_action = SnowflakeSetTypeCommentAction(dialect, "owner's type")
    set_expression = SnowflakeAlterTypeExpression(
        dialect,
        Type(dialect, "age", catalog_name="DB", schema_name="APP"),
        [set_action],
        if_exists=True,
    )
    unset_expression = AlterTypeStatement(
        dialect,
        Type(dialect, "age", schema_name="APP"),
        [SnowflakeUnsetTypeCommentAction(dialect)],
    )

    assert set_expression.to_sql() == (
        'ALTER TYPE IF EXISTS "DB"."APP"."age" SET COMMENT = \'owner\'\'s type\'',
        (),
    )
    assert unset_expression.to_sql() == (
        'ALTER TYPE "APP"."age" UNSET COMMENT',
        (),
    )


def test_alter_type_rejects_multiple_or_unknown_actions():
    dialect = _dialect()

    expression = AlterTypeStatement(
        dialect,
        Type(dialect, "age"),
        [
            SnowflakeSetTypeCommentAction(dialect, "first"),
            SnowflakeUnsetTypeCommentAction(dialect),
        ],
    )
    with pytest.raises(UnsupportedFeatureError, match="multiple ALTER TYPE actions"):
        expression.to_sql()

    class UnsupportedAction(TypeAlterAction):
        """A well-formed action whose kind this dialect never registered."""

        action_kind = "test.unsupported"

    with pytest.raises(
        UnsupportedFeatureError, match=r"ALTER TYPE action test\.unsupported"
    ):
        dialect.format_type_alter_action(UnsupportedAction(dialect))

    # The kind is a declared field of the contract, read directly now: an
    # input that is not a TypeAlterAction at all surfaces the missing
    # attribute instead of the old probe's class-name fallback.
    with pytest.raises(AttributeError, match="action_kind"):
        dialect.format_type_alter_action(object())


def test_drop_type_has_no_if_exists_cascade_or_restrict():
    dialect = _dialect()
    expression = SnowflakeDropTypeExpression(
        dialect,
        Type(dialect, "age", catalog_name="DB", schema_name="APP"),
    )

    assert expression.to_sql() == (
        'DROP TYPE "DB"."APP"."age"',
        (),
    )

    with pytest.raises(UnsupportedFeatureError, match="IF EXISTS"):
        DropTypeStatement(dialect, Type(dialect, "age"), if_exists=True).to_sql()
    with pytest.raises(UnsupportedFeatureError, match="CASCADE"):
        SnowflakeDropTypeExpression(
            dialect, Type(dialect, "age"), cascade=True
        )
    with pytest.raises(UnsupportedFeatureError, match="RESTRICT"):
        SnowflakeDropTypeExpression(
            dialect, Type(dialect, "age"), restrict=True
        )

    expression.cascade = True
    with pytest.raises(UnsupportedFeatureError, match="CASCADE"):
        expression.to_sql()


def test_udt_expressions_resolve_through_the_readers_registry():
    """Every type-DDL class answers to its kind in the assembled registry.

    Deserialisation resolves a kind, never a dotted name, so what a reader
    gets back is decided by ``kind()`` -- derived from the class name -- and
    by the assembly at module import. A kind two classes claim would have
    raised there; this pins that each class's own kind resolves to the class
    itself.
    """
    registry = default_registry()
    for expression_type in _SNOWFLAKE_TYPE_EXPRESSIONS:
        assert registry.resolve_node(expression_type.kind()) is expression_type


def test_udt_expression_dict_json_and_xml_round_trips():
    dialect = _dialect()
    definition = SnowflakeObjectTypeDefinition(
        dialect,
        {"label": SnowflakeVarcharType(dialect, length=80)},
    )
    expression = SnowflakeCreateTypeExpression(
        dialect,
        Type(dialect, "label_type", catalog_name="DB", schema_name="APP"),
        definition,
        comment="round trip",
    )
    expected = expression.to_sql()

    restored = deserialize(serialize(expression), dialect)
    assert isinstance(restored, SnowflakeCreateTypeExpression)
    assert restored.to_sql() == expected

    restored = deserialize_json(serialize_json(expression), dialect)
    assert isinstance(restored, SnowflakeCreateTypeExpression)
    assert restored.to_sql() == expected

    restored = deserialize_xml(serialize_xml(expression), dialect)
    assert isinstance(restored, SnowflakeCreateTypeExpression)
    assert restored.to_sql() == expected


def test_all_nestable_snowflake_data_types_round_trip():
    dialect = _dialect()

    for original in _snowflake_data_types(dialect):
        expected = original.to_sql()

        restored = deserialize(serialize(original), dialect)
        assert type(restored) is type(original)
        assert restored.to_sql() == expected

        restored = deserialize_json(serialize_json(original), dialect)
        assert type(restored) is type(original)
        assert restored.to_sql() == expected

        restored = deserialize_xml(serialize_xml(original), dialect)
        assert type(restored) is type(original)
        assert restored.to_sql() == expected


def test_public_exports_include_udt_ddl_api():
    from rhosocial.activerecord.backend.impl.snowflake.expression import (
        SnowflakeUserDefinedType,
        SnowflakeTypeField,
        SnowflakeScalarTypeDefinition,
        SnowflakeObjectTypeDefinition,
        SnowflakeSetTypeCommentAction,
        SnowflakeUnsetTypeCommentAction,
        SnowflakeCreateTypeExpression,
        SnowflakeAlterTypeExpression,
        SnowflakeDropTypeExpression,
    )
    from rhosocial.activerecord.backend.impl.snowflake.mixins import SnowflakeTypeDDLMixin

    for cls in (
        SnowflakeUserDefinedType,
        SnowflakeTypeField,
        SnowflakeScalarTypeDefinition,
        SnowflakeObjectTypeDefinition,
        SnowflakeSetTypeCommentAction,
        SnowflakeUnsetTypeCommentAction,
        SnowflakeCreateTypeExpression,
        SnowflakeAlterTypeExpression,
        SnowflakeDropTypeExpression,
        SnowflakeTypeDDLMixin,
    ):
        assert isinstance(cls, type)
