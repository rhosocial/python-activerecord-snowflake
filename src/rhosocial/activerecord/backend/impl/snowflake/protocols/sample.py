# src/rhosocial/activerecord/backend/impl/snowflake/protocols/sample.py
"""Snowflake SAMPLE / TABLESAMPLE clause protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake can sample a table either by row count (``SAMPLE (10 ROWS)``) or by
percentage (``SAMPLE (0.5)``), optionally with the ``BERNOULLI`` or ``SYSTEM``
sampling method and a ``REPEATABLE`` seed. ``SAMPLE`` and ``TABLESAMPLE`` are
synonyms.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/constructs/sample
"""
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.sample import SnowflakeSampleExpression


@runtime_checkable
class SnowflakeSampleSupport(Protocol):
    """Snowflake SAMPLE / TABLESAMPLE clause protocol."""

    def supports_sample(self) -> bool:
        """Whether the SAMPLE clause is supported."""
        ...

    def supports_tablesample(self) -> bool:
        """Whether the TABLESAMPLE clause is supported."""
        ...

    def format_sample_clause(
        self, expr: "SnowflakeSampleExpression"
    ) -> str:
        """Format a SAMPLE clause."""
        ...

    def format_tablesample_clause(
        self, expr: "SnowflakeSampleExpression"
    ) -> str:
        """Format a TABLESAMPLE clause."""
        ...
