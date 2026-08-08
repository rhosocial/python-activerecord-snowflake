# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/stage.py
"""Snowflake STAGE and COPY INTO expressions.

Stages are locations (internal or external cloud storage) where data files
are stored for loading into / unloading from tables. These expressions
generate CREATE / ALTER / DROP STAGE statements plus the full COPY INTO
load / unload statement.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- CREATE STAGE:     https://docs.snowflake.com/en/sql-reference/sql/create-stage
- ALTER STAGE:      https://docs.snowflake.com/en/sql-reference/sql/alter-stage
- DROP STAGE:       https://docs.snowflake.com/en/sql-reference/sql/drop-stage
- COPY INTO (table): https://docs.snowflake.com/en/sql-reference/sql/copy-into-table
"""
from enum import Enum
from typing import Any, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeCopyIntoMode",
    "SnowflakeCreateStageExpression",
    "SnowflakeAlterStageExpression",
    "SnowflakeDropStageExpression",
    "SnowflakeCopyIntoExpression",
]


class SnowflakeCopyIntoMode(Enum):
    """COPY INTO direction modes.

    LOAD:   COPY INTO <table> FROM @<stage> — load data into a table.
    UNLOAD: COPY INTO @<stage> FROM <table> — unload data from a table.
    """

    LOAD = "LOAD"
    UNLOAD = "UNLOAD"


class SnowflakeCreateStageExpression(BaseExpression):
    """Snowflake CREATE STAGE statement expression.

    Attributes:
        name: Stage name.
        or_replace: Emit ``OR REPLACE``.
        temporary: Emit ``TEMPORARY`` (session-scoped stage).
        url: ``URL`` for external stages (e.g. ``'s3://bucket/path'``).
        storage_integration: ``STORAGE_INTEGRATION`` name.
        file_format: ``FILE_FORMAT`` object name.
        encryption: ``ENCRYPTION`` spec — string fragment (``"TYPE = 'SSE_S3'"``)
            or dict of ``{key: value}`` pairs.
        directory: When True, emit ``DIRECTORY = (ENABLE = TRUE)``.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        or_replace: bool = False,
        temporary: bool = False,
        url: Optional[str] = None,
        storage_integration: Optional[str] = None,
        file_format: Optional[str] = None,
        encryption: Optional[Any] = None,
        directory: Optional[bool] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.or_replace = or_replace
        self.temporary = temporary
        self.url = url
        self.storage_integration = storage_integration
        self.file_format = file_format
        self.encryption = encryption
        self.directory = directory

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE STAGE SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_create_stage_statement(self), ()


class SnowflakeAlterStageExpression(BaseExpression):
    """Snowflake ALTER STAGE statement expression.

    Only the ``SET`` form is emitted; properties not specified are left
    unchanged on the existing stage.

    Attributes:
        name: Stage name.
        file_format: ``FILE_FORMAT`` object name for ``SET``.
        url: ``URL`` for ``SET``.
        storage_integration: ``STORAGE_INTEGRATION`` name for ``SET``.
        comment: ``COMMENT`` string literal for ``SET``.

    Raises:
        ValueError: when no ``SET`` property is specified.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        file_format: Optional[str] = None,
        url: Optional[str] = None,
        storage_integration: Optional[str] = None,
        comment: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.file_format = file_format
        self.url = url
        self.storage_integration = storage_integration
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate ALTER STAGE SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_alter_stage_statement(self), ()


class SnowflakeDropStageExpression(BaseExpression):
    """Snowflake DROP STAGE statement expression.

    Attributes:
        name: Stage name.
        if_exists: Emit ``IF EXISTS`` (drop is a no-op notice if absent).
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
        """Generate DROP STAGE SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_drop_stage_statement(self), ()


class SnowflakeCopyIntoExpression(BaseExpression):
    """Snowflake COPY INTO statement expression (load or unload).

    ``mode`` selects the direction:

    - ``LOAD``: ``COPY INTO <table> FROM @<stage>`` with
      ``FILES`` / ``PATTERN`` / ``FILE_FORMAT`` / ``ON_ERROR`` / ``FORCE`` /
      ``PURGE`` / ``VALIDATION_MODE`` options.
    - ``UNLOAD``: ``COPY INTO @<stage> FROM <table>`` with
      ``PARTITION BY`` / ``FILE_FORMAT`` / ``HEADER`` / ``OVERWRITE`` /
      ``SINGLE`` options.

    Attributes:
        mode: :class:`SnowflakeCopyIntoMode`.
        table: Target (LOAD) or source (UNLOAD) table reference.
        stage: Source (LOAD) or target (UNLOAD) stage reference.
        files: ``FILES = ('f1', ...)`` list (LOAD only).
        pattern: ``PATTERN = 'regex'`` (LOAD only).
        file_format: ``FILE_FORMAT = (...)`` spec — string fragment
            (e.g. ``"TYPE = 'CSV'"``) or dict of ``{key: value}`` pairs
            (e.g. ``{"FORMAT_NAME": "my_fmt"}``).
        on_error: ``ON_ERROR = '...'`` (LOAD only).
        force: ``FORCE = TRUE/FALSE`` (LOAD only).
        purge: ``PURGE = TRUE/FALSE`` (LOAD only).
        validation_mode: ``VALIDATION_MODE = '...'`` (LOAD only).
        partition_by: ``PARTITION BY (...)` column list (UNLOAD only).
        header: ``HEADER = TRUE/FALSE`` (UNLOAD only).
        overwrite: ``OVERWRITE = TRUE/FALSE`` (UNLOAD only).
        single: ``SINGLE = TRUE/FALSE`` (UNLOAD only).
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        mode: SnowflakeCopyIntoMode = SnowflakeCopyIntoMode.LOAD,
        table: Optional[str] = None,
        stage: Optional[str] = None,
        files: Optional[List[str]] = None,
        pattern: Optional[str] = None,
        file_format: Optional[Any] = None,
        on_error: Optional[str] = None,
        force: Optional[bool] = None,
        purge: Optional[bool] = None,
        validation_mode: Optional[str] = None,
        partition_by: Optional[List[str]] = None,
        header: Optional[bool] = None,
        overwrite: Optional[bool] = None,
        single: Optional[bool] = None,
    ):
        super().__init__(dialect)
        self.mode = mode
        self.table = table
        self.stage = stage
        self.files = files
        self.pattern = pattern
        self.file_format = file_format
        self.on_error = on_error
        self.force = force
        self.purge = purge
        self.validation_mode = validation_mode
        self.partition_by = partition_by
        self.header = header
        self.overwrite = overwrite
        self.single = single

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate COPY INTO SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_copy_into_statement(self), ()
