# src/rhosocial/activerecord/backend/impl/snowflake/mixins/task.py
"""SnowflakeTaskMixin — task (scheduled SQL) DDL support."""

from typing import Any, Optional, TYPE_CHECKING

from ..expression.ddl.task import SnowflakeAlterTaskMode

if TYPE_CHECKING:
    from ..expression.ddl.task import (
        SnowflakeAlterTaskExpression,
        SnowflakeCreateTaskExpression,
        SnowflakeDropTaskExpression,
        SnowflakeExecuteTaskExpression,
    )


class SnowflakeTaskMixin:
    """Mixin for Snowflake task (scheduler) support."""

    def supports_tasks(self) -> bool:
        """Snowflake supports tasks."""
        return True

    def format_create_task_statement(
        self, expr: "SnowflakeCreateTaskExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] TASK statement.

        Args:
            expr: :class:`SnowflakeCreateTaskExpression`.

        Returns:
            The formatted CREATE TASK SQL string.

        """
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        parts.append("TASK")
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.name))
        if expr.warehouse is not None:
            parts.append(
                f"WAREHOUSE = {self.format_identifier(expr.warehouse)}"
            )
        if expr.user_task_managed_initial_warehouse_size is not None:
            parts.append(
                "USER_TASK_MANAGED_INITIAL_WAREHOUSE_SIZE = "
                f"{self.format_identifier(expr.user_task_managed_initial_warehouse_size)}"
            )
        schedule = self.format_task_schedule(expr)
        if schedule:
            parts.append(schedule)
        if expr.allow_overlapping_execution is not None:
            parts.append(
                "ALLOW_OVERLAPPING_EXECUTION = "
                f"{str(bool(expr.allow_overlapping_execution)).upper()}"
            )
        if expr.comment is not None:
            parts.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        if expr.after:
            after = ", ".join(self.format_identifier(t) for t in expr.after)
            parts.append(f"AFTER {after}")
        if expr.when is not None:
            parts.append(f"WHEN {expr.when}")
        if expr.sql is not None:
            parts.extend(["AS", str(expr.sql)])
        return " ".join(parts)

    def format_alter_task_statement(
        self, expr: "SnowflakeAlterTaskExpression"
    ) -> str:
        """Format ALTER TASK statement.

        Emits ``RESUME`` / ``SUSPEND`` / ``ADD AFTER`` / ``REMOVE AFTER`` /
        ``SET ...`` based on :attr:`expr.mode`.

        Args:
            expr: :class:`SnowflakeAlterTaskExpression`.

        Returns:
            The formatted ALTER TASK SQL string.

        Raises:
            ValueError: ADD/REMOVE AFTER without ``after``, or SET with
                no property.
        """
        parts = ["ALTER TASK"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        mode = expr.mode
        if mode is SnowflakeAlterTaskMode.RESUME:
            parts.append("RESUME")
            return " ".join(parts)
        if mode is SnowflakeAlterTaskMode.SUSPEND:
            parts.append("SUSPEND")
            return " ".join(parts)
        if mode is SnowflakeAlterTaskMode.ADD_AFTER:
            if not expr.after:
                raise ValueError("ALTER TASK ADD AFTER requires tasks")
            after = ", ".join(self.format_identifier(t) for t in expr.after)
            parts.append(f"ADD AFTER {after}")
            return " ".join(parts)
        if mode is SnowflakeAlterTaskMode.REMOVE_AFTER:
            if not expr.after:
                raise ValueError("ALTER TASK REMOVE AFTER requires tasks")
            after = ", ".join(self.format_identifier(t) for t in expr.after)
            parts.append(f"REMOVE AFTER {after}")
            return " ".join(parts)
        options = []
        if expr.warehouse is not None:
            options.append(
                f"WAREHOUSE = {self.format_identifier(expr.warehouse)}"
            )
        schedule = self.format_task_schedule(expr)
        if schedule:
            options.append(schedule)
        if not options:
            raise ValueError("ALTER TASK SET requires at least one property")
        parts.append("SET")
        parts.extend(options)
        return " ".join(parts)

    def format_execute_task_statement(
        self, expr: "SnowflakeExecuteTaskExpression"
    ) -> str:
        """Format EXECUTE TASK statement.

        Args:
            expr: :class:`SnowflakeExecuteTaskExpression`.

        Returns:
            The formatted EXECUTE TASK SQL string.

        """
        parts = ["EXECUTE TASK", self.format_identifier(expr.name)]
        if expr.retry_last:
            parts.append("RETRY LAST")
        return " ".join(parts)

    def format_drop_task_statement(
        self, expr: "SnowflakeDropTaskExpression"
    ) -> str:
        """Format DROP TASK statement.

        Args:
            expr: :class:`SnowflakeDropTaskExpression`.

        Returns:
            The formatted DROP TASK SQL string.

        """
        parts = ["DROP TASK"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts)

    def format_task_schedule(self, expr: Any) -> Optional[str]:
        """Render a SCHEDULE clause from interval or cron spec."""
        if expr.using_cron is not None:
            cron = f"USING CRON {expr.using_cron}"
            if expr.timezone is not None:
                cron += f" {self._escape_sql_string(str(expr.timezone))}"
            return f"SCHEDULE = '{cron}'"
        if expr.schedule is not None:
            value = self._escape_sql_string(str(expr.schedule))
            return f"SCHEDULE = '{value}'"
        return None
