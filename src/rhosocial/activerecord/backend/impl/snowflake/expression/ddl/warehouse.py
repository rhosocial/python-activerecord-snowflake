# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/warehouse.py
"""Snowflake WAREHOUSE DDL expressions.

Virtual warehouses are Snowflake's compute resource model (equivalent to a
MySQL/PostgreSQL instance). These expressions generate CREATE / ALTER / DROP
WAREHOUSE statements, including SUSPEND / RESUME / SET / RENAME operations.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- CREATE WAREHOUSE: https://docs.snowflake.com/en/sql-reference/sql/create-warehouse
- ALTER WAREHOUSE:  https://docs.snowflake.com/en/sql-reference/sql/alter-warehouse
- DROP WAREHOUSE:   https://docs.snowflake.com/en/sql-reference/sql/drop-warehouse
"""
from enum import Enum
from typing import Any, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeAlterWarehouseMode",
    "SnowflakeCreateWarehouseExpression",
    "SnowflakeAlterWarehouseExpression",
    "SnowflakeDropWarehouseExpression",
]


class SnowflakeAlterWarehouseMode(Enum):
    """ALTER WAREHOUSE action modes.

    SUSPEND: shut down (suspend) the warehouse.
    RESUME:  restart (resume) the warehouse.
    SET:     change one or more warehouse properties.
    RENAME:  rename the warehouse.
    """

    SUSPEND = "SUSPEND"
    RESUME = "RESUME"
    SET = "SET"
    RENAME = "RENAME"


class SnowflakeCreateWarehouseExpression(BaseExpression):
    """Snowflake CREATE WAREHOUSE statement expression.

    Attributes:
        name: Warehouse name.
        or_replace: Emit ``OR REPLACE``.
        warehouse_size: ``WAREHOUSE_SIZE`` (e.g. ``'X-SMALL'``).
        max_cluster_count: ``MAX_CLUSTER_COUNT``.
        min_cluster_count: ``MIN_CLUSTER_COUNT``.
        scaling_policy: ``SCALING_POLICY`` (``'STANDARD'`` / ``'ECONOMY'``).
        auto_suspend: ``AUTO_SUSPEND`` — seconds as int, or a bool to disable.
        auto_resume: ``AUTO_RESUME`` bool.
        initially_suspended: ``INITIALLY_SUSPENDED`` bool.
        comment: ``COMMENT`` string literal.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        or_replace: bool = False,
        warehouse_size: Optional[str] = None,
        max_cluster_count: Optional[int] = None,
        min_cluster_count: Optional[int] = None,
        scaling_policy: Optional[str] = None,
        auto_suspend: Optional[Any] = None,
        auto_resume: Optional[bool] = None,
        initially_suspended: Optional[bool] = None,
        comment: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.or_replace = or_replace
        self.warehouse_size = warehouse_size
        self.max_cluster_count = max_cluster_count
        self.min_cluster_count = min_cluster_count
        self.scaling_policy = scaling_policy
        self.auto_suspend = auto_suspend
        self.auto_resume = auto_resume
        self.initially_suspended = initially_suspended
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE WAREHOUSE SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_create_warehouse_statement(self), ()


class SnowflakeAlterWarehouseExpression(BaseExpression):
    """Snowflake ALTER WAREHOUSE statement expression.

    The ``mode`` selects one of the four ALTER WAREHOUSE forms:
    ``SUSPEND``, ``RESUME``, ``SET`` or ``RENAME TO``. ``SET`` and ``RENAME``
    carry the property / target name on the expression.

    Attributes:
        name: Warehouse name.
        mode: :class:`SnowflakeAlterWarehouseMode`.
        new_name: New warehouse name for ``RENAME`` mode.
        warehouse_size: ``WAREHOUSE_SIZE`` for ``SET`` mode.
        max_cluster_count: ``MAX_CLUSTER_COUNT`` for ``SET`` mode.
        min_cluster_count: ``MIN_CLUSTER_COUNT`` for ``SET`` mode.
        scaling_policy: ``SCALING_POLICY`` for ``SET`` mode.
        auto_suspend: ``AUTO_SUSPEND`` for ``SET`` mode.
        auto_resume: ``AUTO_RESUME`` for ``SET`` mode.
        comment: ``COMMENT`` for ``SET`` mode.

    Raises:
        ValueError: RENAME without ``new_name``, or SET with no properties.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        mode: SnowflakeAlterWarehouseMode = SnowflakeAlterWarehouseMode.SUSPEND,
        new_name: Optional[str] = None,
        warehouse_size: Optional[str] = None,
        max_cluster_count: Optional[int] = None,
        min_cluster_count: Optional[int] = None,
        scaling_policy: Optional[str] = None,
        auto_suspend: Optional[Any] = None,
        auto_resume: Optional[bool] = None,
        comment: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.mode = mode
        self.new_name = new_name
        self.warehouse_size = warehouse_size
        self.max_cluster_count = max_cluster_count
        self.min_cluster_count = min_cluster_count
        self.scaling_policy = scaling_policy
        self.auto_suspend = auto_suspend
        self.auto_resume = auto_resume
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate ALTER WAREHOUSE SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_alter_warehouse_statement(self), ()


class SnowflakeDropWarehouseExpression(BaseExpression):
    """Snowflake DROP WAREHOUSE statement expression.

    Attributes:
        name: Warehouse name.
        if_exists: Emit ``IF EXISTS`` (drop is a no-op notice if absent).
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
        """Generate DROP WAREHOUSE SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_drop_warehouse_statement(self), ()
