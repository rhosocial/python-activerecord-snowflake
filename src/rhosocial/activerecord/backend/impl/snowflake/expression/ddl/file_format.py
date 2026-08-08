# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/file_format.py
"""Snowflake FILE FORMAT expressions.

File formats describe how staged data files are parsed (CSV / JSON /
AVRO / ORC / PARQUET / XML). They are referenced by STAGE objects and
COPY INTO statements. These expressions generate CREATE / ALTER / DROP
FILE FORMAT statements with pass-through format options.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- CREATE FILE FORMAT: https://docs.snowflake.com/en/sql-reference/sql/create-file-format
- ALTER FILE FORMAT:  https://docs.snowflake.com/en/sql-reference/sql/alter-file-format
- DROP FILE FORMAT:   https://docs.snowflake.com/en/sql-reference/sql/drop-file-format
"""
from enum import Enum
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeFileFormatType",
    "SnowflakeCreateFileFormatExpression",
    "SnowflakeAlterFileFormatExpression",
    "SnowflakeDropFileFormatExpression",
]


class SnowflakeFileFormatType(Enum):
    """Supported FILE FORMAT type values."""

    CSV = "CSV"
    JSON = "JSON"
    AVRO = "AVRO"
    ORC = "ORC"
    PARQUET = "PARQUET"
    XML = "XML"


class SnowflakeCreateFileFormatExpression(BaseExpression):
    """Snowflake CREATE [OR REPLACE] FILE FORMAT statement expression.

    Attributes:
        name: File format name.
        or_replace: Emit ``OR REPLACE``.
        if_not_exists: Emit ``IF NOT EXISTS``.
        type_: ``TYPE`` value (:class:`SnowflakeFileFormatType` or string).
        options: Pass-through format options as a ``{KEY: value}`` dict
            (e.g. ``{"FIELD_DELIMITER": ",", "SKIP_HEADER": 1,
            "NULL_IF": ("NULL",)}``).
        comment: ``COMMENT`` string literal.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        or_replace: bool = False,
        if_not_exists: bool = False,
        type_: Optional[Any] = None,
        options: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.or_replace = or_replace
        self.if_not_exists = if_not_exists
        self.type_ = type_
        self.options = options or {}
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate CREATE FILE FORMAT SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_create_file_format_statement(self), ()


class SnowflakeAlterFileFormatExpression(BaseExpression):
    """Snowflake ALTER FILE FORMAT statement expression.

    Attributes:
        name: File format name.
        if_exists: Emit ``IF EXISTS``.
        options: Pass-through format options for ``SET``.
        comment: ``COMMENT`` string literal for ``SET``.

    Raises:
        ValueError: when no ``SET`` property is specified.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        name: str,
        *,
        if_exists: bool = False,
        options: Optional[Dict[str, Any]] = None,
        comment: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.name = name
        self.if_exists = if_exists
        self.options = options or {}
        self.comment = comment

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate ALTER FILE FORMAT SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_alter_file_format_statement(self), ()


class SnowflakeDropFileFormatExpression(BaseExpression):
    """Snowflake DROP FILE FORMAT statement expression.

    Attributes:
        name: File format name.
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
        """Generate DROP FILE FORMAT SQL statement.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.dialect.format_drop_file_format_statement(self), ()
