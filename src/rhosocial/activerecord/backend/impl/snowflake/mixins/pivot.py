# src/rhosocial/activerecord/backend/impl/snowflake/mixins/pivot.py
"""SnowflakePivotMixin — PIVOT / UNPIVOT clause support."""

from typing import Tuple, TYPE_CHECKING

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
    ) -> Tuple[str, tuple]:
        """Format a PIVOT clause.

        Args:
            expr: :class:`SnowflakePivotExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        value_sql = ", ".join(
            self.inline_sql_literal(value) for value in expr.values
        )
        sql = (
            f"PIVOT ({expr.aggregate_function}("
            f"{self.format_identifier(expr.aggregate_column)}) "
            f"FOR {self.format_identifier(expr.pivot_column)} "
            f"IN ({value_sql}))"
        )
        if expr.alias:
            sql += f" {self.format_identifier(expr.alias)}"
        return sql, ()

    def format_unpivot_clause(
        self, expr: "SnowflakeUnpivotExpression"
    ) -> Tuple[str, tuple]:
        """Format an UNPIVOT clause.

        The null-handling clause is optional in Snowflake's grammar:
        ``UNPIVOT [ { INCLUDE | EXCLUDE } NULLS ] (...)``. ``include_nulls``
        renders ``INCLUDE NULLS``, ``exclude_nulls`` renders the explicit
        ``EXCLUDE NULLS``, and neither renders no clause at all -- the server
        then applies its ``EXCLUDE NULLS`` default. The two parameters are
        mutually exclusive at construction, so the states cannot collide.

        Args:
            expr: :class:`SnowflakeUnpivotExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        if expr.include_nulls:
            nulls = "INCLUDE NULLS "
        elif expr.exclude_nulls:
            nulls = "EXCLUDE NULLS "
        else:
            nulls = ""
        columns_sql = ", ".join(
            self.format_identifier(column) for column in expr.columns
        )
        sql = (
            f"UNPIVOT {nulls}"
            f"({self.format_identifier(expr.value_column)} "
            f"FOR {self.format_identifier(expr.pivot_column)} "
            f"IN ({columns_sql}))"
        )
        if expr.alias:
            sql += f" {self.format_identifier(expr.alias)}"
        return sql, ()
