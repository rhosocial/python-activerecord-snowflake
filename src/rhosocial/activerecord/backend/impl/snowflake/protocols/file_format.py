# src/rhosocial/activerecord/backend/impl/snowflake/protocols/file_format.py
"""Snowflake file format protocol.

Feature Source: Snowflake native (not SQL standard)

File formats describe how staged files are parsed (CSV / JSON / AVRO /
ORC / PARQUET / XML). They are first-class objects managed via
CREATE / ALTER / DROP FILE FORMAT statements.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-file-format
"""
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.ddl.file_format import (
        SnowflakeAlterFileFormatExpression,
        SnowflakeCreateFileFormatExpression,
        SnowflakeDropFileFormatExpression,
    )


@runtime_checkable
class SnowflakeFileFormatSupport(Protocol):
    """Snowflake file format protocol."""

    def supports_file_formats(self) -> bool:
        """Whether named file formats are supported."""
        ...

    def format_create_file_format_statement(
        self, expr: "SnowflakeCreateFileFormatExpression"
    ) -> str:
        """Format CREATE [OR REPLACE] FILE FORMAT statement."""
        ...

    def format_alter_file_format_statement(
        self, expr: "SnowflakeAlterFileFormatExpression"
    ) -> str:
        """Format ALTER FILE FORMAT ... SET statement."""
        ...

    def format_drop_file_format_statement(
        self, expr: "SnowflakeDropFileFormatExpression"
    ) -> str:
        """Format DROP FILE FORMAT statement."""
        ...
