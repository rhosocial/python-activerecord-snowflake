# src/rhosocial/activerecord/backend/impl/snowflake/protocols/stage.py
"""Snowflake stage (data staging area) protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake stages are locations where data files are stored for
loading/unloading:
- Internal stages: Snowflake-managed storage
- External stages: Cloud storage (S3, Azure, GCS)
- CREATE/ALTER/DROP STAGE: Stage object DDL
- COPY INTO: Load data from stages into tables, or unload into stages

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-stage
- https://docs.snowflake.com/en/sql-reference/sql/copy-into-table
"""
from typing import Protocol, Tuple, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.stage import (
        SnowflakeAlterStageExpression,
        SnowflakeCopyIntoExpression,
        SnowflakeCreateStageExpression,
        SnowflakeDropStageExpression,
    )


@runtime_checkable
class SnowflakeStageSupport(Protocol):
    """Snowflake stage (data staging area) protocol."""

    def supports_stages(self) -> bool:
        """Whether stage operations are supported."""
        ...

    def format_copy_into_statement(
        self, expr: "SnowflakeCopyIntoExpression"
    ) -> Tuple[str, tuple]:
        """Format a full COPY INTO statement (load or unload)."""
        ...

    def format_create_stage_statement(
        self, expr: "SnowflakeCreateStageExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE STAGE statement."""
        ...

    def format_alter_stage_statement(
        self, expr: "SnowflakeAlterStageExpression"
    ) -> Tuple[str, tuple]:
        """Format ALTER STAGE ... SET statement."""
        ...

    def format_drop_stage_statement(
        self, expr: "SnowflakeDropStageExpression"
    ) -> Tuple[str, tuple]:
        """Format DROP STAGE statement."""
        ...

    def format_copy_into_load(
        self, expr: "SnowflakeCopyIntoExpression"
    ) -> Tuple[str, tuple]:
        """Format COPY INTO <table> FROM <stage> (load)."""
        ...

    def format_copy_into_unload(
        self, expr: "SnowflakeCopyIntoExpression"
    ) -> Tuple[str, tuple]:
        """Format COPY INTO <stage> FROM <table> (unload)."""
        ...
