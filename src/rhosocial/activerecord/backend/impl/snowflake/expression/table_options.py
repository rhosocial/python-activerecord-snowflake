# src/rhosocial/activerecord/backend/impl/snowflake/expression/table_options.py
"""Snowflake-specific CREATE TABLE options.

Snowflake adds the ``TRANSIENT`` header modifier to ``CREATE TABLE``, which
has no generic equivalent. It lives on ``SnowflakeCreateTableOptions``
(deriving the generic ``CreateTableOptions``) and is rendered by the Snowflake
``format_create_table_options`` override.
"""

from typing import Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.statements import (
    CreateTableOptions,
    TableCommentClause,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeCreateTableOptions",
]


class SnowflakeCreateTableOptions(CreateTableOptions):
    """A Snowflake CREATE TABLE options declaration extending the generic one.

    Adds the Snowflake-only ``transient`` header modifier.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        or_replace: bool = False,
        comment: Optional[TableCommentClause] = None,
        transient: bool = False,
    ):
        super().__init__(dialect, or_replace=or_replace, comment=comment)
        self.transient = transient
