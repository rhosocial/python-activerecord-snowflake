# src/rhosocial/activerecord/backend/impl/snowflake/mixins/ddl_database.py
"""Snowflake database DDL mixin."""
from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_database import (
        AlterDatabaseExpression,
        CreateDatabaseExpression,
        DropDatabaseExpression,
    )


class SnowflakeDatabaseMixin:
    """Snowflake database DDL support.

    Snowflake has rich database support including CLONE, TRANSIENT,
    MANAGED ACCESS, REPLICATION, FAILOVER, and more.
    """

    def supports_database(self) -> bool:
        return True

    def supports_create_database(self) -> bool:
        return True

    def supports_drop_database(self) -> bool:
        return True

    def supports_alter_database(self) -> bool:
        return True

    def supports_database_if_not_exists(self) -> bool:
        return True

    def supports_database_if_exists(self) -> bool:
        return True

    def supports_database_or_replace(self) -> bool:
        """Snowflake supports CREATE OR REPLACE DATABASE."""
        return True

    def supports_database_comment(self) -> bool:
        """Snowflake supports COMMENT for databases."""
        return True

    def supports_undrop_database(self) -> bool:
        """Snowflake supports UNDROP DATABASE."""
        return True

    def supports_database_force_drop(self) -> bool:
        """Snowflake supports DROP DATABASE ... FORCE."""
        return True

    def format_create_database_statement(
        self, expr: CreateDatabaseExpression
    ) -> Tuple[str, tuple]:
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        transient = expr.dialect_options.get("transient", False)
        if transient:
            parts.append("TRANSIENT")
        parts.append("DATABASE")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.database_name))
        clone_source = expr.dialect_options.get("clone")
        if clone_source:
            parts.append(f"CLONE {self.format_identifier(clone_source)}")
        if expr.comment:
            escaped_comment = expr.comment.replace("'", "''")
            parts.append(f"COMMENT = '{escaped_comment}'")
        return " ".join(parts), ()

    def format_drop_database_statement(
        self, expr: DropDatabaseExpression
    ) -> Tuple[str, tuple]:
        parts = ["DROP DATABASE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.database_name))
        return " ".join(parts), ()

    def format_alter_database_statement(
        self, expr: AlterDatabaseExpression
    ) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.expression.statements.ddl_database import AlterDatabaseAction
        parts = ["ALTER DATABASE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.database_name))
        if expr.action == AlterDatabaseAction.RENAME_TO:
            parts.append(f"RENAME TO {self.format_identifier(expr.target)}")
        elif expr.action == AlterDatabaseAction.SWAP_WITH:
            parts.append(f"SWAP WITH {self.format_identifier(expr.target)}")
        elif expr.action == AlterDatabaseAction.SET_PROPERTY:
            props = ", ".join(f"{k} = '{v}'" for k, v in expr.properties.items())
            parts.append(f"SET {props}")
        elif expr.action == AlterDatabaseAction.UNSET_PROPERTY:
            props = ", ".join(expr.properties.keys())
            parts.append(f"UNSET {props}")
        elif expr.action == AlterDatabaseAction.ENABLE_REPLICATION:
            parts.append("ENABLE REPLICATION")
        elif expr.action == AlterDatabaseAction.DISABLE_REPLICATION:
            parts.append("DISABLE REPLICATION")
        elif expr.action == AlterDatabaseAction.ENABLE_FAILOVER:
            parts.append("ENABLE FAILOVER")
        elif expr.action == AlterDatabaseAction.DISABLE_FAILOVER:
            parts.append("DISABLE FAILOVER")
        return " ".join(parts), ()


__all__ = ['SnowflakeDatabaseMixin']
