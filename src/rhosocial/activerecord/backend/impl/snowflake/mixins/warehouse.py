# src/rhosocial/activerecord/backend/impl/snowflake/mixins/warehouse.py
"""SnowflakeWarehouseMixin — virtual warehouse DDL support."""

from typing import Tuple, TYPE_CHECKING

from ..expression.ddl.warehouse import SnowflakeAlterWarehouseMode

if TYPE_CHECKING:
    from ..expression.ddl.warehouse import (
        SnowflakeAlterWarehouseExpression,
        SnowflakeCreateWarehouseExpression,
        SnowflakeDropWarehouseExpression,
    )
    from ..expression.ddl.warehouse_options import (
        SnowflakeWarehouseOptionsExpression,
    )


class SnowflakeWarehouseMixin:
    """Mixin for Snowflake virtual warehouse (compute resource) support."""

    def supports_warehouse(self) -> bool:
        """Snowflake supports virtual warehouses."""
        return True

    def format_warehouse_options_expression(
        self, expr: "SnowflakeWarehouseOptionsExpression"
    ) -> Tuple[str, tuple]:
        """Render the shared warehouse property set as ``KEY = value`` tokens.

        The same nine properties appear on ``CREATE WAREHOUSE`` and on
        ``ALTER WAREHOUSE ... SET``, in the same spelling, so they are rendered
        once here and the two statements ask for this clause. A property left
        ``None`` is omitted rather than written as a default -- the server's own
        default is the answer, and inventing one would silently override it.

        ``AUTO_SUSPEND`` takes a number of seconds *or* the ``FALSE`` / ``TRUE``
        keyword, which is why it is the one property whose value decides its
        own spelling; Snowflake documents both forms.

        https://docs.snowflake.com/en/sql-reference/sql/create-warehouse
        https://docs.snowflake.com/en/sql-reference/sql/alter-warehouse
        """
        parts: list[str] = []
        if expr.warehouse_size is not None:
            parts.append(f"WAREHOUSE_SIZE = {self.format_literal(expr.warehouse_size)}")
        if expr.max_cluster_count is not None:
            parts.append(f"MAX_CLUSTER_COUNT = {int(expr.max_cluster_count)}")
        if expr.min_cluster_count is not None:
            parts.append(f"MIN_CLUSTER_COUNT = {int(expr.min_cluster_count)}")
        if expr.scaling_policy is not None:
            parts.append(f"SCALING_POLICY = {self.format_literal(expr.scaling_policy)}")
        if expr.auto_suspend is not None:
            if isinstance(expr.auto_suspend, bool):
                parts.append(f"AUTO_SUSPEND = {str(expr.auto_suspend).upper()}")
            else:
                parts.append(f"AUTO_SUSPEND = {int(expr.auto_suspend)}")
        if expr.auto_resume is not None:
            parts.append(f"AUTO_RESUME = {str(bool(expr.auto_resume)).upper()}")
        if expr.initially_suspended is not None:
            value = str(bool(expr.initially_suspended)).upper()
            parts.append(f"INITIALLY_SUSPENDED = {value}")
        if expr.comment is not None:
            parts.append(f"COMMENT = {self.format_literal(expr.comment)}")
        return " ".join(parts), ()

    def format_create_warehouse_statement(
        self, expr: "SnowflakeCreateWarehouseExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE WAREHOUSE statement.

        Args:
            expr: :class:`SnowflakeCreateWarehouseExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("WAREHOUSE")
        parts.append(self.format_identifier(expr.name))
        options: list[str] = []
        if expr.warehouse_size is not None:
            options.append(
                f"WAREHOUSE_SIZE = "
                f"'{self.escape_sql_string(expr.warehouse_size)}'"
            )
        if expr.max_cluster_count is not None:
            options.append(f"MAX_CLUSTER_COUNT = {int(expr.max_cluster_count)}")
        if expr.min_cluster_count is not None:
            options.append(f"MIN_CLUSTER_COUNT = {int(expr.min_cluster_count)}")
        if expr.scaling_policy is not None:
            options.append(
                f"SCALING_POLICY = "
                f"'{self.escape_sql_string(expr.scaling_policy)}'"
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
        if expr.initially_suspended is not None:
            options.append(
                f"INITIALLY_SUSPENDED = "
                f"{str(bool(expr.initially_suspended)).upper()}"
            )
        if expr.comment is not None:
            options.append(
                f"COMMENT = '{self.escape_sql_string(expr.comment)}'"
            )
        if options:
            parts.append("WITH")
            parts.extend(options)
        return " ".join(parts), ()

    def format_alter_warehouse_statement(
        self, expr: "SnowflakeAlterWarehouseExpression"
    ) -> Tuple[str, tuple]:
        """Format ALTER WAREHOUSE statement.

        Emits one of ``SUSPEND`` / ``RESUME`` / ``SET ...`` / ``RENAME TO ...``
        based on :attr:`expr.mode`.

        Args:
            expr: :class:`SnowflakeAlterWarehouseExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        Raises:
            ValueError: RENAME without ``new_name``, or SET with no property.

        """
        mode = expr.mode
        parts = ["ALTER WAREHOUSE", self.format_identifier(expr.name)]
        if mode is SnowflakeAlterWarehouseMode.SUSPEND:
            parts.append("SUSPEND")
            return " ".join(parts), ()
        if mode is SnowflakeAlterWarehouseMode.RESUME:
            parts.append("RESUME")
            return " ".join(parts), ()
        if mode is SnowflakeAlterWarehouseMode.RENAME:
            if not expr.new_name:
                raise ValueError(
                    "ALTER WAREHOUSE RENAME requires a new_name"
                )
            parts.extend(["RENAME TO", self.format_identifier(expr.new_name)])
            return " ".join(parts), ()
        options: list[str] = []
        if expr.warehouse_size is not None:
            options.append(
                f"WAREHOUSE_SIZE = "
                f"'{self.escape_sql_string(expr.warehouse_size)}'"
            )
        if expr.max_cluster_count is not None:
            options.append(f"MAX_CLUSTER_COUNT = {int(expr.max_cluster_count)}")
        if expr.min_cluster_count is not None:
            options.append(f"MIN_CLUSTER_COUNT = {int(expr.min_cluster_count)}")
        if expr.scaling_policy is not None:
            options.append(
                f"SCALING_POLICY = "
                f"'{self.escape_sql_string(expr.scaling_policy)}'"
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
        if expr.comment is not None:
            options.append(
                f"COMMENT = '{self.escape_sql_string(expr.comment)}'"
            )
        if not options:
            raise ValueError(
                "ALTER WAREHOUSE SET requires at least one property"
            )
        parts.append("SET")
        parts.extend(options)
        return " ".join(parts), ()

    def format_drop_warehouse_statement(
        self, expr: "SnowflakeDropWarehouseExpression"
    ) -> Tuple[str, tuple]:
        """Format DROP WAREHOUSE statement.

        Args:
            expr: :class:`SnowflakeDropWarehouseExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = ["DROP WAREHOUSE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts), ()
