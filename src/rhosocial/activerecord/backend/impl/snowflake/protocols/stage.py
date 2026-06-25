# src/rhosocial/activerecord/backend/impl/snowflake/protocols/stage.py
"""Snowflake stage (data staging area) protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake stages are locations where data files are stored for
loading/unloading:
- Internal stages: Snowflake-managed storage
- External stages: Cloud storage (S3, Azure, GCS)
- PUT/GET: Upload/download files to/from stages
- COPY INTO: Load data from stages into tables

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-stage
- https://docs.snowflake.com/en/sql-reference/sql/copy-into-table
"""
from typing import Optional, Protocol, runtime_checkable


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