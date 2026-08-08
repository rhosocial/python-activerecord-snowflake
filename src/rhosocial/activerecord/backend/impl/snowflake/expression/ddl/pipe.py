# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/pipe.py
"""Snowflake PIPE expressions.

Pipes (Snowpipe) continuously load data as files land in a stage.
These expressions generate CREATE / ALTER / DROP PIPE statements,
including AUTO_INGEST mode and the REFRESH / PAUSE / RESUME controls.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- CREATE PIPE: https://docs.snowflake.com/en/sql-reference/sql/create-pipe
- ALTER PIPE:  https://docs.snowflake.com/en/sql-reference/sql/alter-pipe
- DROP PIPE:   https://docs.snowflake.com/en/sql-reference/sql/drop-pipe
"""
from enum import Enum
from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeAlterPipeMode",
    "SnowflakeCreatePipeExpression",
    "SnowflakeAlterPipeExpression",
    "SnowflakeDropPipeExpression",
]


class SnowflakeAlterPipeMode(Enum):
    """ALTER PIPE action modes.

    REFRESH: manually refresh the pipe to load staged files.
    SET:     change pipe properties (pause flag, comment).
    PAUSE:   set ``PIPE_EXECUTION_PAUSED = TRUE``.
    RESUME:  set ``PIPE_EXECUTION_PAUSED = FALSE``.
    """

    REFRESH = "REFRESH"
    SET = "SET"
    PAUSE = "PAUSE"
    RESUME = "RESUME"


class SnowflakeCreatePipeExpression(BaseExpression):
    """Snowflake CREATE [OR REPLACE] PIPE statement expression.

    Attributes:
        name: Pipe name.
        or_replace: Emit ``OR REPLACE``.
        if_not_exists: Emit ``IF NOT EXISTS``.
        auto_ingest: ``AUTO_INGEST`` bool (notification-based ingestion).
        error_integration: ``ERROR_INTEGRATION`` name.
        aws_sns_topic: ``AWS_SNS_TOPIC`` string literal.
        integration: ``INTEGRATION`` string literal.
        comment: ``COMMENT`` string literal.
        copy_sql: ``COPY INTO`` statement fragment (pipe body).
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        or_replace: bool = False,
        if_not_exists: bool = False,
        auto_ingest: Optional[bool] = None,
        error_integration: Optional[str] = None,
        aws_sns_topic: Optional[str] = None,
        integration: Optional[str] = None,
        comment: Optional[str] = None,
        copy_sql: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.or_replace = or_replace
        self.if_not_exists = if_not_exists
        self.auto_ingest = auto_ingest
        self.error_integration = error_integration
        self.aws_sns_topic = aws_sns_topic
        self.integration = integration
        self.comment = comment
        self.copy_sql = copy_sql

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE PIPE SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_create_pipe_statement(self), ()


class SnowflakeAlterPipeExpression(BaseExpression):
    """Snowflake ALTER PIPE statement expression.

    The ``mode`` selects one of the ALTER PIPE forms: ``REFRESH``,
    ``SET``, ``PAUSE`` or ``RESUME``.

    Attributes:
        name: Pipe name.
        mode: :class:`SnowflakeAlterPipeMode`.
        if_exists: Emit ``IF EXISTS``.
        modified_after: ``MODIFIED_AFTER => ...`` for ``REFRESH``.
        pipe_execution_paused: ``PIPE_EXECUTION_PAUSED`` for ``SET``.
        comment: ``COMMENT`` string literal for ``SET``.

    Raises:
        ValueError: SET with no property.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        mode: SnowflakeAlterPipeMode = SnowflakeAlterPipeMode.REFRESH,
        if_exists: bool = False,
        modified_after: Optional[str] = None,
        pipe_execution_paused: Optional[bool] = None,
        comment: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.mode = mode
        self.if_exists = if_exists
        self.modified_after = modified_after
        self.pipe_execution_paused = pipe_execution_paused
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate ALTER PIPE SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_alter_pipe_statement(self), ()


class SnowflakeDropPipeExpression(BaseExpression):
    """Snowflake DROP PIPE statement expression.

    Attributes:
        name: Pipe name.
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
        """Generate DROP PIPE SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_drop_pipe_statement(self), ()
