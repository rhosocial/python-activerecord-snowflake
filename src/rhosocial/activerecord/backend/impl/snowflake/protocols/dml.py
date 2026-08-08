# src/rhosocial/activerecord/backend/impl/snowflake/protocols/dml.py
"""Snowflake DML statement protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake's ``INSERT OVERWRITE`` truncates the target table and inserts the
source rows inside the same transaction, avoiding the implicit commit of a
separate ``TRUNCATE`` + ``INSERT`` pair.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/insert
"""
from typing import Protocol, runtime_checkable, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        InsertExpression,
    )


@runtime_checkable
class SnowflakeDMLSupport(Protocol):
    """Snowflake DML statement protocol."""

    def supports_insert_overwrite(self) -> bool:
        """Whether INSERT OVERWRITE is supported."""
        ...

    def format_insert_statement(
        self, expr: "InsertExpression"
    ) -> Tuple[str, tuple]:
        """Format an INSERT statement (honours the ``overwrite`` option)."""
        ...

    def format_insert_overwrite_statement(
        self, expr: "InsertExpression"
    ) -> Tuple[str, tuple]:
        """Format an INSERT OVERWRITE statement."""
        ...
