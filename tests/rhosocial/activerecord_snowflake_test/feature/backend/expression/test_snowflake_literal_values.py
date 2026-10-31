# tests/rhosocial/activerecord_snowflake_test/feature/backend/expression/test_snowflake_literal_values.py
"""Snowflake's spellings for the value literals -- construction and rendering
only.

Core's one literal node owns the binding decision: ``Literal(d, value)`` binds
the host value behind a placeholder, and ``Literal(d, value, inline=True)`` --
what a DDL syntax position passes, the one that accepts no bind parameters --
writes the value as SQL text through the dialect's controlled literal
construction. Snowflake's own spellings live in the second tier of that
construction, ``SnowflakeLiteralValueMixin.format_literal``, and everything
else falls through to the base.

**not server-verified.**  There is no Snowflake instance reachable from this
repository; every assertion below is a rendering assertion over grammar
transcribed from the official documentation, never a measurement:

  https://docs.snowflake.com/en/sql-reference/functions/to_binary
  https://docs.snowflake.com/en/sql-reference/binary-input-output
  https://docs.snowflake.com/en/sql-reference/data-types-uuid
  https://docs.snowflake.com/en/sql-reference/data-types-numeric
  https://docs.snowflake.com/en/sql-reference/data-types-text
  https://docs.snowflake.com/en/sql-reference/data-types-datetime
"""

import datetime
import decimal
import uuid

import pytest

from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


@pytest.fixture
def dialect():
    return SnowflakeDialect()


class TestBinarySpelling:
    """``TO_BINARY('0102', 'HEX')`` -- the encoding named, not assumed."""

    def test_data_position_binds_the_bytes(self, dialect):
        sql, params = Literal(dialect, b"\x01\x02").to_sql()
        assert sql == "%s"
        assert params == (b"\x01\x02",)

    def test_inline_position_names_hex(self, dialect):
        sql, params = Literal(dialect, b"\x01\x02", inline=True).to_sql()
        assert sql == "TO_BINARY('0102', 'HEX')"
        assert params == ()

    def test_the_digits_are_uppercase_like_snowflakes_own_output(self, dialect):
        sql, _ = Literal(dialect, b"\xab\xcd\xef", inline=True).to_sql()
        assert sql == "TO_BINARY('ABCDEF', 'HEX')"

    def test_an_empty_value_is_the_empty_literal(self, dialect):
        sql, _ = Literal(dialect, b"", inline=True).to_sql()
        assert sql == "TO_BINARY('', 'HEX')"

    def test_bytearray_is_spelled_from_the_bytes_it_holds(self, dialect):
        sql, params = Literal(dialect, bytearray(b"\x01"), inline=True).to_sql()
        assert sql == "TO_BINARY('01', 'HEX')"
        assert params == ()


class TestUUIDSpelling:
    """The bare quoted canonical text -- the ANSI literal form."""

    CANONICAL = "c73d9175-0a1d-48c6-8d30-df165461328b"

    def test_data_position_binds_the_uuid(self, dialect):
        value = uuid.UUID(self.CANONICAL)
        sql, params = Literal(dialect, value).to_sql()
        assert sql == "%s"
        assert params == (value,)

    def test_inline_position_is_the_quoted_canonical_text(self, dialect):
        sql, params = Literal(dialect, uuid.UUID(self.CANONICAL), inline=True).to_sql()
        assert sql == f"'{self.CANONICAL}'"
        assert params == ()


class TestIntervalStaysRefused:
    """No ``timedelta`` branch in this dialect's ``format_literal``, on purpose.

    The interval *constant* is a date-arithmetic operand that Snowflake
    refuses to store in an interval column, and the interval *data type*
    takes a string whose shape depends on the column's qualifier, which a
    value node does not carry -- so the base's explicit ``TypeError`` is the
    answer, and the structural absence is asserted rather than papered over.
    """

    def test_data_position_still_binds(self, dialect):
        span = datetime.timedelta(days=2, hours=3)
        sql, params = Literal(dialect, span).to_sql()
        assert sql == "%s"
        assert params == (span,)

    def test_inline_position_keeps_the_base_refusal(self, dialect):
        with pytest.raises(TypeError, match="has no inline SQL literal form"):
            Literal(dialect, datetime.timedelta(days=1), inline=True).to_sql()


