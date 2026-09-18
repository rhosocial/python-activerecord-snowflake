# src/rhosocial/activerecord/backend/impl/snowflake/mixins/datetime.py
"""Snowflake DateTime formatting mixin.

Snowflake uses DATEADD/DATEDIFF for datetime arithmetic.
"""
from typing import Any, Tuple, TYPE_CHECKING


class SnowflakeDateTimeMixin:
    """Snowflake datetime formatting override.

    Provides Snowflake-specific datetime add/subtract and diff
    expressions using DATEADD and DATEDIFF.
    """

    def format_datetime_add_expression(self, expr: "Any") -> Tuple[str, tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        sql = f"DATEADD({unit}, {self.p()}, {source_sql})"
        return self.apply_alias(
            sql, (expr.interval.value,) + source_params, expr
        )

    def format_datetime_subtract_expression(self, expr: "Any") -> Tuple[str, tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        sql = f"DATEADD({unit}, {self.p()}, {source_sql})"
        return self.apply_alias(
            sql, (-expr.interval.value,) + source_params, expr
        )

    def format_datetime_diff_expression(self, expr: "Any") -> Tuple[str, tuple]:
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        sql = f"DATEDIFF({expr.unit.value.upper()}, {start_sql}, {end_sql})"
        return self.apply_alias(sql, start_params + end_params, expr)


__all__ = ['SnowflakeDateTimeMixin']
