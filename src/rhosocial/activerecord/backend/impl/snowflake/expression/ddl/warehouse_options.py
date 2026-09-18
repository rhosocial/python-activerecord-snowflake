# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/warehouse_options.py
"""Snowflake WAREHOUSE OPTIONS expression.

Holds the shared property set for CREATE WAREHOUSE and ALTER WAREHOUSE SET,
allowing the options to be formatted as a standalone expression clause.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- CREATE WAREHOUSE: https://docs.snowflake.com/en/sql-reference/sql/create-warehouse
- ALTER WAREHOUSE:  https://docs.snowflake.com/en/sql-reference/sql/alter-warehouse
"""
from typing import Any, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeWarehouseOptionsExpression",
]


class SnowflakeWarehouseOptionsExpression(BaseExpression):
    """Snowflake warehouse property options expression.

    Encapsulates the warehouse properties shared by CREATE and ALTER SET,
    including size, cluster counts, scaling policy, auto-suspend/resume,
    initial suspension state, and comment.

    Attributes:
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
        *,
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
        self.warehouse_size = warehouse_size
        self.max_cluster_count = max_cluster_count
        self.min_cluster_count = min_cluster_count
        self.scaling_policy = scaling_policy
        self.auto_suspend = auto_suspend
        self.auto_resume = auto_resume
        self.initially_suspended = initially_suspended
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate warehouse options SQL tokens.

        Returns:
            Tuple of (options SQL string, empty params tuple).

        """
        parts: list[str] = []
        if self.warehouse_size is not None:
            parts.append(
                f"WAREHOUSE_SIZE = "
                f"'{self.dialect._escape_sql_string(self.warehouse_size)}'"
            )
        if self.max_cluster_count is not None:
            parts.append(f"MAX_CLUSTER_COUNT = {int(self.max_cluster_count)}")
        if self.min_cluster_count is not None:
            parts.append(f"MIN_CLUSTER_COUNT = {int(self.min_cluster_count)}")
        if self.scaling_policy is not None:
            parts.append(
                f"SCALING_POLICY = "
                f"'{self.dialect._escape_sql_string(self.scaling_policy)}'"
            )
        if self.auto_suspend is not None:
            if isinstance(self.auto_suspend, bool):
                parts.append(f"AUTO_SUSPEND = {str(self.auto_suspend).upper()}")
            else:
                parts.append(f"AUTO_SUSPEND = {int(self.auto_suspend)}")
        if self.auto_resume is not None:
            parts.append(
                f"AUTO_RESUME = {str(bool(self.auto_resume)).upper()}"
            )
        if self.initially_suspended is not None:
            parts.append(
                f"INITIALLY_SUSPENDED = "
                f"{str(bool(self.initially_suspended)).upper()}"
            )
        if self.comment is not None:
            parts.append(
                f"COMMENT = '{self.dialect._escape_sql_string(self.comment)}'"
            )
        return " ".join(parts), ()
