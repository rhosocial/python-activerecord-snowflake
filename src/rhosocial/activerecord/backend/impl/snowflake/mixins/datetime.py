# src/rhosocial/activerecord/backend/impl/snowflake/mixins/datetime.py
"""Snowflake DateTime formatting mixin.

Snowflake uses DATEADD/DATEDIFF for datetime arithmetic.
"""
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.datetime import (
        DatetimeAddExpression,
        DatetimeDiffExpression,
        DatetimeSubtractExpression,
        SecondsBetweenExpression,
    )


class SnowflakeDateTimeMixin:
    """Snowflake datetime formatting override.

    Provides Snowflake-specific datetime add/subtract and diff
    expressions using DATEADD and DATEDIFF.

    Each formatter names the expression it is handed rather than ``Any``.
    ``format_method`` dispatches on the node's own class, so the parameter has
    one possible type and naming it turns a wrong attribute read into a type
    error a reader can see, instead of an ``AttributeError`` raised later from
    inside the body.
    """

    def format_datetime_add_expression(
        self, expr: "DatetimeAddExpression"
    ) -> Tuple[str, tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        sql = f"DATEADD({unit}, {self.p()}, {source_sql})"
        return self.apply_alias(
            sql, (expr.interval.value,) + source_params, expr
        )

    def format_datetime_subtract_expression(
        self, expr: "DatetimeSubtractExpression"
    ) -> Tuple[str, tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        sql = f"DATEADD({unit}, {self.p()}, {source_sql})"
        return self.apply_alias(
            sql, (-expr.interval.value,) + source_params, expr
        )

    def format_datetime_diff_expression(
        self, expr: "DatetimeDiffExpression"
    ) -> Tuple[str, tuple]:
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        sql = f"DATEDIFF({expr.unit.value.upper()}, {start_sql}, {end_sql})"
        return self.apply_alias(sql, start_params + end_params, expr)

    def format_seconds_between_expression(
        self, expr: "SecondsBetweenExpression"
    ) -> Tuple[str, tuple]:
        """Format signed seconds between two instants with ``DATEDIFF``.

        Snowflake has no interval subtraction that yields a duration: a
        ``TIMESTAMP`` minus a ``TIMESTAMP`` is not a number there. Its
        ``DATEDIFF`` counts the named unit's boundaries between two instants,
        so the finest unit a timestamp can keep is named and the integer it
        returns is divided back into seconds:

        ``DATEDIFF(MILLISECOND, start, end) / 1000.0``

        Snowflake's own ``DATEDIFF`` already computes ``end - start``, so a
        later end is positive and an earlier one negative without a special
        case. The divisor is written as ``1000.0`` rather than ``1000`` so the
        division keeps the fraction; integer division would truncate the
        result to whole seconds and make a half-second duration read as zero.

        Resolution: a timestamp column can keep microseconds or nanoseconds,
        but ``DATEDIFF`` in milliseconds counts whole millisecond boundaries,
        so the fraction below one millisecond is truncated before the
        division. Up to 0.001 seconds can therefore be lost, and a difference
        smaller than a millisecond can render as ``0.0``; a duration the
        caller needs to that precision must be written as an explicit
        timestamp difference elsewhere.

        The SQL writes ``start`` before ``end`` -- ``DATEDIFF``'s argument
        order -- so their bind parameters are collected in the order the
        placeholders appear. ``apply_alias`` preserves a ``.as_(...)`` alias.
        """
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        sql = f"DATEDIFF(MILLISECOND, {start_sql}, {end_sql}) / 1000.0"
        return self.apply_alias(sql, start_params + end_params, expr)


__all__ = ['SnowflakeDateTimeMixin']