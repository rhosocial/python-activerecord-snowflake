# src/rhosocial/activerecord/backend/impl/snowflake/mixins/sample.py
"""SnowflakeSampleMixin — SAMPLE / TABLESAMPLE clause support."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..expression.sample import SnowflakeSampleExpression


class SnowflakeSampleMixin:
    """Mixin for Snowflake SAMPLE / TABLESAMPLE clause support."""

    def supports_sample(self) -> bool:
        """Snowflake supports the SAMPLE clause."""
        return True

    def supports_tablesample(self) -> bool:
        """Snowflake supports the TABLESAMPLE clause."""
        return True

    def format_sample_clause(
        self, expr: "SnowflakeSampleExpression"
    ) -> str:
        """Format a ``SAMPLE`` clause.

        Args:
            expr: :class:`SnowflakeSampleExpression`.

        Returns:
            The formatted SAMPLE clause SQL string.

        """
        return self.format_sampling_clause(expr, "SAMPLE")

    def format_tablesample_clause(
        self, expr: "SnowflakeSampleExpression"
    ) -> str:
        """Format a ``TABLESAMPLE`` clause.

        Args:
            expr: :class:`SnowflakeSampleExpression`.

        Returns:
            The formatted TABLESAMPLE clause SQL string.

        """
        return self.format_sampling_clause(expr, "TABLESAMPLE")

    def format_sampling_clause(
        self, expr: "SnowflakeSampleExpression", keyword: str
    ) -> str:
        """Render a sampling clause under a given keyword.

        Emits ``{keyword} [method] ({count} ROWS | {percentage})
        [REPEATABLE ({seed})]``.
        """
        parts = [keyword]
        if expr.sampling_method is not None:
            parts.append(expr.sampling_method.value)
        if expr.is_percent or isinstance(expr.count, float):
            parts.append(f"({expr.count})")
        else:
            parts.append(f"({int(expr.count)} ROWS)")
        if expr.seed is not None:
            parts.append(f"REPEATABLE ({int(expr.seed)})")
        return " ".join(parts)
