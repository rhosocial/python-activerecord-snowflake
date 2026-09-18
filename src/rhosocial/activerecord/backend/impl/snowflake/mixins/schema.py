# src/rhosocial/activerecord/backend/impl/snowflake/mixins/schema.py
"""Snowflake schema DDL mixin."""
from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_schema import (
        CreateSchemaExpression,
        DropSchemaExpression,
    )


class SnowflakeSchemaMixin:
    """Snowflake schema DDL support.

    Snowflake has rich schema support including CREATE/DROP/ALTER SCHEMA,
    CLONE, TRANSIENT, MANAGED ACCESS, and more.
    """

    def supports_schema(self) -> bool:
        """Snowflake uses three-level namespace (database.schema.table)."""
        return True

    def supports_create_schema(self) -> bool:
        """Snowflake supports CREATE SCHEMA."""
        return True

    def supports_drop_schema(self) -> bool:
        """Snowflake supports DROP SCHEMA."""
        return True

    def supports_schema_if_not_exists(self) -> bool:
        """Snowflake supports CREATE SCHEMA IF NOT EXISTS."""
        return True

    def supports_schema_if_exists(self) -> bool:
        """Snowflake supports DROP SCHEMA IF EXISTS."""
        return True

    def supports_schema_cascade(self) -> bool:
        """Snowflake supports DROP SCHEMA CASCADE."""
        return True

    def supports_schema_authorization(self) -> bool:
        """Snowflake does not support AUTHORIZATION clause."""
        return False

    def supports_alter_schema(self) -> bool:
        """Snowflake supports ALTER SCHEMA."""
        return True

    def supports_alter_schema_rename(self) -> bool:
        """Snowflake supports ALTER SCHEMA RENAME TO."""
        return True

    def supports_alter_schema_swap(self) -> bool:
        """Snowflake supports ALTER SCHEMA SWAP WITH."""
        return True

    def supports_alter_schema_set_property(self) -> bool:
        """Snowflake supports ALTER SCHEMA SET."""
        return True

    def supports_alter_schema_managed_access(self) -> bool:
        """Snowflake supports ALTER SCHEMA SET MANAGED ACCESS."""
        return True

    def supports_undrop_schema(self) -> bool:
        """Snowflake supports UNDROP SCHEMA."""
        return True

    def format_create_schema_statement(self, expr: CreateSchemaExpression) -> Tuple[str, tuple]:
        if expr.if_not_exists and not self.supports_schema_if_not_exists():
            raise UnsupportedFeatureError(
                self.name, "CREATE SCHEMA IF NOT EXISTS",
                f"{self.name} does not support CREATE SCHEMA IF NOT EXISTS."
            )
        if expr.authorization and not self.supports_schema_authorization():
            raise UnsupportedFeatureError(
                self.name, "CREATE SCHEMA AUTHORIZATION",
                f"{self.name} does not support CREATE SCHEMA AUTHORIZATION."
            )
        parts = ["CREATE SCHEMA"]
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.schema_name))
        if expr.authorization:
            parts.append(f"AUTHORIZATION {self.format_identifier(expr.authorization)}")
        return " ".join(parts), ()

    def format_drop_schema_statement(self, expr: DropSchemaExpression) -> Tuple[str, tuple]:
        if expr.if_exists and not self.supports_schema_if_exists():
            raise UnsupportedFeatureError(
                self.name, "DROP SCHEMA IF EXISTS",
                f"{self.name} does not support DROP SCHEMA IF EXISTS."
            )
        if expr.cascade and not self.supports_schema_cascade():
            raise UnsupportedFeatureError(
                self.name, "DROP SCHEMA CASCADE",
                f"{self.name} does not support DROP SCHEMA CASCADE."
            )
        parts = ["DROP SCHEMA"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.schema_name))
        if expr.cascade:
            parts.append("CASCADE")
        return " ".join(parts), ()


__all__ = ['SnowflakeSchemaMixin']
