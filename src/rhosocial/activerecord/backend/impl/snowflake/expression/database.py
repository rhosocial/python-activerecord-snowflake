# src/rhosocial/activerecord/backend/impl/snowflake/expression/database.py
"""Snowflake-specific CREATE DATABASE expression."""

from typing import TYPE_CHECKING, Optional

from rhosocial.activerecord.backend.expression.statements.ddl_database import (
    CreateDatabaseExpression,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SnowflakeCreateDatabaseExpression(CreateDatabaseExpression):
    """A Snowflake CREATE DATABASE statement extending the generic one.

    Adds the Snowflake-only ``TRANSIENT`` qualifier and ``CLONE <source>``
    form, which have no generic equivalent.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        database_name: str,
        if_not_exists: bool = False,
        owner: Optional[str] = None,
        encoding: Optional[str] = None,
        collation: Optional[str] = None,
        tablespace: Optional[str] = None,
        template: Optional[str] = None,
        connection_limit: Optional[int] = None,
        comment: Optional[str] = None,
        or_replace: bool = False,
        *,
        transient: bool = False,
        clone: Optional[str] = None,
    ):
        super().__init__(
            dialect,
            database_name=database_name,
            if_not_exists=if_not_exists,
            owner=owner,
            encoding=encoding,
            collation=collation,
            tablespace=tablespace,
            template=template,
            connection_limit=connection_limit,
            comment=comment,
            or_replace=or_replace,
        )
        self.transient = transient
        self.clone = clone


__all__ = [
    "SnowflakeCreateDatabaseExpression",
]
