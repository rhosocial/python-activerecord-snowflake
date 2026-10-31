# src/rhosocial/activerecord/backend/impl/snowflake/expression/show.py
"""Snowflake SHOW statement expression.

The ``SHOW`` command lists metadata about Snowflake objects (tables, views,
warehouses, stages, tasks, pipes, streams, ...). Unlike ``DESCRIBE`` it can
filter objects by scope (``IN {ACCOUNT | DATABASE | SCHEMA}``), by name
pattern (``LIKE``) and by result row count (``LIMIT``).

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- SHOW: https://docs.snowflake.com/en/sql-reference/sql/show
"""
from enum import Enum
from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

from .coercion import as_member

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeShowObjectType",
    "SnowflakeShowScope",
    "SnowflakeShowStatement",
]


class SnowflakeShowObjectType(str, Enum):
    """Object types supported by the SHOW command."""
    #: A member *is* the word it carries: ``str()`` and f-string
    #: interpolation must yield the value, not ``ClassName.MEMBER``, or the
    #: rendered SQL and the artifact would carry the Python spelling.
    #: ``(str, Enum)`` alone does not give that -- ``Enum.__str__`` wins --
    #: so it is stated here once.
    __str__ = str.__str__

    TABLES = "TABLES"
    VIEWS = "VIEWS"
    SCHEMAS = "SCHEMAS"
    DATABASES = "DATABASES"
    WAREHOUSES = "WAREHOUSES"
    STAGES = "STAGES"
    TASKS = "TASKS"
    PIPES = "PIPES"
    STREAMS = "STREAMS"
    FILE_FORMATS = "FILE FORMATS"
    SEQUENCES = "SEQUENCES"
    USERS = "USERS"
    ROLES = "ROLES"
    FUNCTIONS = "FUNCTIONS"
    PROCEDURES = "PROCEDURES"
    COLUMNS = "COLUMNS"


class SnowflakeShowScope(str, Enum):
    """Namespace scope for the SHOW ``IN`` clause."""
    #: A member *is* the word it carries: ``str()`` and f-string
    #: interpolation must yield the value, not ``ClassName.MEMBER``, or the
    #: rendered SQL and the artifact would carry the Python spelling.
    #: ``(str, Enum)`` alone does not give that -- ``Enum.__str__`` wins --
    #: so it is stated here once.
    __str__ = str.__str__

    ACCOUNT = "ACCOUNT"
    DATABASE = "DATABASE"
    SCHEMA = "SCHEMA"


class SnowflakeShowStatement(BaseExpression):
    """Snowflake SHOW statement expression.

    Attributes:
        object_type: :class:`SnowflakeShowObjectType` to list.
        in_scope: Optional :class:`SnowflakeShowScope` namespace to search in.
        in_name: Optional namespace name for the ``IN`` clause.
        like: Optional ``LIKE`` name pattern.
        limit: Optional result row ``LIMIT``.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        object_type: SnowflakeShowObjectType,
        *,
        in_scope: Optional[SnowflakeShowScope] = None,
        in_name: Optional[str] = None,
        like: Optional[str] = None,
        limit: Optional[int] = None,
    ):
        super().__init__(dialect)
        self.object_type = as_member(SnowflakeShowObjectType, object_type, parameter="object_type")
        self.in_scope = as_member(SnowflakeShowScope, in_scope, parameter="in_scope")
        self.in_name = in_name
        self.like = like
        self.limit = limit

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate the SHOW statement SQL.

        Returns:
            Tuple of (statement SQL string, empty params tuple).

        """
        return self.dialect.format_show_statement(self)
