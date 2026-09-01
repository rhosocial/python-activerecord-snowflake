# src/rhosocial/activerecord/backend/impl/snowflake/mixins/warehouse.py
"""SnowflakeWarehouseMixin — virtual warehouse DDL support."""

from typing import Any, List, TYPE_CHECKING

from ..expression.ddl.warehouse import SnowflakeAlterWarehouseMode

if TYPE_CHECKING:
    from ..expression.ddl.warehouse import (
        SnowflakeAlterWarehouseExpression,
        SnowflakeCreateWarehouseExpression,
        SnowflakeDropWarehouseExpression,
    )


class SnowflakeWarehouseMixin:
    """Mixin for Snowflake virtual warehouse (compute resource) support."""

    def supports_warehouse(self) -> bool:
        """Snowflake supports virtual warehouses."""
        return True

    def format_create_warehouse_statement(
        self, expr: "SnowflakeCreateWarehouseExpression"
    ) -> str:
        """Format CREATE WAREHOUSE statement.

        Args:
            expr: :class:`SnowflakeCreateWarehouseExpression`.

        Returns:
            The formatted CREATE WAREHOUSE SQL string.

        """
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("WAREHOUSE")
        parts.append(self.format_identifier(expr.name))
        options = self.format_warehouse_options(
            expr, include_initially_suspended=True
        )
        if options:
            parts.append("WITH")
            parts.extend(options)
        return " ".join(parts)

    def format_alter_warehouse_statement(
        self, expr: "SnowflakeAlterWarehouseExpression"
    ) -> str:
        """Format ALTER WAREHOUSE statement.

        Emits one of ``SUSPEND`` / ``RESUME`` / ``SET ...`` / ``RENAME TO ...``
        based on :attr:`expr.mode`.

        Args:
            expr: :class:`SnowflakeAlterWarehouseExpression`.

        Returns:
            The formatted ALTER WAREHOUSE SQL string.

        Raises:
            ValueError: RENAME without ``new_name``, or SET with no property.

        """
        mode = expr.mode
        parts = ["ALTER WAREHOUSE", self.format_identifier(expr.name)]
        if mode is SnowflakeAlterWarehouseMode.SUSPEND:
            parts.append("SUSPEND")
            return " ".join(parts)
        if mode is SnowflakeAlterWarehouseMode.RESUME:
            parts.append("RESUME")
            return " ".join(parts)
        if mode is SnowflakeAlterWarehouseMode.RENAME:
            if not expr.new_name:
                raise ValueError(
                    "ALTER WAREHOUSE RENAME requires a new_name"
                )
            parts.extend(["RENAME TO", self.format_identifier(expr.new_name)])
            return " ".join(parts)
        options = self.format_warehouse_options(
            expr, include_initially_suspended=False
        )
        if not options:
            raise ValueError(
                "ALTER WAREHOUSE SET requires at least one property"
            )
        parts.append("SET")
        parts.extend(options)
        return " ".join(parts)

    def format_drop_warehouse_statement(
        self, expr: "SnowflakeDropWarehouseExpression"
    ) -> str:
        """Format DROP WAREHOUSE statement.

        Args:
            expr: :class:`SnowflakeDropWarehouseExpression`.

        Returns:
            The formatted DROP WAREHOUSE SQL string.

        """
        parts = ["DROP WAREHOUSE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts)

    def format_warehouse_options(
        self,
        expr: Any,
        *,
        include_initially_suspended: bool,
    ) -> List[str]:
        """Render warehouse property tokens shared by CREATE and ALTER SET."""
        options = []
        if expr.warehouse_size is not None:
            options.append(
                f"WAREHOUSE_SIZE = "
                f"'{self._escape_sql_string(expr.warehouse_size)}'"
            )
        if expr.max_cluster_count is not None:
            options.append(f"MAX_CLUSTER_COUNT = {int(expr.max_cluster_count)}")
        if expr.min_cluster_count is not None:
            options.append(f"MIN_CLUSTER_COUNT = {int(expr.min_cluster_count)}")
        if expr.scaling_policy is not None:
            options.append(
                f"SCALING_POLICY = "
                f"'{self._escape_sql_string(expr.scaling_policy)}'"
            )
        if expr.auto_suspend is not None:
            if isinstance(expr.auto_suspend, bool):
                options.append(f"AUTO_SUSPEND = {str(expr.auto_suspend).upper()}")
            else:
                options.append(f"AUTO_SUSPEND = {int(expr.auto_suspend)}")
        if expr.auto_resume is not None:
            options.append(
                f"AUTO_RESUME = {str(bool(expr.auto_resume)).upper()}"
            )
        if include_initially_suspended and expr.initially_suspended is not None:
            options.append(
                f"INITIALLY_SUSPENDED = "
                f"{str(bool(expr.initially_suspended)).upper()}"
            )
        if expr.comment is not None:
            options.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        return options
