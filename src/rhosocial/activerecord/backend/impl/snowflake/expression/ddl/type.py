"""Snowflake schema-level user-defined type DDL expressions."""

from collections.abc import Mapping as ABCMapping
from typing import Any, Optional, Sequence, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.serialization import ExpressionRegistry
from rhosocial.activerecord.backend.expression.statements.ddl_type import (
    AlterTypeExpression,
    CreateTypeExpression,
    DropTypeExpression,
    TypeAlterAction,
    TypeDefinition,
)
from rhosocial.activerecord.backend.expression.types import DataType

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


def _validate_name(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_optional_name(value: Optional[str], field_name: str) -> None:
    if value is not None:
        _validate_name(value, field_name)


def _validate_database_qualification(
    database_name: Optional[str],
    schema_name: Optional[str],
) -> None:
    _validate_optional_name(database_name, "database_name")
    if database_name is not None and schema_name is None:
        raise ValueError("schema_name is required when database_name is provided")


class SnowflakeTypeField(BaseExpression):
    """One field in a Snowflake structured OBJECT type definition."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        data_type: DataType,
    ) -> None:
        super().__init__(dialect)
        _validate_name(name, "field name")
        if not isinstance(data_type, DataType):
            raise TypeError(f"field data_type must be a DataType instance, got {type(data_type).__name__}")
        self.name = name
        self.data_type = data_type

    @property
    def format_method(self) -> str:
        return "format_snowflake_type_field"


def _coerce_type_field(
    value: Any,
    dialect: "SQLDialectBase",
) -> SnowflakeTypeField:
    if isinstance(value, SnowflakeTypeField):
        return value
    if isinstance(value, ABCMapping):
        if "name" in value and "data_type" in value:
            if len(value) != 2:
                raise ValueError("field mapping must contain only name and data_type")
            return SnowflakeTypeField(dialect, value["name"], value["data_type"])
        if len(value) != 1:
            raise ValueError("field mapping must contain one name and data_type pair")
        name, data_type = next(iter(value.items()))
        return SnowflakeTypeField(dialect, name, data_type)
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return SnowflakeTypeField(dialect, value[0], value[1])
    raise TypeError(
        f"fields must contain SnowflakeTypeField, mapping, or (name, data_type) pairs, got {type(value).__name__}"
    )


class SnowflakeScalarTypeDefinition(TypeDefinition):
    """Scalar UDT definition based on an existing Snowflake data type."""

    definition_kind = "snowflake.scalar"

    def __init__(
        self,
        dialect: "SQLDialectBase",
        data_type: DataType,
    ) -> None:
        super().__init__(dialect)
        if not isinstance(data_type, DataType):
            raise TypeError(f"data_type must be a DataType instance, got {type(data_type).__name__}")
        self.data_type = data_type


class SnowflakeObjectTypeDefinition(TypeDefinition):
    """Structured UDT definition based on OBJECT fields."""

    definition_kind = "snowflake.object"

    def __init__(
        self,
        dialect: "SQLDialectBase",
        fields: Any,
    ) -> None:
        super().__init__(dialect)
        if isinstance(fields, ABCMapping) and not ("name" in fields and "data_type" in fields):
            raw_fields: Any = [{name: data_type} for name, data_type in fields.items()]
        else:
            raw_fields = fields
        if raw_fields is None:
            raw_fields = []
        try:
            field_values = list(raw_fields)
        except TypeError as exc:
            raise TypeError(
                f"fields must be a sequence of Snowflake OBJECT type fields, got {type(fields).__name__}"
            ) from exc
        if not field_values:
            raise ValueError("Snowflake OBJECT type definitions require at least one field")
        coerced_fields = [_coerce_type_field(value, dialect) for value in field_values]
        names = [field.name for field in coerced_fields]
        if len(names) != len(set(names)):
            raise ValueError("Snowflake OBJECT type field names must be unique")
        self.fields = coerced_fields


class SnowflakeSetTypeCommentAction(TypeAlterAction):
    """SET COMMENT action for an existing Snowflake UDT."""

    action_kind = "snowflake.set_type_comment"

    def __init__(
        self,
        dialect: "SQLDialectBase",
        comment: str,
    ) -> None:
        super().__init__(dialect)
        if not isinstance(comment, str):
            raise TypeError("comment must be a string")
        self.comment = comment


class SnowflakeUnsetTypeCommentAction(TypeAlterAction):
    """UNSET COMMENT action for an existing Snowflake UDT."""

    action_kind = "snowflake.unset_type_comment"


class SnowflakeCreateTypeExpression(CreateTypeExpression):
    """CREATE TYPE expression with Snowflake qualification and comment syntax."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        type_name: str,
        definition: TypeDefinition,
        *,
        database_name: Optional[str] = None,
        schema_name: Optional[str] = None,
        if_not_exists: bool = False,
        or_replace: bool = False,
        comment: Optional[str] = None,
    ) -> None:
        _validate_database_qualification(database_name, schema_name)
        if comment is not None and not isinstance(comment, str):
            raise TypeError("comment must be a string or None")
        super().__init__(
            dialect,
            type_name,
            definition,
            schema_name=schema_name,
            if_not_exists=if_not_exists,
            or_replace=or_replace,
        )
        self.database_name = database_name
        self.comment = comment


