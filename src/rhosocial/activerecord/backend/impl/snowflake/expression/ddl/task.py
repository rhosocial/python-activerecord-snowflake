# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/task.py
"""Snowflake TASK expressions.

Tasks execute scheduled SQL statements (Snowflake's job scheduler).
They support interval or cron-based schedules, ``WHEN`` gating conditions
(such as ``SYSTEM$STREAM_HAS_DATA``) and ``AFTER`` predecessor dependencies
for DAG-style pipelines. These expressions generate CREATE / ALTER /
EXECUTE / DROP TASK statements.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- CREATE TASK:   https://docs.snowflake.com/en/sql-reference/sql/create-task
- ALTER TASK:    https://docs.snowflake.com/en/sql-reference/sql/alter-task
- EXECUTE TASK:  https://docs.snowflake.com/en/sql-reference/sql/execute-task
- DROP TASK:     https://docs.snowflake.com/en/sql-reference/sql/drop-task
"""
from enum import Enum
from typing import List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeAlterTaskMode",
    "SnowflakeCreateTaskExpression",
    "SnowflakeAlterTaskExpression",
    "SnowflakeExecuteTaskExpression",
    "SnowflakeDropTaskExpression",
]


class SnowflakeAlterTaskMode(Enum):
    """ALTER TASK action modes.

    RESUME:      resume a suspended task.
    SUSPEND:     suspend a running task.
    ADD_AFTER:   add predecessor task dependencies.
    REMOVE_AFTER: remove predecessor task dependencies.
    SET:         change task properties (warehouse, schedule).
    """

    RESUME = "RESUME"
    SUSPEND = "SUSPEND"
    ADD_AFTER = "ADD AFTER"
    REMOVE_AFTER = "REMOVE AFTER"
    SET = "SET"


class SnowflakeCreateTaskExpression(BaseExpression):
    """Snowflake CREATE [OR REPLACE] TASK statement expression.

    Attributes:
        name: Task name.
        or_replace: Emit ``OR REPLACE``.
        if_not_exists: Emit ``IF NOT EXISTS``.
        warehouse: ``WAREHOUSE`` name.
        user_task_managed_initial_warehouse_size:
            ``USER_TASK_MANAGED_INITIAL_WAREHOUSE_SIZE``.
        schedule: Interval ``SCHEDULE`` value (e.g. ``'5 MINUTE'``).
        using_cron: ``USING CRON`` expression inside ``SCHEDULE``.
        timezone: Cron timezone (e.g. ``'UTC'``).
        allow_overlapping_execution: ``ALLOW_OVERLAPPING_EXECUTION`` bool.
        comment: ``COMMENT`` string literal.
        after: List of predecessor task names for ``AFTER``.
        when: ``WHEN`` boolean condition fragment.
        sql: Task body SQL.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        or_replace: bool = False,
        if_not_exists: bool = False,
        warehouse: Optional[str] = None,
        user_task_managed_initial_warehouse_size: Optional[str] = None,
        schedule: Optional[str] = None,
        using_cron: Optional[str] = None,
        timezone: Optional[str] = None,
        allow_overlapping_execution: Optional[bool] = None,
        comment: Optional[str] = None,
        after: Optional[List[str]] = None,
        when: Optional[str] = None,
        sql: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.or_replace = or_replace
        self.if_not_exists = if_not_exists
        self.warehouse = warehouse
        self.user_task_managed_initial_warehouse_size = (
            user_task_managed_initial_warehouse_size
        )
        self.schedule = schedule
        self.using_cron = using_cron
        self.timezone = timezone
        self.allow_overlapping_execution = allow_overlapping_execution
        self.comment = comment
        self.after = after
        self.when = when
        self.sql = sql

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE TASK SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_create_task_statement(self), ()


class SnowflakeAlterTaskExpression(BaseExpression):
    """Snowflake ALTER TASK statement expression.

    The ``mode`` selects one of the ALTER TASK forms: ``RESUME``,
    ``SUSPEND``, ``ADD AFTER``, ``REMOVE AFTER`` or ``SET``.

    Attributes:
        name: Task name.
        mode: :class:`SnowflakeAlterTaskMode`.
        if_exists: Emit ``IF EXISTS``.
        after: Predecessor task names for ``ADD AFTER`` / ``REMOVE AFTER``.
        warehouse: ``WAREHOUSE`` for ``SET``.
        schedule: Interval ``SCHEDULE`` for ``SET``.
        using_cron: ``USING CRON`` expression for ``SET``.
        timezone: Cron timezone for ``SET``.

    Raises:
        ValueError: ADD/REMOVE AFTER without ``after``, or SET with no property.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        mode: SnowflakeAlterTaskMode = SnowflakeAlterTaskMode.RESUME,
        if_exists: bool = False,
        after: Optional[List[str]] = None,
        warehouse: Optional[str] = None,
        schedule: Optional[str] = None,
        using_cron: Optional[str] = None,
        timezone: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.mode = mode
        self.if_exists = if_exists
        self.after = after
        self.warehouse = warehouse
        self.schedule = schedule
        self.using_cron = using_cron
        self.timezone = timezone

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate ALTER TASK SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_alter_task_statement(self), ()


class SnowflakeExecuteTaskExpression(BaseExpression):
    """Snowflake EXECUTE TASK statement expression.

    Attributes:
        name: Task name.
        retry_last: Emit ``RETRY LAST``.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        retry_last: bool = False,
    ):
        super().__init__(dialect)
        self.name = name
        self.retry_last = retry_last

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate EXECUTE TASK SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_execute_task_statement(self), ()


class SnowflakeDropTaskExpression(BaseExpression):
    """Snowflake DROP TASK statement expression.

    Attributes:
        name: Task name.
        if_exists: Emit ``IF EXISTS``.
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
        """Generate DROP TASK SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_drop_task_statement(self), ()
