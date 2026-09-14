# src/rhosocial/activerecord/backend/impl/snowflake/expression/variant.py
"""Snowflake VARIANT path access and cast expressions.

Snowflake VARIANT type stores semi-structured data (JSON, Avro, ORC, Parquet).
Key operations:
- Path access: variant_col:path (colon notation)
- Type casting: variant_col:path::type (colon-cast notation)

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/data-types-semistructured
"""
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeVariantPathAccessExpression",
    "SnowflakeVariantCastExpression",
]


class SnowflakeVariantPathAccessExpression(BaseExpression):
    """Snowflake VARIANT path access expression.

    Formats a colon-notation path access on a VARIANT column:
    ``column:path``

    Attributes:
        column: Column name containing VARIANT data.
        path: Dot-notation path inside the VARIANT (e.g. ``'key.nested'``).
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        column: str,
        path: str,
    ):
        super().__init__(dialect)
        self.column = column
        self.path = path

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate VARIANT path access SQL.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        sql, params = self.dialect.format_variant_path_access(self)
        return sql, ()


class SnowflakeVariantCastExpression(BaseExpression):
    """Snowflake VARIANT path access with explicit type cast expression.

    Formats a colon-notation path access followed by a double-colon cast:
    ``column:path::target_type``

    Attributes:
        column: Column name containing VARIANT data.
        path: Dot-notation path inside the VARIANT (e.g. ``'count'``).
        target_type: SQL type to cast the result to (e.g. ``'NUMBER'``).
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        column: str,
        path: str,
        target_type: str,
    ):
        super().__init__(dialect)
        self.column = column
        self.path = path
        self.target_type = target_type

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate VARIANT cast SQL.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        sql, params = self.dialect.format_variant_cast(self)
        return sql, ()
