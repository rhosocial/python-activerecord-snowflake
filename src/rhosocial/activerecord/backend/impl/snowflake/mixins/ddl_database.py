# src/rhosocial/activerecord/backend/impl/snowflake/mixins/ddl_database.py
"""Snowflake database DDL mixin."""
from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Database

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

    # The remaining CREATE DATABASE clause switches. Snowflake composes neither
    # the generic ``DatabaseMixin`` nor its default-False probes, so each one
    # Snowflake has no syntax for is declared here. They matter: the generic
    # renderer reads them before deciding a clause is emit-able, and a probe
    # that does not exist reads as "not implemented" rather than "no".
    def supports_database_owner(self) -> bool:
        """Snowflake CREATE DATABASE has no OWNER / AUTHORIZATION clause."""
        return False

    def supports_database_encoding(self) -> bool:
        """Snowflake CREATE DATABASE has no ENCODING clause."""
        return False

    def supports_database_collation(self) -> bool:
        """Snowflake CREATE DATABASE has no COLLATE clause."""
        return False

    def supports_database_tablespace(self) -> bool:
        """Snowflake has no tablespaces."""
        return False

    def supports_database_template(self) -> bool:
        """Snowflake CREATE DATABASE has no TEMPLATE clause."""
        return False

    def supports_database_connection_limit(self) -> bool:
        """Snowflake CREATE DATABASE has no CONNECTION LIMIT clause."""
        return False

    def supports_undrop_database(self) -> bool:
        """Snowflake supports UNDROP DATABASE."""
        return True

    def supports_database_force_drop(self) -> bool:
        """Snowflake supports DROP DATABASE ... FORCE."""
        return True

    def format_create_database_statement(
        self, expr: CreateDatabaseExpression
    ) -> Tuple[str, tuple]:
        # The object-kind check belongs to the formatter that consumes the
        # object, not to the constructor. An object carries its own
        # ``format_method``, so handing this statement a Table would render
        # ``CREATE DATABASE "users"`` -- well-formed SQL naming a table -- and
        # the wrong kind would be indistinguishable from the right one.
        if not isinstance(expr.database, Database):
            raise TypeError(
                f"{type(expr).__name__}.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        if getattr(expr, "transient", False):
            parts.append("TRANSIENT")
        parts.append("DATABASE")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(expr.database.to_sql()[0])
        clone_source = getattr(expr, "clone", None)
        if clone_source:
            parts.append(f"CLONE {self.format_identifier(clone_source)}")
        if expr.comment:
            escaped_comment = expr.comment.replace("'", "''")
            parts.append(f"COMMENT = '{escaped_comment}'")
        return " ".join(parts), ()

    def format_drop_database_statement(
        self, expr: DropDatabaseExpression
    ) -> Tuple[str, tuple]:
        if not isinstance(expr.database, Database):
            raise TypeError(
                f"{type(expr).__name__}.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        parts = ["DROP DATABASE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(expr.database.to_sql()[0])
        return " ".join(parts), ()

    def format_alter_database_statement(
        self, expr: AlterDatabaseExpression
    ) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.expression.statements.ddl_database import AlterDatabaseAction
        if not isinstance(expr.database, Database):
            raise TypeError(
                f"{type(expr).__name__}.database must be a Database, "
                f"got {type(expr.database).__name__}"
            )
        parts = ["ALTER DATABASE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(expr.database.to_sql()[0])
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
