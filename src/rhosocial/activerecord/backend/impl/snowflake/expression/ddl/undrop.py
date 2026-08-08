# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/undrop.py
"""Snowflake UNDROP expression.

UNDROP restores an object dropped within its time-travel retention window.
Snowflake can undrop tables, schemas, databases, tags and other object
kinds. This expression generates UNDROP statements.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- UNDROP: https://docs.snowflake.com/en/sql-reference/sql/undrop
"""
from enum import Enum
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeUndropObjectType",
    "SnowflakeUndropExpression",
]


class SnowflakeUndropObjectType(Enum):
    """Object kinds supported by UNDROP."""

    TABLE = "TABLE"
    SCHEMA = "SCHEMA"
    DATABASE = "DATABASE"
    TAG = "TAG"


class SnowflakeUndropExpression(BaseExpression):
    """Snowflake UNDROP statement expression.

    Attributes:
        name: Name of the object to restore.
        object_type: :class:`SnowflakeUndropObjectType`.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        object_type: SnowflakeUndropObjectType = SnowflakeUndropObjectType.TABLE,
    ):
        super().__init__(dialect)
        self.name = name
        self.object_type = object_type

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate UNDROP SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_undrop_statement(self), ()
