# src/rhosocial/activerecord/backend/impl/snowflake/protocols/materialized_view.py
"""Snowflake materialized view protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake materialized views precompute query results and are refreshed
incrementally in the background, managed via
``CREATE [OR REPLACE] MATERIALIZED VIEW ... AS <query>``.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-materialized-view
"""
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.materialized_view import (
        SnowflakeCreateMaterializedViewExpression,
    )


@runtime_checkable
class SnowflakeMaterializedViewSupport(Protocol):
    """Snowflake materialized view protocol."""

    def supports_materialized_view(self) -> bool:
        """Whether materialized views are supported."""
        ...

    def format_create_materialized_view_statement(
        self, expr: "SnowflakeCreateMaterializedViewExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] MATERIALIZED VIEW statement."""
        ...
