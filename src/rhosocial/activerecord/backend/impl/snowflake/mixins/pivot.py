# src/rhosocial/activerecord/backend/impl/snowflake/mixins/pivot.py
"""SnowflakePivotMixin — PIVOT / UNPIVOT clause support."""

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.pivot import (
        SnowflakePivotExpression,
        SnowflakeUnpivotExpression,
    )


class SnowflakePivotMixin:
    """Mixin for Snowflake PIVOT / UNPIVOT clause support."""

    def supports_pivot(self) -> bool:
        """Snowflake supports the PIVOT clause."""
        return True

    def supports_unpivot(self) -> bool:
        """Snowflake supports the UNPIVOT clause."""
        return True

    def format_pivot_clause(
        self, expr: "SnowflakePivotExpression"
    ) -> str:
        """Format a PIVOT clause.

        Args:
            expr: :class:`SnowflakePivotExpression`.

        Returns:
            The formatted PIVOT clause SQL string.

        """
        value_sql = ", ".join(
            self.format_pivot_value(value) for value in expr.values
        )
        sql = (
            f"PIVOT ({expr.aggregate_function}("
            f"{self.format_identifier(expr.aggregate_column)}) "
            f"FOR {self.format_identifier(expr.pivot_column)} "
            f"IN ({value_sql}))"
        )
        if expr.alias:
            sql += f" {self.format_identifier(expr.alias)}"
        return sql

    def format_unpivot_clause(
        self, expr: "SnowflakeUnpivotExpression"
    ) -> str:
        """Format an UNPIVOT clause.

        Args:
            expr: :class:`SnowflakeUnpivotExpression`.

        Returns:
            The formatted UNPIVOT clause SQL string.

        """
        nulls = "INCLUDE NULLS" if expr.include_nulls else "EXCLUDE NULLS"
        columns_sql = ", ".join(
            self.format_identifier(column) for column in expr.columns
        )
        sql = (
            f"UNPIVOT {nulls} "
            f"({self.format_identifier(expr.value_column)} "
            f"FOR {self.format_identifier(expr.pivot_column)} "
            f"IN ({columns_sql}))"
        )
        if expr.alias:
            sql += f" {self.format_identifier(expr.alias)}"
        return sql

    def format_pivot_value(self, value: Any) -> str:
        """Render a single PIVOT ``IN`` value as a SQL literal."""
        if isinstance(value, str):
            return f"'{self._escape_sql_string(value)}'"
        return str(value)
