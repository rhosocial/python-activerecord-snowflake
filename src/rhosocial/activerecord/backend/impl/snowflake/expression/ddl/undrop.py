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

from ..coercion import as_member

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeUndropObjectType",
    "SnowflakeUndropExpression",
]


class SnowflakeUndropObjectType(str, Enum):
    """Object kinds supported by UNDROP."""
    #: A member *is* the word it carries: ``str()`` and f-string
    #: interpolation must yield the value, not ``ClassName.MEMBER``, or the
    #: rendered SQL and the artifact would carry the Python spelling.
    #: ``(str, Enum)`` alone does not give that -- ``Enum.__str__`` wins --
    #: so it is stated here once.
    __str__ = str.__str__

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
        self.object_type = as_member(SnowflakeUndropObjectType, object_type, parameter="object_type")

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate UNDROP SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_undrop_statement(self)
