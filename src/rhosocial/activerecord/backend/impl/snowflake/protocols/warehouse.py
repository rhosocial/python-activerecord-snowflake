# src/rhosocial/activerecord/backend/impl/snowflake/protocols/warehouse.py
"""Snowflake warehouse (compute resource) protocol.

Feature Source: Snowflake native (not SQL standard)

Virtual warehouses are Snowflake's compute resource model, providing the
compute capacity for query execution. They are managed via:
- CREATE [OR REPLACE] WAREHOUSE ... WITH ... (compute properties)
- ALTER WAREHOUSE ... SUSPEND / RESUME / SET ... / RENAME TO ...
- DROP WAREHOUSE ...

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-warehouse
- https://docs.snowflake.com/en/sql-reference/sql/alter-warehouse
- https://docs.snowflake.com/en/sql-reference/sql/drop-warehouse
"""
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.warehouse import (
        SnowflakeAlterWarehouseExpression,
        SnowflakeCreateWarehouseExpression,
        SnowflakeDropWarehouseExpression,
    )


@runtime_checkable
class SnowflakeWarehouseSupport(Protocol):
    """Snowflake warehouse (compute resource) protocol."""

    def supports_warehouse(self) -> bool:
        """Whether warehouse operations are supported."""
        ...

    def format_create_warehouse_statement(
        self, expr: "SnowflakeCreateWarehouseExpression"
    ) -> str:
        """Format CREATE WAREHOUSE statement."""
        ...

    def format_alter_warehouse_statement(
        self, expr: "SnowflakeAlterWarehouseExpression"
    ) -> str:
        """Format ALTER WAREHOUSE statement.

        Emits ``SUSPEND`` / ``RESUME`` / ``SET`` / ``RENAME TO`` depending
        on the expression mode.
        """
        ...

    def format_drop_warehouse_statement(
        self, expr: "SnowflakeDropWarehouseExpression"
    ) -> str:
        """Format DROP WAREHOUSE statement."""
        ...
