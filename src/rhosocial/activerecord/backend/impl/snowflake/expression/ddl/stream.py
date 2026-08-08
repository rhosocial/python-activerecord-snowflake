# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/stream.py
"""Snowflake STREAM expressions.

Streams provide change data capture (CDC) on top of a source object
(TABLE / VIEW / EXTERNAL TABLE / STAGE). These expressions generate
CREATE [OR REPLACE] STREAM and DROP STREAM statements, including the
APPEND_ONLY / INSERT_ONLY controls and AT / BEFORE time-travel points.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- CREATE STREAM: https://docs.snowflake.com/en/sql-reference/sql/create-stream
- DROP STREAM:   https://docs.snowflake.com/en/sql-reference/sql/drop-stream
"""
from enum import Enum
from typing import Any, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeStreamObjectType",
    "SnowflakeCreateStreamExpression",
    "SnowflakeDropStreamExpression",
]


class SnowflakeStreamObjectType(Enum):
    """Source object kinds supported by CREATE STREAM.

    TABLE:        table stream (default).
    VIEW:         view stream.
    EXTERNAL_TABLE: external table stream.
    STAGE:        stage stream.
    """

    TABLE = "TABLE"
    VIEW = "VIEW"
    EXTERNAL_TABLE = "EXTERNAL TABLE"
    STAGE = "STAGE"


class SnowflakeCreateStreamExpression(BaseExpression):
    """Snowflake CREATE [OR REPLACE] STREAM statement expression.

    Attributes:
        name: Stream name.
        or_replace: Emit ``OR REPLACE``.
        if_not_exists: Emit ``IF NOT EXISTS``.
        object_type: :class:`SnowflakeStreamObjectType` source kind.
        object_name: Name of the source object.
        append_only: ``APPEND_ONLY`` bool.
        insert_only: ``INSERT_ONLY`` bool.
        show_initial_rows: ``SHOW_INITIAL_ROWS`` bool.
        at: ``AT`` time-travel point as ``(kind, value)`` where kind is
            ``TIMESTAMP`` / ``OFFSET`` / ``STATEMENT``.
        before: ``BEFORE`` time-travel point as ``(kind, value)``.
        copy_grants: ``COPY_GRANTS`` bool.
        comment: ``COMMENT`` string literal.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        or_replace: bool = False,
        if_not_exists: bool = False,
        object_type: SnowflakeStreamObjectType = SnowflakeStreamObjectType.TABLE,
        object_name: Optional[str] = None,
        append_only: Optional[bool] = None,
        insert_only: Optional[bool] = None,
        show_initial_rows: Optional[bool] = None,
        at: Optional[Tuple[str, Any]] = None,
        before: Optional[Tuple[str, Any]] = None,
        copy_grants: Optional[bool] = None,
        comment: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.or_replace = or_replace
        self.if_not_exists = if_not_exists
        self.object_type = object_type
        self.object_name = object_name
        self.append_only = append_only
        self.insert_only = insert_only
        self.show_initial_rows = show_initial_rows
        self.at = at
        self.before = before
        self.copy_grants = copy_grants
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE STREAM SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_create_stream_statement(self), ()


class SnowflakeDropStreamExpression(BaseExpression):
    """Snowflake DROP STREAM statement expression.

    Attributes:
        name: Stream name.
        if_exists: Emit ``IF EXISTS``.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        if_exists: bool = False,
    ):
        super().__init__(dialect)
        self.name = name
        self.if_exists = if_exists

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate DROP STREAM SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_drop_stream_statement(self), ()