class SnowflakeAlterTypeExpression(AlterTypeExpression):
    """ALTER TYPE expression with Snowflake database/schema qualification."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        type_name: str,
        actions: Sequence[TypeAlterAction],
        *,
        database_name: Optional[str] = None,
        schema_name: Optional[str] = None,
        if_exists: bool = False,
    ) -> None:
        _validate_database_qualification(database_name, schema_name)
        super().__init__(
            dialect,
            type_name,
            actions,
            schema_name=schema_name,
            if_exists=if_exists,
        )
        self.database_name = database_name


class SnowflakeDropTypeExpression(DropTypeExpression):
    """DROP TYPE expression with Snowflake database/schema qualification."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        type_name: str,
        *,
        database_name: Optional[str] = None,
        schema_name: Optional[str] = None,
        if_exists: bool = False,
        cascade: bool = False,
        restrict: bool = False,
    ) -> None:
        _validate_database_qualification(database_name, schema_name)
        if not isinstance(cascade, bool):
            raise TypeError("cascade must be a bool")
        if not isinstance(restrict, bool):
            raise TypeError("restrict must be a bool")
        if cascade:
            raise UnsupportedFeatureError(
                dialect.name,
                "DROP TYPE CASCADE",
                suggestion="Snowflake DROP TYPE does not support CASCADE.",
            )
        if restrict:
            raise UnsupportedFeatureError(
                dialect.name,
                "DROP TYPE RESTRICT",
                suggestion="Snowflake DROP TYPE does not support RESTRICT.",
            )
        super().__init__(
            dialect,
            type_name,
            schema_name=schema_name,
            if_exists=if_exists,
        )
        self.database_name = database_name
        self.cascade = False
        self.restrict = False


_EXPRESSION_TYPES = (
    SnowflakeTypeField,
    SnowflakeScalarTypeDefinition,
    SnowflakeObjectTypeDefinition,
    SnowflakeSetTypeCommentAction,
    SnowflakeUnsetTypeCommentAction,
    SnowflakeCreateTypeExpression,
    SnowflakeAlterTypeExpression,
    SnowflakeDropTypeExpression,
)
for _expression_type in _EXPRESSION_TYPES:
    ExpressionRegistry.register(_expression_type)


__all__ = [
    "SnowflakeTypeField",
    "SnowflakeScalarTypeDefinition",
    "SnowflakeObjectTypeDefinition",
    "SnowflakeSetTypeCommentAction",
    "SnowflakeUnsetTypeCommentAction",
    "SnowflakeCreateTypeExpression",
    "SnowflakeAlterTypeExpression",
    "SnowflakeDropTypeExpression",
]
