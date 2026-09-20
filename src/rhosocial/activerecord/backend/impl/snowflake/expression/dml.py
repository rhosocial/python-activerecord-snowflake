# src/rhosocial/activerecord/backend/impl/snowflake/expression/dml.py
"""Snowflake-specific DML expression classes."""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression.statements import InsertExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class SnowflakeInsertExpression(InsertExpression):
    """A Snowflake INSERT statement extending the generic one.

    Snowflake supports ``INSERT OVERWRITE INTO`` which truncates the target
    table inside the same transaction; the flag lives here as a typed field and
    is rendered by ``SnowflakeDMLMixin.format_insert_statement``.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        into,
        source,
        columns=None,
        *,
        on_conflict=None,
        returning=None,
        overwrite: bool = False,
    ):
        super().__init__(
            dialect,
            into=into,
            source=source,
            columns=columns,
            on_conflict=on_conflict,
            returning=returning,
        )
        self.overwrite = overwrite


__all__ = [
    "SnowflakeInsertExpression",
]
