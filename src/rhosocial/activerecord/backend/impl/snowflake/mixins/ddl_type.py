"""Snowflake schema-level user-defined type DDL capability and SQL formatting."""

from typing import Any, Tuple, Type, cast

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.user_defined_type import UserDefinedTypeMixin
from rhosocial.activerecord.backend.expression.statements.ddl_type import (
    AlterTypeExpression,
    CreateTypeExpression,
    DropTypeExpression,
    TypeAlterAction,
    TypeDefinition,
)

from ..expression.ddl.type import (
    SnowflakeObjectTypeDefinition,
    SnowflakeScalarTypeDefinition,
    SnowflakeSetTypeCommentAction,
    SnowflakeTypeField,
    SnowflakeUnsetTypeCommentAction,
)
from ..expression.types import SnowflakeUserDefinedType


SNOWFLAKE_TYPE_DDL_MIN_VERSION = (10, 8, 0)


class SnowflakeTypeDDLMixin(UserDefinedTypeMixin):
    """Snowflake UDT capability gates and TYPE DDL formatters."""

    _TYPE_DEFINITION_TYPES = (
        SnowflakeScalarTypeDefinition,
        SnowflakeObjectTypeDefinition,
    )
    _TYPE_ACTION_TYPES = (
        SnowflakeSetTypeCommentAction,
        SnowflakeUnsetTypeCommentAction,
    )

    def _has_type_support(self) -> bool:
        version = getattr(self, "version", None)
        if version is None:
            return False
        try:
            return tuple(version) >= SNOWFLAKE_TYPE_DDL_MIN_VERSION
        except TypeError:
            return False

    def _require_type_support(self, feature_name: str) -> None:
        if not self._has_type_support():
            raise UnsupportedFeatureError(
                self.name,
                feature_name,
                suggestion="Snowflake schema-level TYPE DDL requires server version 10.8 or newer.",
            )

    def supports_type_objects(self) -> bool:
        return self._has_type_support()

    def supports_create_type(self) -> bool:
        return self._has_type_support()

    def supports_alter_type(self) -> bool:
        return self._has_type_support()

    def supports_drop_type(self) -> bool:
        return self._has_type_support()

    def supported_type_definitions(self) -> Tuple[Type[TypeDefinition], ...]:
        if not self._has_type_support():
            return ()
        return self._TYPE_DEFINITION_TYPES

    def supports_type_definition(
        self,
        definition_type: Type[TypeDefinition],
    ) -> bool:
        try:
            return self._has_type_support() and issubclass(
                definition_type,
                self._TYPE_DEFINITION_TYPES,
            )
        except TypeError:
            return False

    def supports_type_alter_action(
        self,
        action_type: Type[TypeAlterAction],
    ) -> bool:
        try:
            return self._has_type_support() and issubclass(
                action_type,
                self._TYPE_ACTION_TYPES,
            )
        except TypeError:
            return False

    def supports_create_type_if_not_exists(self) -> bool:
        return self._has_type_support()

    def supports_create_type_or_replace(self) -> bool:
        return self._has_type_support()

    def supports_alter_type_if_exists(self) -> bool:
        return self._has_type_support()

    def supports_drop_type_if_exists(self) -> bool:
        return False

    def supports_multiple_type_alter_actions(self) -> bool:
        return False

    def _format_type_name(self, expr: Any) -> str:
        parts = []
        database_name = getattr(expr, "database_name", None)
        schema_name = getattr(expr, "schema_name", None)
        if database_name is not None:
            parts.append(cast(str, self.format_identifier(database_name)))
        if schema_name is not None:
            parts.append(cast(str, self.format_identifier(schema_name)))
        parts.append(cast(str, self.format_identifier(expr.type_name)))
        return ".".join(parts)

    def format_create_type_statement(
        self,
        expr: CreateTypeExpression,
    ) -> Tuple[str, tuple]:
        self._require_type_support("CREATE TYPE")
        if expr.if_not_exists and expr.or_replace:
            raise ValueError("CREATE TYPE IF NOT EXISTS and OR REPLACE are mutually exclusive")
        if expr.if_not_exists and not self.supports_create_type_if_not_exists():
            raise UnsupportedFeatureError(self.name, "CREATE TYPE IF NOT EXISTS")
        if expr.or_replace and not self.supports_create_type_or_replace():
            raise UnsupportedFeatureError(self.name, "CREATE OR REPLACE TYPE")
        if not self.supports_type_definition(type(expr.definition)):
            raise UnsupportedFeatureError(
                self.name,
                f"TYPE definition {expr.definition.definition_kind}",
            )
        definition_sql, definition_params = expr.definition.to_sql()
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("TYPE")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.extend((self._format_type_name(expr), definition_sql))
        comment = getattr(expr, "comment", None)
        if comment is not None:
            if not isinstance(comment, str):
                raise TypeError("Snowflake TYPE comment must be a string")
            parts.extend(("COMMENT", "=", self.format_literal(comment)))
        return " ".join(parts), tuple(definition_params)

    def format_alter_type_statement(
        self,
        expr: AlterTypeExpression,
    ) -> Tuple[str, tuple]:
        self._require_type_support("ALTER TYPE")
        if expr.if_exists and not self.supports_alter_type_if_exists():
            raise UnsupportedFeatureError(self.name, "ALTER TYPE IF EXISTS")
        if not expr.actions:
            raise ValueError("ALTER TYPE requires at least one action")
        if len(expr.actions) > 1 and not self.supports_multiple_type_alter_actions():
            raise UnsupportedFeatureError(self.name, "multiple ALTER TYPE actions")
        action_parts = []
        action_params = []
        for action in expr.actions:
            if not self.supports_type_alter_action(type(action)):
                raise UnsupportedFeatureError(
                    self.name,
                    f"ALTER TYPE action {action.action_kind}",
                )
            action_sql, params = action.to_sql()
            action_parts.append(action_sql)
            action_params.extend(params)
        parts = ["ALTER TYPE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.extend((self._format_type_name(expr), ", ".join(action_parts)))
        return " ".join(parts), tuple(action_params)

    def format_drop_type_statement(
        self,
        expr: DropTypeExpression,
    ) -> Tuple[str, tuple]:
        self._require_type_support("DROP TYPE")
        if expr.if_exists:
            raise UnsupportedFeatureError(self.name, "DROP TYPE IF EXISTS")
        if getattr(expr, "cascade", False):
            raise UnsupportedFeatureError(self.name, "DROP TYPE CASCADE")
        if getattr(expr, "restrict", False):
            raise UnsupportedFeatureError(self.name, "DROP TYPE RESTRICT")
        return f"DROP TYPE {self._format_type_name(expr)}", ()

    def format_type_definition(
        self,
        expr: TypeDefinition,
    ) -> Tuple[str, tuple]:
        self._require_type_support("TYPE definition")
        if isinstance(expr, SnowflakeScalarTypeDefinition):
            if isinstance(expr.data_type, SnowflakeUserDefinedType):
                raise UnsupportedFeatureError(
                    self.name,
                    "scalar UDT based on another UDT",
                    suggestion="Snowflake TYPE definitions must use a built-in Snowflake data type as their base.",
                )
            data_type_sql, data_type_params = cast(
                Tuple[str, tuple],
                expr.data_type.to_sql(),
            )
            return f"AS {data_type_sql}", data_type_params
        if isinstance(expr, SnowflakeObjectTypeDefinition):
            field_sql = []
            field_params = []
            for field in expr.fields:
                if not isinstance(field, SnowflakeTypeField):
                    raise TypeError("Snowflake OBJECT type fields must be SnowflakeTypeField instances")
                sql, params = field.to_sql()
                field_sql.append(sql)
                field_params.extend(params)
            return f"AS OBJECT({', '.join(field_sql)})", tuple(field_params)
        raise UnsupportedFeatureError(
            self.name,
            f"TYPE definition {getattr(expr, 'definition_kind', type(expr).__name__)}",
        )

    def format_snowflake_type_field(
        self,
        expr: SnowflakeTypeField,
    ) -> Tuple[str, tuple]:
        self._require_type_support("Snowflake OBJECT UDT field")
        type_sql, type_params = expr.data_type.to_sql()
        return f"{self.format_identifier(expr.name)} {type_sql}", tuple(type_params)

    def format_type_alter_action(
        self,
        expr: TypeAlterAction,
    ) -> Tuple[str, tuple]:
        self._require_type_support("ALTER TYPE action")
        if isinstance(expr, SnowflakeSetTypeCommentAction):
            return f"SET COMMENT = {self.format_literal(expr.comment)}", ()
        if isinstance(expr, SnowflakeUnsetTypeCommentAction):
            return "UNSET COMMENT", ()
        raise UnsupportedFeatureError(
            self.name,
            f"ALTER TYPE action {getattr(expr, 'action_kind', type(expr).__name__)}",
        )


__all__ = ["SNOWFLAKE_TYPE_DDL_MIN_VERSION", "SnowflakeTypeDDLMixin"]
