# src/rhosocial/activerecord/backend/impl/snowflake/expression/pivot.py
"""Snowflake PIVOT / UNPIVOT clause expressions.

PIVOT rotates rows into columns, producing a cross-tabulation query.
UNPIVOT rotates columns into rows, the inverse operation. The Snowflake
syntax is compatible with Oracle's ``agg(x) FOR col IN (...)`` form.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- PIVOT / UNPIVOT: https://docs.snowflake.com/en/sql-reference/constructs/pivot
"""
from typing import List, Optional, Tuple, Union, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakePivotExpression",
    "SnowflakeUnpivotExpression",
]


class SnowflakePivotExpression(BaseExpression):
    """Snowflake PIVOT clause expression.

    PIVOT rotates rows to columns:

        PIVOT (SUM(v) FOR c IN ('a', 'b')) p

    Attributes:
        aggregate_function: Aggregate function name (``SUM``, ``COUNT``, ...).
        aggregate_column: Column the aggregate function is applied to.
        pivot_column: Column whose values become the new column headers.
        values: List of values to pivot into columns.
        alias: Optional alias for the pivoted result.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        aggregate_function: str,
        aggregate_column: str,
        pivot_column: str,
        values: Optional[List[Union[str, int, float]]] = None,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.aggregate_function = aggregate_function
        self.aggregate_column = aggregate_column
        self.pivot_column = pivot_column
        self.values = values or []
        self.alias = alias

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate the PIVOT clause SQL.

        Returns:
            Tuple of (clause SQL string, empty params tuple).

        """
        return self.dialect.format_pivot_clause(self), ()


class SnowflakeUnpivotExpression(BaseExpression):
    """Snowflake UNPIVOT clause expression.

    UNPIVOT rotates columns to rows, the inverse of PIVOT:

        UNPIVOT (val FOR col IN (a, b)) u

    Attributes:
        value_column: Output column name holding the unpivoted values.
        pivot_column: Output column name holding the source column names.
        columns: List of columns to unpivot.
        include_nulls: Include NULL values (default: exclude them).
        alias: Optional alias for the unpivoted result.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        *,
        value_column: str,
        pivot_column: str,
        columns: Optional[List[str]] = None,
        include_nulls: bool = False,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.value_column = value_column
        self.pivot_column = pivot_column
        self.columns = columns or []
        self.include_nulls = include_nulls
        self.alias = alias

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate the UNPIVOT clause SQL.

        Returns:
            Tuple of (clause SQL string, empty params tuple).

        """
        return self.dialect.format_unpivot_clause(self), ()
