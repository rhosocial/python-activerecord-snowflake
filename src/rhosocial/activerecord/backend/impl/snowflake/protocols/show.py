# src/rhosocial/activerecord/backend/impl/snowflake/protocols/show.py
"""Snowflake SHOW statement protocol.

Feature Source: Snowflake native (not SQL standard)

The ``SHOW`` command lists metadata about Snowflake objects. It supports
scoping by namespace (``IN {ACCOUNT | DATABASE | SCHEMA}``), name filtering
(``LIKE 'pattern'``) and result row limits (``LIMIT``).

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/show
"""
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.show import SnowflakeShowExpression


@runtime_checkable
class SnowflakeShowSupport(Protocol):
    """Snowflake SHOW statement protocol."""

    def supports_show(self) -> bool:
        """Whether the SHOW command is supported."""
        ...

    def format_show_statement(
        self, expr: "SnowflakeShowExpression"
    ) -> str:
        """Format a SHOW statement."""
        ...