class TestTierOneAgreesWithTheBase:
    """The audit: nothing overridden for the kinds Snowflake spells like core.

    Each assertion is the base's spelling reached through this dialect's
    ``format_literal``, pinned here so a base change that breaks Snowflake's
    grammar is caught by this file rather than in the matrix, where the row
    would only say "renders".
    """

    def test_null_binds_then_renders_as_the_keyword(self, dialect):
        assert Literal(dialect, None).to_sql() == ("%s", (None,))
        assert Literal(dialect, None, inline=True).to_sql() == ("NULL", ())

    def test_booleans_render_as_keywords(self, dialect):
        assert Literal(dialect, True, inline=True).to_sql() == ("TRUE", ())
        assert Literal(dialect, False, inline=True).to_sql() == ("FALSE", ())

    def test_integers_render_as_numeric_text(self, dialect):
        assert Literal(dialect, 18, inline=True).to_sql() == ("18", ())
        assert Literal(dialect, -7, inline=True).to_sql() == ("-7", ())

    def test_floats_render_as_their_repr(self, dialect):
        assert Literal(dialect, 0.5, inline=True).to_sql() == ("0.5", ())
        assert Literal(dialect, 15e-03, inline=True).to_sql() == ("0.015", ())

    def test_decimals_render_exact(self, dialect):
        value = decimal.Decimal("12.34")
        assert Literal(dialect, value, inline=True).to_sql() == ("12.34", ())

    def test_strings_double_the_quotes(self, dialect):
        sql, _ = Literal(dialect, "today's", inline=True).to_sql()
        assert sql == "'today''s'"

    def test_dates_render_as_quoted_iso(self, dialect):
        sql, _ = Literal(dialect, datetime.date(2026, 10, 17), inline=True).to_sql()
        assert sql == "'2026-10-17'"

    def test_times_render_as_quoted_iso(self, dialect):
        sql, _ = Literal(dialect, datetime.time(10, 3, 56), inline=True).to_sql()
        assert sql == "'10:03:56'"

    def test_datetimes_render_as_quoted_iso_with_a_space_separator(self, dialect):
        sql, _ = Literal(
            dialect, datetime.datetime(2024, 8, 15, 10, 59, 43), inline=True
        ).to_sql()
        assert sql == "'2024-08-15 10:59:43'"


class TestNonFiniteFloatsNeverReachSqlText:
    """The base's refusal is Snowflake's answer: they are quoted specials.

    Snowflake spells the FLOAT special values ``'NaN'`` / ``'inf'`` -- quoted
    text, not a numeric literal the base could emit. Core decides the value's
    kind before rendering (``nan_value`` / ``infinity_value``), so a
    ``float`` carrying one of these is refused rather than spelled.
    """

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_inline_position_is_refused(self, dialect, value):
        with pytest.raises(ValueError, match="cannot be inlined into SQL"):
            Literal(dialect, value, inline=True).to_sql()


class TestMROOrder:
    """The composed order is what resolves the tier-2 spellings."""

    def test_the_local_mixin_wins_over_the_base(self, dialect):
        assert dialect.format_literal.__func__.__qualname__.startswith(
            "SnowflakeLiteralValueMixin"
        )

    def test_inline_literals_route_through_the_local_mixin(self, dialect):
        # format_literal_expression hands inline=True literals to
        # format_literal, so the MRO test and the rendering test agree.
        sql, _ = Literal(dialect, b"\x01", inline=True).to_sql()
        assert sql == "TO_BINARY('01', 'HEX')"
