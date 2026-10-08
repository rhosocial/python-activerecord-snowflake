# src/rhosocial/activerecord/backend/impl/snowflake/mixins/schema.py
"""Snowflake schema DDL mixin."""
from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Schema

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
        """Snowflake has schemas, so ``CREATE SCHEMA`` may be offered at all.

        This is the DDL-side switch and it is declared here, next to the
        granular ``supports_create_schema`` family it umbrellas. Whether a name
        may be *qualified* with a schema is the naming-side question and lives
        on :class:`~...mixins.namespace.SnowflakeNamespaceMixin` as
        ``supports_schema_qualification``; the two are named apart because an
        engine may answer them differently, though Snowflake answers both
        ``True``. It used to be declared a second time in
        :class:`~...mixins.capabilities.SnowflakeCapabilityMixin`, where the
        earlier MRO position silently won over this one -- so this is the only
        ``supports_schema`` in the backend, and the naming side states its own
        answer in exactly one place.
        """
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

    def supports_schema_restrict(self) -> bool:
        """Snowflake supports DROP SCHEMA RESTRICT.

        The reference grammar is ``DROP SCHEMA [ IF EXISTS ] <name>
        [ CASCADE | RESTRICT ]``; RESTRICT returns a warning about existing
        foreign-key references and does not drop the schema. Core's probe
        defaults to ``False`` (fail closed), so this dialect declares it.
        https://docs.snowflake.com/en/sql-reference/sql/drop-schema
        """
        return True

    def supports_schema_authorization(self) -> bool:
        """Snowflake does not support AUTHORIZATION clause."""
        return False

    def supports_alter_schema(self) -> bool:
        """Whether ``ALTER SCHEMA`` is supported.

        Snowflake natively supports ALTER SCHEMA, but there is no
        ``AlterSchemaExpression`` / formatter yet, so the capability is
        advertised as unsupported to avoid a dead, unrenderable switch.
        """
        return False

    def supports_alter_schema_rename(self) -> bool:
        """Snowflake supports ALTER SCHEMA RENAME TO (not modelled yet)."""
        return False

    def supports_alter_schema_swap(self) -> bool:
        """Snowflake supports ALTER SCHEMA SWAP WITH (not modelled yet)."""
        return False

    def supports_alter_schema_set_property(self) -> bool:
        """Snowflake supports ALTER SCHEMA SET (not modelled yet)."""
        return False

    def supports_alter_schema_managed_access(self) -> bool:
        """Snowflake supports ALTER SCHEMA SET MANAGED ACCESS (not modelled yet)."""
        return False

    def supports_undrop_schema(self) -> bool:
        """Snowflake supports UNDROP SCHEMA."""
        return True

    def format_create_schema_statement(self, expr: CreateSchemaExpression) -> Tuple[str, tuple]:
        # The object kind is checked here rather than in the constructor: an
        # object renders itself through its own ``format_method``, so a Table
        # handed here would produce a well-formed ``CREATE SCHEMA "users"``.
        if not isinstance(expr.schema, Schema):
            raise TypeError(
                f"{type(expr).__name__}.schema must be a Schema, "
                f"got {type(expr.schema).__name__}"
            )
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
        parts.append(expr.schema.to_sql()[0])
        if expr.authorization:
            parts.append(f"AUTHORIZATION {self.format_identifier(expr.authorization)}")
        return " ".join(parts), ()

    def format_drop_schema_statement(self, expr: DropSchemaExpression) -> Tuple[str, tuple]:
        if not isinstance(expr.schema, Schema):
            raise TypeError(
                f"{type(expr).__name__}.schema must be a Schema, "
                f"got {type(expr.schema).__name__}"
            )
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
        if expr.restrict and not self.supports_schema_restrict():
            raise UnsupportedFeatureError(
                self.name, "DROP SCHEMA RESTRICT",
                f"{self.name} does not support DROP SCHEMA RESTRICT."
            )
        parts = ["DROP SCHEMA"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(expr.schema.to_sql()[0])
        if expr.cascade:
            parts.append("CASCADE")
        elif expr.restrict:
            parts.append("RESTRICT")
        return " ".join(parts), ()


__all__ = ['SnowflakeSchemaMixin']
