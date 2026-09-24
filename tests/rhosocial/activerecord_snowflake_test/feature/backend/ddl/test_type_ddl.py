"""Snowflake schema-level user-defined TYPE DDL unit tests."""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.protocols import UserDefinedTypeSupport
from rhosocial.activerecord.backend.expression.serialization import (
    ExpressionRegistry,
    deserialize,
    deserialize_json,
    deserialize_xml,
    serialize,
    serialize_json,
    serialize_xml,
)
from rhosocial.activerecord.backend.expression.statements.ddl_type import (
    AlterTypeExpression,
    CreateTypeExpression,
    DropTypeExpression,
    TypeDefinition,
)
from rhosocial.activerecord.backend.impl.snowflake import (
    SnowflakeAlterTypeExpression,
    SnowflakeCreateTypeExpression,
    SnowflakeDropTypeExpression,
    SnowflakeObjectTypeDefinition,
    SnowflakeScalarTypeDefinition,
    SnowflakeSetTypeCommentAction,
    SnowflakeTypeDDLMixin,
    SnowflakeTypeField,
    SnowflakeUnsetTypeCommentAction,
    SnowflakeUserDefinedType,
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
    SnowflakeVariantType,
    SnowflakeVarcharType,
)


def _dialect(version=(10, 8, 0)):
    return SnowflakeDialect(version=version)


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
    assert isinstance(dialect, UserDefinedTypeSupport)
    assert SnowflakeDialect.format_type_definition is SnowflakeTypeDDLMixin.format_type_definition

    mro = SnowflakeDialect.__mro__
    assert mro.index(SnowflakeTypeDDLMixin) < mro.index(UserDefinedTypeSupport)


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
        CreateTypeExpression(dialect, "age", scalar),
        AlterTypeExpression(dialect, "age", [set_action]),
        DropTypeExpression(dialect, "age"),
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

    expression = CreateTypeExpression(
        dialect,
        "age",
        definition,
        schema_name="app",
    )

    assert definition.to_sql() == ("AS NUMBER(3, 0)", ())
    assert expression.to_sql() == ('CREATE TYPE "app"."age" AS NUMBER(3, 0)')


def test_create_options_are_rendered_in_snowflake_order():
    dialect = _dialect()
    definition = SnowflakeScalarTypeDefinition(
        dialect,
        SnowflakeVarcharType(dialect),
    )

    replace = SnowflakeCreateTypeExpression(
        dialect,
        "label",
        definition,
        or_replace=True,
    )
    create_if_missing = SnowflakeCreateTypeExpression(
        dialect,
        "label",
        definition,
        if_not_exists=True,
    )

    assert replace.to_sql() == 'CREATE OR REPLACE TYPE "label" AS VARCHAR'
    assert create_if_missing.to_sql() == 'CREATE TYPE IF NOT EXISTS "label" AS VARCHAR'
    with pytest.raises(ValueError, match="mutually exclusive"):
        SnowflakeCreateTypeExpression(
            dialect,
            "label",
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
        "age type",
        definition,
        database_name='DB"name',
        schema_name='S"chema',
        comment="owner's type",
    )

    assert expression.to_sql() == (
        'CREATE TYPE "DB""name"."S""chema"."age type" AS NUMBER(3, 0) COMMENT = \'owner\'\'s type\''
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
        "address",
        definition,
        database_name="DB",
        schema_name="APP",
    )

    assert definition.to_sql() == (
        'AS OBJECT("street" VARCHAR(100), "segments" ARRAY)',
        (),
    )
    assert expression.to_sql() == (
        'CREATE TYPE "DB"."APP"."address" AS OBJECT("street" VARCHAR(100), "segments" ARRAY)'
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

    assert reference.to_sql() == '"DB"."APP"."age"'
    with pytest.raises(UnsupportedFeatureError, match="another UDT"):
        definition.to_sql()


def test_alter_type_set_and_unset_comment_actions():
    dialect = _dialect()
    set_action = SnowflakeSetTypeCommentAction(dialect, "owner's type")
    set_expression = SnowflakeAlterTypeExpression(
        dialect,
        "age",
        [set_action],
        database_name="DB",
        schema_name="APP",
        if_exists=True,
    )
    unset_expression = AlterTypeExpression(
        dialect,
        "age",
        [SnowflakeUnsetTypeCommentAction(dialect)],
        schema_name="APP",
    )

    assert set_expression.to_sql() == ('ALTER TYPE IF EXISTS "DB"."APP"."age" SET COMMENT = \'owner\'\'s type\'')
    assert unset_expression.to_sql() == ('ALTER TYPE "APP"."age" UNSET COMMENT')


def test_alter_type_rejects_multiple_or_unknown_actions():
    dialect = _dialect()

    expression = AlterTypeExpression(
        dialect,
        "age",
        [
            SnowflakeSetTypeCommentAction(dialect, "first"),
            SnowflakeUnsetTypeCommentAction(dialect),
        ],
    )
    with pytest.raises(UnsupportedFeatureError, match="multiple ALTER TYPE actions"):
        expression.to_sql()
    with pytest.raises(UnsupportedFeatureError, match="ALTER TYPE action"):
        dialect.format_type_alter_action(object())


def test_drop_type_has_no_if_exists_cascade_or_restrict():
    dialect = _dialect()
    expression = SnowflakeDropTypeExpression(
        dialect,
        "age",
        database_name="DB",
        schema_name="APP",
    )

    assert expression.to_sql() == 'DROP TYPE "DB"."APP"."age"'

    with pytest.raises(UnsupportedFeatureError, match="IF EXISTS"):
        DropTypeExpression(dialect, "age", if_exists=True).to_sql()
    with pytest.raises(UnsupportedFeatureError, match="CASCADE"):
        SnowflakeDropTypeExpression(dialect, "age", cascade=True)
    with pytest.raises(UnsupportedFeatureError, match="RESTRICT"):
        SnowflakeDropTypeExpression(dialect, "age", restrict=True)

    expression.cascade = True
    with pytest.raises(UnsupportedFeatureError, match="CASCADE"):
        expression.to_sql()


def test_udt_expressions_are_explicitly_registered_for_serialization():
    expression_types = (
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

    for expression_type in expression_types:
        fqn = f"{expression_type.__module__}.{expression_type.__name__}"
        assert ExpressionRegistry.lookup(fqn) is expression_type


def test_udt_expression_dict_json_and_xml_round_trips():
    dialect = _dialect()
    definition = SnowflakeObjectTypeDefinition(
        dialect,
        {"label": SnowflakeVarcharType(dialect, length=80)},
    )
    expression = SnowflakeCreateTypeExpression(
        dialect,
        "label_type",
        definition,
        database_name="DB",
        schema_name="APP",
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
    import rhosocial.activerecord.backend.impl.snowflake as snowflake

    for name in (
        "SnowflakeUserDefinedType",
        "SnowflakeTypeField",
        "SnowflakeScalarTypeDefinition",
        "SnowflakeObjectTypeDefinition",
        "SnowflakeSetTypeCommentAction",
        "SnowflakeUnsetTypeCommentAction",
        "SnowflakeCreateTypeExpression",
        "SnowflakeAlterTypeExpression",
        "SnowflakeDropTypeExpression",
        "SnowflakeTypeDDLMixin",
    ):
        assert hasattr(snowflake, name)
