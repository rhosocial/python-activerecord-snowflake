# src/rhosocial/activerecord/backend/impl/snowflake/mixins/stage.py
"""SnowflakeStageMixin — stage (data staging area) support."""

from typing import Tuple, TYPE_CHECKING

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

    def format_copy_into_statement(
        self, expr: "SnowflakeCopyIntoExpression"
    ) -> Tuple[str, tuple]:
        """Format a full COPY INTO statement (load or unload).

        Args:
            expr: :class:`SnowflakeCopyIntoExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        if expr.mode is SnowflakeCopyIntoMode.UNLOAD:
            return self.format_copy_into_unload(expr)
        return self.format_copy_into_load(expr)

    def format_copy_into_load(
        self, expr: "SnowflakeCopyIntoExpression"
    ) -> Tuple[str, tuple]:
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
        if expr.file_format is not None:
            ff = expr.file_format
            if isinstance(ff, dict):
                items = []
                for key, value in ff.items():
                    if isinstance(value, str):
                        items.append(f"{key} = {value}")
                    else:
                        items.append(f"{key} = {str(value).upper()}")
                parts.append(f"FILE_FORMAT = ({' '.join(items)})")
            else:
                parts.append(f"FILE_FORMAT = ({ff})")
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
        return " ".join(parts), ()

    def format_copy_into_unload(
        self, expr: "SnowflakeCopyIntoExpression"
    ) -> Tuple[str, tuple]:
        """Format COPY INTO @<stage> FROM <table> (unload direction)."""
        parts = [f"COPY INTO @{expr.stage} FROM {expr.table}"]
        if expr.partition_by:
            cols = ", ".join(expr.partition_by)
            parts.append(f"PARTITION BY ({cols})")
        if expr.file_format is not None:
            ff = expr.file_format
            if isinstance(ff, dict):
                items = []
                for key, value in ff.items():
                    if isinstance(value, str):
                        items.append(f"{key} = {value}")
                    else:
                        items.append(f"{key} = {str(value).upper()}")
                parts.append(f"FILE_FORMAT = ({' '.join(items)})")
            else:
                parts.append(f"FILE_FORMAT = ({ff})")
        if expr.header is not None:
            parts.append(f"HEADER = {str(bool(expr.header)).upper()}")
        if expr.overwrite is not None:
            parts.append(f"OVERWRITE = {str(bool(expr.overwrite)).upper()}")
        if expr.single is not None:
            parts.append(f"SINGLE = {str(bool(expr.single)).upper()}")
        return " ".join(parts), ()

    def format_create_stage_statement(
        self, expr: "SnowflakeCreateStageExpression"
    ) -> Tuple[str, tuple]:
        """Format CREATE STAGE statement.

        Args:
            expr: :class:`SnowflakeCreateStageExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

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
            enc = expr.encryption
            if isinstance(enc, dict):
                items = []
                for key, value in enc.items():
                    if isinstance(value, str):
                        items.append(
                            f"{key} = '{self._escape_sql_string(value)}'"
                        )
                    else:
                        items.append(f"{key} = {str(value).upper()}")
                options.append(f"ENCRYPTION = ({' '.join(items)})")
            else:
                options.append(f"ENCRYPTION = ({enc})")
        if expr.directory is True:
            options.append("DIRECTORY = (ENABLE = TRUE)")
        if options:
            parts.extend(options)
        return " ".join(parts), ()

    def format_alter_stage_statement(
        self, expr: "SnowflakeAlterStageExpression"
    ) -> Tuple[str, tuple]:
        """Format ALTER STAGE ... SET statement.

        Args:
            expr: :class:`SnowflakeAlterStageExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

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
        return " ".join(parts), ()

    def format_drop_stage_statement(
        self, expr: "SnowflakeDropStageExpression"
    ) -> Tuple[str, tuple]:
        """Format DROP STAGE statement.

        Args:
            expr: :class:`SnowflakeDropStageExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        parts = ["DROP STAGE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(self.format_identifier(expr.name))
        return " ".join(parts), ()
