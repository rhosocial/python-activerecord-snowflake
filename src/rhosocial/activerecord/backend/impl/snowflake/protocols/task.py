# src/rhosocial/activerecord/backend/impl/snowflake/protocols/task.py
"""Snowflake task (scheduled SQL) protocol.

Feature Source: Snowflake native (not SQL standard)

Tasks run scheduled SQL statements. They support interval or cron-based
``SCHEDULE`` values, ``WHEN`` gating conditions (e.g. ``SYSTEM$STREAM_HAS_DATA``)
and ``AFTER`` predecessor dependencies. Managed via CREATE / ALTER / EXECUTE /
DROP TASK statements.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-task
- https://docs.snowflake.com/en/sql-reference/sql/alter-task
- https://docs.snowflake.com/en/sql-reference/sql/execute-task
"""
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.task import (
        SnowflakeAlterTaskExpression,
        SnowflakeCreateTaskExpression,
        SnowflakeDropTaskExpression,
        SnowflakeExecuteTaskExpression,
    )


@runtime_checkable
class SnowflakeTaskSupport(Protocol):
    """Snowflake task (scheduled SQL) protocol."""

    def supports_tasks(self) -> bool:
        """Whether tasks are supported."""
        ...

    def format_create_task_statement(
        self, expr: "SnowflakeCreateTaskExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] TASK statement."""
        ...

    def format_alter_task_statement(
        self, expr: "SnowflakeAlterTaskExpression"
    ) -> str:
        """Format ALTER TASK statement (RESUME / SUSPEND / AFTER / SET)."""
        ...

    def format_execute_task_statement(
        self, expr: "SnowflakeExecuteTaskExpression"
    ) -> str:
        """Format EXECUTE TASK statement."""
        ...

    def format_drop_task_statement(
        self, expr: "SnowflakeDropTaskExpression"
    ) -> str:
        """Format DROP TASK statement."""
        ...
