# src/rhosocial/activerecord/backend/impl/snowflake/protocols/stage.py
"""Snowflake stage (data staging area) protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake stages are locations where data files are stored for
loading/unloading:
- Internal stages: Snowflake-managed storage
- External stages: Cloud storage (S3, Azure, GCS)
- CREATE/ALTER/DROP STAGE: Stage object DDL
- LIST/REMOVE: Inspect and delete files inside a stage
- COPY INTO: Load data from stages into tables, or unload into stages

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-stage
- https://docs.snowflake.com/en/sql-reference/sql/copy-into-table
"""
from typing import Any, Optional, Protocol, runtime_checkable, TYPE_CHECKING

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

    def format_copy_into_table(
        self, table: str, stage: str, file_format: Optional[str] = None
    ) -> str:
        """Format COPY INTO table FROM stage statement."""
        ...

    def format_copy_into_statement(
        self, expr: "SnowflakeCopyIntoExpression"
    ) -> str:
        """Format a full COPY INTO statement (load or unload)."""
        ...

    def format_create_stage_statement(
        self, expr: "SnowflakeCreateStageExpression"
    ) -> str:
        """Format CREATE STAGE statement."""
        ...

    def format_alter_stage_statement(
        self, expr: "SnowflakeAlterStageExpression"
    ) -> str:
        """Format ALTER STAGE ... SET statement."""
        ...

    def format_drop_stage_statement(
        self, expr: "SnowflakeDropStageExpression"
    ) -> str:
        """Format DROP STAGE statement."""
        ...

    def format_list_stage(self, stage: str) -> str:
        """Format LIST @stage statement."""
        ...

    def format_remove_stage(self, stage: str, path: str) -> str:
        """Format REMOVE @stage/path statement."""
        ...

    def format_copy_into_load(self, expr: Any) -> str:
        """Format COPY INTO <table> FROM <stage> (load)."""
        ...

    def format_copy_into_unload(self, expr: Any) -> str:
        """Format COPY INTO <stage> FROM <table> (unload)."""
        ...

    def format_file_format(self, file_format: Optional[Any]) -> Optional[str]:
        """Format FILE_FORMAT clause."""
        ...

    def format_encryption(self, encryption: Any) -> str:
        """Format ENCRYPTION option."""
        ...
