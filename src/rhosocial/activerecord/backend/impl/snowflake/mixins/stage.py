# src/rhosocial/activerecord/backend/impl/snowflake/mixins/stage.py
"""SnowflakeStageMixin — stage (data staging area) support."""

from typing import Any, Optional, TYPE_CHECKING

from ..expression.ddl.stage import SnowflakeCopyIntoMode

if TYPE_CHECKING:
    from ..expression.ddl.stage import (
        SnowflakeAlterStageExpression,
        SnowflakeCopyIntoExpression,
        SnowflakeCreateStageExpression,
        SnowflakeDropStageExpression,
    )


class SnowflakeStageMixin:
    """Mixin for Snowflake stage (data staging area) support."""

    def supports_stages(self) -> bool:
        """Snowflake supports stages."""
        return True

    def format_copy_into_table(
        self, table: str, stage: str, file_format: Optional[str] = None
    ) -> str:
        """Format COPY INTO table FROM stage statement.

        Backwards-compatible convenience wrapper kept for existing callers;
        prefer :meth:`format_copy_into_statement` for full option support.
        """
        sql = f"COPY INTO {table} FROM @{stage}"
        if file_format:
            sql += f" FILE_FORMAT = ({file_format})"
        return sql

    def format_copy_into_statement(
        self, expr: "SnowflakeCopyIntoExpression"
    ) -> str:
        """Format a full COPY INTO statement (load or unload).

        Args:
            expr: :class:`SnowflakeCopyIntoExpression`.

        Returns:
            The formatted COPY INTO SQL string.

        """
        if expr.mode is SnowflakeCopyIntoMode.UNLOAD:
            return self.format_copy_into_unload(expr)
        return self.format_copy_into_load(expr)

    def format_copy_into_load(self, expr: Any) -> str:
        """Format COPY INTO <table> FROM @<stage> (load direction)."""
        parts = [f"COPY INTO {expr.table} FROM @{expr.stage}"]
        if expr.files:
            files = ", ".join(
                f"'{self._escape_sql_string(name)}'" for name in expr.files
            )
            parts.append(f"FILES = ({files})")
        if expr.pattern is not None:
            parts.append(
                f"PATTERN = '{self._escape_sql_string(expr.pattern)}'"
            )
        file_format_clause = self.format_file_format(expr.file_format)
        if file_format_clause:
            parts.append(file_format_clause)
        if expr.on_error is not None:
            parts.append(
                f"ON_ERROR = '{self._escape_sql_string(expr.on_error)}'"
            )
        if expr.force is not None:
            parts.append(f"FORCE = {str(bool(expr.force)).upper()}")
        if expr.purge is not None:
            parts.append(f"PURGE = {str(bool(expr.purge)).upper()}")
        if expr.validation_mode is not None:
            parts.append(
                f"VALIDATION_MODE = "
                f"'{self._escape_sql_string(expr.validation_mode)}'"
            )
        return " ".join(parts)

    def format_copy_into_unload(self, expr: Any) -> str:
        """Format COPY INTO @<stage> FROM <table> (unload direction)."""
        parts = [f"COPY INTO @{expr.stage} FROM {expr.table}"]
        if expr.partition_by:
            cols = ", ".join(expr.partition_by)
            parts.append(f"PARTITION BY ({cols})")
        file_format_clause = self.format_file_format(expr.file_format)
        if file_format_clause:
            parts.append(file_format_clause)
        if expr.header is not None:
            parts.append(f"HEADER = {str(bool(expr.header)).upper()}")
        if expr.overwrite is not None:
            parts.append(f"OVERWRITE = {str(bool(expr.overwrite)).upper()}")
        if expr.single is not None:
            parts.append(f"SINGLE = {str(bool(expr.single)).upper()}")
        return " ".join(parts)

    def format_file_format(self, file_format: Optional[Any]) -> Optional[str]:
        """Render a FILE_FORMAT clause from a string fragment or dict.

        A dict is rendered as ``FILE_FORMAT = (KEY = value ...)`` with values
        emitted verbatim (identifiers such as ``FORMAT_NAME = my_fmt`` and
        type names such as ``TYPE = CSV`` are left unquoted; quote a value
        yourself when a string literal is required).
        """
        if file_format is None:
            return None
        if isinstance(file_format, dict):
            items = []
            for key, value in file_format.items():
                if isinstance(value, str):
                    items.append(f"{key} = {value}")
                else:
                    items.append(f"{key} = {str(value).upper()}")
            return f"FILE_FORMAT = ({' '.join(items)})"
        return f"FILE_FORMAT = ({file_format})"

    def format_create_stage_statement(
        self, expr: "SnowflakeCreateStageExpression"
    ) -> str:
        """Format CREATE STAGE statement.

        Args:
            expr: :class:`SnowflakeCreateStageExpression`.

        Returns:
            The formatted CREATE STAGE SQL string.

        """
        parts = ["CREATE"]
        if expr.or_replace:
            parts.append("OR REPLACE")
        if expr.temporary:
            parts.append("TEMPORARY")
        parts.append("STAGE")
        parts.append(self.format_identifier(expr.name))
        options = []
        if expr.url is not None:
            options.append(f"URL = '{self._escape_sql_string(expr.url)}'")
        if expr.storage_integration is not None:
            options.append(
                f"STORAGE_INTEGRATION = "
                f"{self.format_identifier(expr.storage_integration)}"
            )
        if expr.file_format is not None:
            options.append(
                f"FILE_FORMAT = {self.format_identifier(expr.file_format)}"
            )
        if expr.encryption is not None:
            encryption = self.format_encryption(expr.encryption)
            if encryption:
                options.append(encryption)
        if expr.directory is True:
            options.append("DIRECTORY = (ENABLE = TRUE)")
        if options:
            parts.extend(options)
        return " ".join(parts)

    def format_alter_stage_statement(
        self, expr: "SnowflakeAlterStageExpression"
    ) -> str:
        """Format ALTER STAGE ... SET statement.

        Args:
            expr: :class:`SnowflakeAlterStageExpression`.

        Returns:
            The formatted ALTER STAGE SQL string.

        Raises:
            ValueError: when no ``SET`` property is specified.

        """
        options = []
        if expr.file_format is not None:
            options.append(
                f"FILE_FORMAT = {self.format_identifier(expr.file_format)}"
            )
        if expr.url is not None:
            options.append(f"URL = '{self._escape_sql_string(expr.url)}'")
        if expr.storage_integration is not None:
            options.append(
                f"STORAGE_INTEGRATION = "
                f"{self.format_identifier(expr.storage_integration)}"
            )
        if expr.comment is not None:
            options.append(
                f"COMMENT = '{self._escape_sql_string(expr.comment)}'"
            )
        if not options:
            raise ValueError("ALTER STAGE SET requires at least one property")
        parts = ["ALTER STAGE", self.format_identifier(expr.name), "SET"]
        parts.extend(options)
        return " ".join(parts)

    def format_drop_stage_statement(
        self, expr: "SnowflakeDropStageExpression"
    ) -> str:
        """Format DROP STAGE statement.

        Args:
            expr: :class:`SnowflakeDropStageExpression`.

        Returns:
            The formatted DROP STAGE SQL string.

        """
        parts = ["DROP STAGE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts)

    def format_list_stage(self, stage: str) -> str:
        """Format LIST @stage statement.

        Args:
            stage: Stage name (without ``@`` prefix).

        Returns:
            The formatted LIST statement string.

        """
        return f"LIST @{stage}"

    def format_remove_stage(self, stage: str, path: str) -> str:
        """Format REMOVE @stage/path statement.

        Args:
            stage: Stage name (without ``@`` prefix).
            path: Path of the file to remove inside the stage.

        Returns:
            The formatted REMOVE statement string.

        """
        return f"REMOVE @{stage}/{path}"

    def format_encryption(self, encryption: Any) -> str:
        """Render an ENCRYPTION clause from a string fragment or dict.

        A dict is rendered as ``ENCRYPTION = (KEY = 'value' ...)`` with string
        values quoted (e.g. ``TYPE = 'SSE_S3'``).
        """
        if isinstance(encryption, dict):
            items = []
            for key, value in encryption.items():
                if isinstance(value, str):
                    items.append(f"{key} = '{self._escape_sql_string(value)}'")
                else:
                    items.append(f"{key} = {str(value).upper()}")
            return f"ENCRYPTION = ({' '.join(items)})"
        return f"ENCRYPTION = ({encryption})"
