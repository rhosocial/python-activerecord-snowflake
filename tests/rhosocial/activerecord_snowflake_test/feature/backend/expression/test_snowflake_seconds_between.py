# tests/rhosocial/activerecord_snowflake_test/feature/backend/expression/test_snowflake_seconds_between.py
"""The Snowflake spelling of ``seconds_between(start, end)``.

The node asks one question -- how many seconds elapsed from ``start`` to
``end`` -- and the dialect answers it with ``DATEDIFF``: Snowflake's difference
function works in whole units, so the finest unit the type keeps is named
(``MILLISECOND``) and the integer is divided back into seconds with a decimal
divisor. What this module pins is the rendering and the two properties the
spelling would silently lose if it drifted:

* the argument order -- ``DATEDIFF`` computes its second argument minus its
  first, so ``start`` must come first for a later end to read positive;
* the decimal divisor -- ``/ 1000`` would truncate a fractional duration to
  whole seconds.

The values themselves are checked against a live account when one is
configured (``tests/integration/test_seconds_between.py``); here the check is
that the SQL says what it must for those values to come out right.
"""

from rhosocial.activerecord.backend.expression import (
    Column,
    Literal,
    TimestampColumn,
    seconds_between,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect

import pytest


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSecondsBetweenRendering:
    """The SQL a Snowflake dialect writes for the node."""

    def test_seconds_between_columns_render_datediff_in_milliseconds(self, dialect):
        expr = seconds_between(
            dialect,
            Column(dialect, "queued_at"),
            Column(dialect, "started_at"),
        )
        sql, params = expr.to_sql()
        assert sql == (
            'DATEDIFF(MILLISECOND, "queued_at", "started_at") / 1000.0'
        )
        assert params == ()

    def test_factory_coerces_strings_to_columns(self, dialect):
        expr = seconds_between(dialect, "queued_at", "started_at")
        sql, params = expr.to_sql()
        assert sql == (
            'DATEDIFF(MILLISECOND, "queued_at", "started_at") / 1000.0'
        )
        assert params == ()

    def test_timestamp_column_exposes_the_same_question(self, dialect):
        queued = TimestampColumn(dialect, "queued_at")
        started = Column(dialect, "started_at")
        sql, params = queued.seconds_between(started).to_sql()
        assert sql == (
            'DATEDIFF(MILLISECOND, "queued_at", "started_at") / 1000.0'
        )
        assert params == ()

    def test_argument_order_is_start_then_end(self, dialect):
        """``DATEDIFF`` subtracts its first argument from its second.

        Writing the later instant first would make every positive duration
        read negative, so the order is asserted, not assumed.
        """
        sql, _ = seconds_between(dialect, "earlier", "later").to_sql()
        assert sql == 'DATEDIFF(MILLISECOND, "earlier", "later") / 1000.0'
        assert sql.index('"earlier"') < sql.index('"later"')

    def test_divisor_is_decimal_not_integer(self, dialect):
        """``/ 1000`` floors a half-second duration to zero."""
        sql, _ = seconds_between(dialect, "a", "b").to_sql()
        assert sql.endswith("/ 1000.0")
        assert "/ 1000 " not in sql

    def test_alias_is_applied_after_the_division(self, dialect):
        expr = seconds_between(dialect, "queued_at", "started_at").as_(
            "queue_seconds"
        )
        sql, params = expr.to_sql()
        assert sql == (
            'DATEDIFF(MILLISECOND, "queued_at", "started_at") / 1000.0 '
            'AS "queue_seconds"'
        )
        assert params == ()

    def test_alias_does_not_disturb_bind_order(self, dialect):
        expr = seconds_between(
            dialect,
            Literal(dialect, "2026-01-01 00:00:00"),
            Literal(dialect, "2026-01-01 00:00:05"),
        ).as_("elapsed")
        sql, params = expr.to_sql()
        assert sql == (
            "DATEDIFF(MILLISECOND, %s, %s) / 1000.0 AS \"elapsed\""
        )
        assert params == ("2026-01-01 00:00:00", "2026-01-01 00:00:05")


class TestSecondsBetweenBindOrder:
    """Bind parameters follow the placeholders, not the constructor."""

    def test_params_follow_the_sql_placeholders(self, dialect):
        start = Literal(dialect, "start_value")
        end = Literal(dialect, "end_value")
        sql, params = seconds_between(dialect, start, end).to_sql()
        assert sql == "DATEDIFF(MILLISECOND, %s, %s) / 1000.0"
        assert len(params) == sql.count("%s")
        assert params == ("start_value", "end_value")

    def test_distinct_values_prove_the_order(self, dialect):
        """A swap of the two literals must change the two parameters."""
        forward_sql, forward_params = seconds_between(
            dialect, Literal(dialect, "first"), Literal(dialect, "second")
        ).to_sql()
        reverse_sql, reverse_params = seconds_between(
            dialect, Literal(dialect, "second"), Literal(dialect, "first")
        ).to_sql()
        assert forward_sql == reverse_sql
        assert forward_params == ("first", "second")
        assert reverse_params == ("second", "first")


class TestSecondsBetweenCapability:
    """The node is no longer a refused capability on this dialect."""

    def test_formatter_is_declared(self, dialect):
        from rhosocial.activerecord.backend.expression.datetime import (
            SecondsBetweenExpression,
        )

        expr = seconds_between(dialect, "a", "b")
        assert isinstance(expr, SecondsBetweenExpression)
        assert expr.format_method == "format_seconds_between_expression"
        assert callable(
            getattr(dialect, "format_seconds_between_expression", None)
        )

    def test_does_not_raise_unsupported(self, dialect):
        sql, params = seconds_between(dialect, "a", "b").to_sql()
        assert sql and params == ()
