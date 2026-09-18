# src/rhosocial/activerecord/backend/impl/snowflake/mixins/sample.py
"""SnowflakeSampleMixin — SAMPLE / TABLESAMPLE clause support."""

from typing import Tuple, TYPE_CHECKING

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
    ) -> Tuple[str, tuple]:
        """Format a ``SAMPLE`` clause.

        Args:
            expr: :class:`SnowflakeSampleExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.format_sampling_clause(expr)

    def format_tablesample_clause(
        self, expr: "SnowflakeSampleExpression"
    ) -> Tuple[str, tuple]:
        """Format a ``TABLESAMPLE`` clause.

        Args:
            expr: :class:`SnowflakeSampleExpression`.

        Returns:
            Tuple of (SQL string, empty params tuple).

        """
        return self.format_sampling_clause(expr)

    def format_sampling_clause(
        self, expr: "SnowflakeSampleExpression"
    ) -> Tuple[str, tuple]:
        """Render a sampling clause.

        Emits ``{keyword} [method] ({count} ROWS | {percentage})
        [REPEATABLE ({seed})]``.
        """
        keyword = expr.form.value
        parts = [keyword]
        if expr.sampling_method is not None:
            parts.append(expr.sampling_method.value)
        if expr.is_percent or isinstance(expr.count, float):
            parts.append(f"({expr.count})")
        else:
            parts.append(f"({int(expr.count)} ROWS)")
        if expr.seed is not None:
            parts.append(f"REPEATABLE ({int(expr.seed)})")
        return " ".join(parts), ()
