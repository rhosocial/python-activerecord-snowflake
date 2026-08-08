# src/rhosocial/activerecord/backend/impl/snowflake/protocols/pivot.py
"""Snowflake PIVOT / UNPIVOT clause protocol.

Feature Source: Snowflake native (not SQL standard)

PIVOT rotates rows into columns (cross-tabulation); UNPIVOT is the inverse,
rotating columns into rows. Snowflake syntax is compatible with Oracle's
``agg(x) FOR col IN (...)`` form.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/constructs/pivot
"""
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.pivot import (
        SnowflakePivotExpression,
        SnowflakeUnpivotExpression,
    )


@runtime_checkable
class SnowflakePivotSupport(Protocol):
    """Snowflake PIVOT / UNPIVOT clause protocol."""

    def supports_pivot(self) -> bool:
        """Whether the PIVOT clause is supported."""
        ...

    def supports_unpivot(self) -> bool:
        """Whether the UNPIVOT clause is supported."""
        ...

    def format_pivot_clause(
        self, expr: "SnowflakePivotExpression"
    ) -> str:
        """Format a PIVOT clause."""
        ...

    def format_unpivot_clause(
        self, expr: "SnowflakeUnpivotExpression"
    ) -> str:
        """Format an UNPIVOT clause."""
        ...
