# tests/rhosocial/activerecord_snowflake_test/feature/backend/expression/test_typed_values.py
"""Snowflake's spellings for the typed value literals.

Core's value nodes render through ``inline_params`` -- a class-level
strategy, never a per-instance flag -- so the DDL-position assertions below
use a test-local DDL-position class per kind, the same lift core itself
performs when it renders a ``DEFAULT`` / ``CHECK`` tree (``Literal`` ->
``DdlLiteral``). The data-position assertions run the node classes as they
ship, which bind.

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

from rhosocial.activerecord.backend.expression.values import (
    BinaryValue,
    BooleanValue,
    DateValue,
    DecimalValue,
    FloatValue,
    IntegerValue,
    IntervalValue,
    NullValue,
    StringValue,
    TimeValue,
    TimestampValue,
    UUIDValue,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


# -- the DDL-position lift ------------------------------------------------
#
# One class per kind, each declaring the strategy its position requires,
# exactly as core's own DdlLiteral does for Literal. The subclass adds no
# field and no kind: it only owns the position, which is the whole of the
# class-level inline strategy.

class DdlBinaryValue(BinaryValue):
    inline_params = True


class DdlUUIDValue(UUIDValue):
    inline_params = True


class DdlIntervalValue(IntervalValue):
    inline_params = True


class DdlNullValue(NullValue):
    inline_params = True


class DdlBooleanValue(BooleanValue):
    inline_params = True


class DdlIntegerValue(IntegerValue):
    inline_params = True


class DdlFloatValue(FloatValue):
    inline_params = True


class DdlDecimalValue(DecimalValue):
    inline_params = True


class DdlStringValue(StringValue):
    inline_params = True


class DdlDateValue(DateValue):
    inline_params = True


class DdlTimeValue(TimeValue):
    inline_params = True


class DdlTimestampValue(TimestampValue):
    inline_params = True


class TestBinaryValue:
    """``TO_BINARY('0102', 'HEX')`` -- the encoding named, not assumed."""

    def test_data_position_binds_the_bytes(self, dialect):
        sql, params = BinaryValue(dialect, b"\x01\x02").to_sql()
        assert sql == "%s"
        assert params == (b"\x01\x02",)

    def test_ddl_position_names_hex(self, dialect):
        sql, params = DdlBinaryValue(dialect, b"\x01\x02").to_sql()
        assert sql == "TO_BINARY('0102', 'HEX')"
        assert params == ()

    def test_the_digits_are_uppercase_like_snowflakes_own_output(self, dialect):
        sql, _ = DdlBinaryValue(dialect, b"\xab\xcd\xef").to_sql()
        assert sql == "TO_BINARY('ABCDEF', 'HEX')"

    def test_an_empty_value_is_the_empty_literal(self, dialect):
        sql, _ = DdlBinaryValue(dialect, b"").to_sql()
        assert sql == "TO_BINARY('', 'HEX')"

    def test_bytearray_is_normalised_before_rendering(self, dialect):
        sql, params = DdlBinaryValue(dialect, bytearray(b"\x01")).to_sql()
        assert sql == "TO_BINARY('01', 'HEX')"
        assert params == ()


class TestUUIDValue:
    """The bare quoted canonical text -- the ANSI literal form."""

    CANONICAL = "c73d9175-0a1d-48c6-8d30-df165461328b"

    def test_data_position_binds_the_uuid(self, dialect):
        value = uuid.UUID(self.CANONICAL)
        sql, params = UUIDValue(dialect, value).to_sql()
        assert sql == "%s"
        assert params == (value,)

    def test_ddl_position_is_the_quoted_canonical_text(self, dialect):
        sql, params = DdlUUIDValue(dialect, uuid.UUID(self.CANONICAL)).to_sql()
        assert sql == f"'{self.CANONICAL}'"
        assert params == ()


class TestIntervalValueStaysRefused:
    """No ``format_interval_value`` on this dialect, on purpose.

    The interval *constant* is a date-arithmetic operand that Snowflake
    refuses to insert into an interval column, and the interval *data type*
    takes a string whose shape depends on the column's qualifier, which a
    value node does not carry -- so the base's explicit failure is the
    answer, and the structural absence is asserted rather than papered over.
    """

    def test_data_position_still_binds(self, dialect):
        span = datetime.timedelta(days=2, hours=3)
        sql, params = IntervalValue(dialect, span).to_sql()
        assert sql == "%s"
        assert params == (span,)

    def test_ddl_position_keeps_the_base_refusal(self, dialect):
        with pytest.raises(NotImplementedError, match="INTERVAL literals"):
            DdlIntervalValue(dialect, datetime.timedelta(days=1)).to_sql()


class TestTierOneAgreesWithTheBase:
    """The audit: nothing overridden for the kinds Snowflake spells like core.

    Each assertion is the base's spelling, pinned here so a base change that
    breaks Snowflake's grammar is caught by this file rather than in the
    matrix, where the row would only say "renders".
    """

    def test_null_binds_then_renders_as_the_keyword(self, dialect):
        assert NullValue(dialect).to_sql() == ("%s", (None,))
        assert DdlNullValue(dialect).to_sql() == ("NULL", ())

    def test_booleans_render_as_keywords(self, dialect):
        assert DdlBooleanValue(dialect, True).to_sql() == ("TRUE", ())
        assert DdlBooleanValue(dialect, False).to_sql() == ("FALSE", ())

    def test_integers_render_as_numeric_text(self, dialect):
        assert DdlIntegerValue(dialect, 18).to_sql() == ("18", ())
        assert DdlIntegerValue(dialect, -7).to_sql() == ("-7", ())

    def test_floats_render_as_their_repr(self, dialect):
        assert DdlFloatValue(dialect, 0.5).to_sql() == ("0.5", ())
        assert DdlFloatValue(dialect, 15e-03).to_sql() == ("0.015", ())

    def test_decimals_render_exact(self, dialect):
        value = decimal.Decimal("12.34")
        assert DdlDecimalValue(dialect, value).to_sql() == ("12.34", ())

    def test_strings_double_the_quotes(self, dialect):
        sql, _ = DdlStringValue(dialect, "today's").to_sql()
        assert sql == "'today''s'"

    def test_dates_render_as_quoted_iso(self, dialect):
        sql, _ = DdlDateValue(dialect, datetime.date(2026, 10, 17)).to_sql()
        assert sql == "'2026-10-17'"

    def test_times_render_as_quoted_iso(self, dialect):
        sql, _ = DdlTimeValue(dialect, datetime.time(10, 3, 56)).to_sql()
        assert sql == "'10:03:56'"

    def test_timestamps_render_as_quoted_iso_with_a_space_separator(self, dialect):
        sql, _ = DdlTimestampValue(
            dialect, datetime.datetime(2024, 8, 15, 10, 59, 43)
        ).to_sql()
        assert sql == "'2024-08-15 10:59:43'"


class TestMROOrder:
    """The composed order is what resolves the two overrides."""

    def test_the_local_mixin_wins_over_the_base(self, dialect):
        assert dialect.format_binary_value.__func__.__qualname__.startswith(
            "SnowflakeTypedValueMixin"
        )
        assert dialect.format_uuid_value.__func__.__qualname__.startswith(
            "SnowflakeTypedValueMixin"
        )

    def test_the_base_answers_the_kinds_the_local_mixin_leaves_alone(self, dialect):
        assert dialect.format_null_value.__func__.__qualname__.startswith(
            "TypedValueMixin"
        )
        assert dialect.format_interval_value.__func__.__qualname__.startswith(
            "TypedValueMixin"
        )
