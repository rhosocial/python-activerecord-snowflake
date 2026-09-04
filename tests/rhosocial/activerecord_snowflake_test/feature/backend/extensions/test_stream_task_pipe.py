# tests/rhosocial/activerecord_snowflake_test/feature/backend/extensions/test_stream_task_pipe.py
"""Tests for Snowflake STREAM / TASK / PIPE DDL support.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakePipeSupport,
    SnowflakeStreamSupport,
    SnowflakeTaskSupport,
)
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeAlterPipeExpression,
    SnowflakeAlterPipeMode,
    SnowflakeAlterTaskExpression,
    SnowflakeAlterTaskMode,
    SnowflakeCreatePipeExpression,
    SnowflakeCreateStreamExpression,
    SnowflakeCreateTaskExpression,
    SnowflakeDropPipeExpression,
    SnowflakeDropStreamExpression,
    SnowflakeDropTaskExpression,
    SnowflakeExecuteTaskExpression,
    SnowflakeStreamObjectType,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeStreamProtocol:
    """Dialect satisfies isinstance checks for the stream protocol."""

    def test_dialect_is_stream_support(self, dialect):
        assert isinstance(dialect, SnowflakeStreamSupport)

    def test_supports_stream(self, dialect):
        assert dialect.supports_stream() is True


class TestSnowflakeCreateStream:
    """CREATE [OR REPLACE] STREAM statement generation."""

    def test_create_stream_basic(self, dialect):
        expr = SnowflakeCreateStreamExpression(
            dialect, "my_stream", object_name="t"
        )
        sql, params = expr.to_sql()
        assert sql == 'CREATE STREAM "my_stream" ON TABLE "t"'
        assert params == ()

    def test_create_stream_or_replace_append_only(self, dialect):
        expr = SnowflakeCreateStreamExpression(
            dialect,
            "my_stream",
            or_replace=True,
            object_type=SnowflakeStreamObjectType.TABLE,
            object_name="t",
            append_only=True,
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE OR REPLACE STREAM "my_stream" ON TABLE "t" '
            "APPEND_ONLY = TRUE"
        )

    def test_create_stream_insert_only_on_view(self, dialect):
        expr = SnowflakeCreateStreamExpression(
            dialect,
            "my_stream",
            object_type=SnowflakeStreamObjectType.VIEW,
            object_name="v",
            insert_only=True,
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE STREAM "my_stream" ON VIEW "v" INSERT_ONLY = TRUE'
        )

    def test_create_stream_on_external_table(self, dialect):
        expr = SnowflakeCreateStreamExpression(
            dialect,
            "my_stream",
            object_type=SnowflakeStreamObjectType.EXTERNAL_TABLE,
            object_name="et",
        )
        sql, _ = expr.to_sql()
        assert sql == 'CREATE STREAM "my_stream" ON EXTERNAL TABLE "et"'

    def test_create_stream_time_travel_at(self, dialect):
        expr = SnowflakeCreateStreamExpression(
            dialect,
            "my_stream",
            object_name="t",
            at=("TIMESTAMP", "2024-01-01 00:00:00"),
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "CREATE STREAM \"my_stream\" ON TABLE \"t\" "
            "AT(TIMESTAMP => '2024-01-01 00:00:00')"
        )

    def test_create_stream_time_travel_before_offset(self, dialect):
        expr = SnowflakeCreateStreamExpression(
            dialect,
            "my_stream",
            object_name="t",
            before=("OFFSET", 3600),
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE STREAM "my_stream" ON TABLE "t" BEFORE(OFFSET => 3600)'
        )

    def test_create_stream_requires_object_name(self, dialect):
        expr = SnowflakeCreateStreamExpression(dialect, "my_stream")
        with pytest.raises(ValueError):
            expr.to_sql()

    def test_drop_stream(self, dialect):
        expr = SnowflakeDropStreamExpression(dialect, "my_stream")
        sql, params = expr.to_sql()
        assert sql == 'DROP STREAM "my_stream"'
        assert params == ()

    def test_drop_stream_if_exists(self, dialect):
        expr = SnowflakeDropStreamExpression(dialect, "my_stream", if_exists=True)
        sql, _ = expr.to_sql()
        assert sql == 'DROP STREAM IF EXISTS "my_stream"'


class TestSnowflakeTaskProtocol:
    """Dialect satisfies isinstance checks for the task protocol."""

    def test_dialect_is_task_support(self, dialect):
        assert isinstance(dialect, SnowflakeTaskSupport)

    def test_supports_tasks(self, dialect):
        assert dialect.supports_tasks() is True


class TestSnowflakeCreateTask:
    """CREATE [OR REPLACE] TASK statement generation."""

    def test_create_task_basic(self, dialect):
        expr = SnowflakeCreateTaskExpression(
            dialect, "my_task", sql="INSERT INTO archive SELECT * FROM my_stream"
        )
        sql, params = expr.to_sql()
        assert sql == (
            'CREATE TASK "my_task" AS '
            "INSERT INTO archive SELECT * FROM my_stream"
        )
        assert params == ()

    def test_create_task_schedule_interval(self, dialect):
        expr = SnowflakeCreateTaskExpression(
            dialect,
            "my_task",
            warehouse="my_wh",
            schedule="5 MINUTE",
            sql="SELECT 1",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE TASK "my_task" WAREHOUSE = "my_wh" '
            "SCHEDULE = '5 MINUTE' AS SELECT 1"
        )

    def test_create_task_using_cron_with_timezone(self, dialect):
        expr = SnowflakeCreateTaskExpression(
            dialect,
            "my_task",
            using_cron="0 0 * * *",
            timezone="UTC",
            sql="SELECT 1",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE TASK "my_task" SCHEDULE = \'USING CRON 0 0 * * * UTC\' '
            "AS SELECT 1"
        )

    def test_create_task_when_condition(self, dialect):
        expr = SnowflakeCreateTaskExpression(
            dialect,
            "my_task",
            when="SYSTEM$STREAM_HAS_DATA('my_stream')",
            sql="INSERT INTO archive SELECT * FROM my_stream",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE TASK "my_task" WHEN SYSTEM$STREAM_HAS_DATA(\'my_stream\') '
            "AS INSERT INTO archive SELECT * FROM my_stream"
        )

    def test_create_task_after_dependencies(self, dialect):
        expr = SnowflakeCreateTaskExpression(
            dialect,
            "my_task",
            after=["another_task", "third_task"],
            sql="SELECT 1",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE TASK "my_task" AFTER "another_task", "third_task" '
            "AS SELECT 1"
        )

    def test_create_task_or_replace(self, dialect):
        expr = SnowflakeCreateTaskExpression(
            dialect, "my_task", or_replace=True, sql="SELECT 1"
        )
        sql, _ = expr.to_sql()
        assert sql == 'CREATE OR REPLACE TASK "my_task" AS SELECT 1'


class TestSnowflakeAlterTask:
    """ALTER TASK RESUME / SUSPEND / ADD AFTER / REMOVE AFTER generation."""

    def test_alter_task_resume(self, dialect):
        expr = SnowflakeAlterTaskExpression(
            dialect, "my_task", mode=SnowflakeAlterTaskMode.RESUME
        )
        sql, params = expr.to_sql()
        assert sql == 'ALTER TASK "my_task" RESUME'
        assert params == ()

    def test_alter_task_suspend(self, dialect):
        expr = SnowflakeAlterTaskExpression(
            dialect, "my_task", mode=SnowflakeAlterTaskMode.SUSPEND
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER TASK "my_task" SUSPEND'

    def test_alter_task_add_after(self, dialect):
        expr = SnowflakeAlterTaskExpression(
            dialect,
            "my_task",
            mode=SnowflakeAlterTaskMode.ADD_AFTER,
            after=["another_task"],
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER TASK "my_task" ADD AFTER "another_task"'

    def test_alter_task_remove_after(self, dialect):
        expr = SnowflakeAlterTaskExpression(
            dialect,
            "my_task",
            mode=SnowflakeAlterTaskMode.REMOVE_AFTER,
            after=["another_task"],
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER TASK "my_task" REMOVE AFTER "another_task"'

    def test_alter_task_set_warehouse(self, dialect):
        expr = SnowflakeAlterTaskExpression(
            dialect,
            "my_task",
            mode=SnowflakeAlterTaskMode.SET,
            warehouse="other_wh",
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER TASK "my_task" SET WAREHOUSE = "other_wh"'

    def test_alter_task_add_after_without_tasks_raises(self, dialect):
        expr = SnowflakeAlterTaskExpression(
            dialect, "my_task", mode=SnowflakeAlterTaskMode.ADD_AFTER
        )
        with pytest.raises(ValueError):
            expr.to_sql()

    def test_alter_task_set_without_property_raises(self, dialect):
        expr = SnowflakeAlterTaskExpression(
            dialect, "my_task", mode=SnowflakeAlterTaskMode.SET
        )
        with pytest.raises(ValueError):
            expr.to_sql()


class TestSnowflakeExecuteTask:
    """EXECUTE TASK statement generation."""

    def test_execute_task(self, dialect):
        expr = SnowflakeExecuteTaskExpression(dialect, "my_task")
        sql, params = expr.to_sql()
        assert sql == 'EXECUTE TASK "my_task"'
        assert params == ()

    def test_execute_task_retry_last(self, dialect):
        expr = SnowflakeExecuteTaskExpression(dialect, "my_task", retry_last=True)
        sql, _ = expr.to_sql()
        assert sql == 'EXECUTE TASK "my_task" RETRY LAST'

    def test_drop_task(self, dialect):
        expr = SnowflakeDropTaskExpression(dialect, "my_task")
        sql, _ = expr.to_sql()
        assert sql == 'DROP TASK "my_task"'

    def test_drop_task_if_exists(self, dialect):
        expr = SnowflakeDropTaskExpression(dialect, "my_task", if_exists=True)
        sql, _ = expr.to_sql()
        assert sql == 'DROP TASK IF EXISTS "my_task"'


class TestSnowflakePipeProtocol:
    """Dialect satisfies isinstance checks for the pipe protocol."""

    def test_dialect_is_pipe_support(self, dialect):
        assert isinstance(dialect, SnowflakePipeSupport)

    def test_supports_pipes(self, dialect):
        assert dialect.supports_pipes() is True


class TestSnowflakeCreatePipe:
    """CREATE [OR REPLACE] PIPE statement generation."""

    def test_create_pipe_basic(self, dialect):
        expr = SnowflakeCreatePipeExpression(
            dialect, "my_pipe", copy_sql="COPY INTO t FROM @stage"
        )
        sql, params = expr.to_sql()
        assert sql == 'CREATE PIPE "my_pipe" AS COPY INTO t FROM @stage'
        assert params == ()

    def test_create_pipe_auto_ingest(self, dialect):
        expr = SnowflakeCreatePipeExpression(
            dialect,
            "my_pipe",
            or_replace=True,
            auto_ingest=True,
            copy_sql="COPY INTO t FROM @stage",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE OR REPLACE PIPE "my_pipe" AUTO_INGEST = TRUE '
            "AS COPY INTO t FROM @stage"
        )

    def test_create_pipe_error_integration(self, dialect):
        expr = SnowflakeCreatePipeExpression(
            dialect,
            "my_pipe",
            error_integration="my_err_int",
            copy_sql="COPY INTO t FROM @stage",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE PIPE "my_pipe" ERROR_INTEGRATION = "my_err_int" '
            "AS COPY INTO t FROM @stage"
        )

    def test_create_pipe_requires_copy_sql(self, dialect):
        expr = SnowflakeCreatePipeExpression(dialect, "my_pipe")
        with pytest.raises(ValueError):
            expr.to_sql()


class TestSnowflakeAlterPipe:
    """ALTER PIPE REFRESH / SET / PAUSE / RESUME generation."""

    def test_alter_pipe_refresh(self, dialect):
        expr = SnowflakeAlterPipeExpression(
            dialect, "my_pipe", mode=SnowflakeAlterPipeMode.REFRESH
        )
        sql, params = expr.to_sql()
        assert sql == 'ALTER PIPE "my_pipe" REFRESH'
        assert params == ()

    def test_alter_pipe_set_paused(self, dialect):
        expr = SnowflakeAlterPipeExpression(
            dialect,
            "my_pipe",
            mode=SnowflakeAlterPipeMode.SET,
            pipe_execution_paused=True,
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'ALTER PIPE "my_pipe" SET PIPE_EXECUTION_PAUSED = TRUE'
        )

    def test_alter_pipe_pause(self, dialect):
        expr = SnowflakeAlterPipeExpression(
            dialect, "my_pipe", mode=SnowflakeAlterPipeMode.PAUSE
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER PIPE "my_pipe" SET PIPE_EXECUTION_PAUSED = TRUE'

    def test_alter_pipe_resume(self, dialect):
        expr = SnowflakeAlterPipeExpression(
            dialect, "my_pipe", mode=SnowflakeAlterPipeMode.RESUME
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER PIPE "my_pipe" SET PIPE_EXECUTION_PAUSED = FALSE'

    def test_alter_pipe_set_without_property_raises(self, dialect):
        expr = SnowflakeAlterPipeExpression(
            dialect, "my_pipe", mode=SnowflakeAlterPipeMode.SET
        )
        with pytest.raises(ValueError):
            expr.to_sql()

    def test_drop_pipe(self, dialect):
        expr = SnowflakeDropPipeExpression(dialect, "my_pipe")
        sql, _ = expr.to_sql()
        assert sql == 'DROP PIPE "my_pipe"'

    def test_drop_pipe_if_exists(self, dialect):
        expr = SnowflakeDropPipeExpression(dialect, "my_pipe", if_exists=True)
        sql, _ = expr.to_sql()
        assert sql == 'DROP PIPE IF EXISTS "my_pipe"'
