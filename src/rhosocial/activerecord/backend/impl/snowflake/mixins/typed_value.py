# src/rhosocial/activerecord/backend/impl/snowflake/mixins/typed_value.py
"""Snowflake's spellings for the typed value literals whose form is its own.

**not server-verified** -- this repository reaches no Snowflake instance, so
every spelling below is transcribed from the official documentation, quoted
per method, and checked only as a rendering assertion. When a live server
contradicts a spelling here, change the spelling, not the test.

Snowflake agrees with the base on the whole of tier 1, so nothing is
overridden for those kinds:

* ``NULL`` and the ``TRUE`` / ``FALSE`` keywords -- the literal-value
  grammar spells them as keywords;
* numbers as numeric text -- the numeric-constants grammar
  (``[+-][digits][.digits][e[+-]digits]``) takes ``str(int)``, ``repr(float)``
  and ``str(Decimal)`` verbatim, and the FLOAT special values ``'NaN'`` /
  ``'inf'`` require quotes, so the base's NaN/Inf refusal is also Snowflake's
  answer;
* strings quoted with doubled single quotes -- the string-constants section
  writes the escape rule exactly that way;
* date / time / timestamp as quoted ISO 8601 text -- the date & time page
  accepts ``YYYY-MM-DD`` among "the most common forms" and quotes every
  constant.

Two value types differ, and each differs because Snowflake's grammar says so:

* **binary** -- ``TO_BINARY('0102', 'HEX')``, the two-argument conversion.
  The one-argument ``TO_BINARY`` reads the ``BINARY_INPUT_FORMAT`` session
  parameter, which a dialect must neither read nor assume; naming ``'HEX'``
  makes the literal deterministic across sessions. Uppercase hex is
  Snowflake's own binary-to-string convention.
* **UUID** -- the bare quoted canonical text. Snowflake's UUID page says "The
  ANSI literal form of UUID is supported as input" and inserts a quoted
  canonical string; there is no ``::uuid`` suffix to add.

**INTERVAL stays unimplemented on purpose.** Snowflake's own pages give three
reasons, any one of which would settle it:

1. The interval *constant* (the ``INTERVAL '...'`` keyword form) is a date
   arithmetic operand only: the page says interval constants "can't be
   inserted into a column that has an interval data type", so the DDL
   position a typed value's inline path serves cannot accept one.
2. The interval *data types* take string literals in an interval format
   whose shape depends on the column's qualifier (``+Y-MM`` for year-month,
   ``+D HH24:MI:SS.F`` for day-time) -- a qualifier the value node does not
   carry, and cannot pick without changing what the value means.
3. A ``timedelta`` holds days, seconds and microseconds, never years or
   months, and Snowflake splits its interval grammar into year-month and
   day-time families that cannot be mixed -- so no single qualifier can
   faithfully carry an arbitrary ``timedelta``.

That is why this mixin defines no ``format_interval_value``: leaving the
method absent is what makes the base's explicit refusal structural, the same
fail-closed choice the dialect makes elsewhere.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- TO_BINARY:            https://docs.snowflake.com/en/sql-reference/functions/to_binary
- Binary input and output:
  https://docs.snowflake.com/en/sql-reference/binary-input-output
- String & binary data types:
  https://docs.snowflake.com/en/sql-reference/data-types-text
- Numeric data types:   https://docs.snowflake.com/en/sql-reference/data-types-numeric
- UUID data type:       https://docs.snowflake.com/en/sql-reference/data-types-uuid
- Date & time data types:
  https://docs.snowflake.com/en/sql-reference/data-types-datetime
"""

from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.values import TypedValue


class SnowflakeTypedValueMixin:
    """Snowflake's tier-2 value literals.

    Stands alone rather than inheriting :class:`TypedValueMixin`, like this
    backend's other mixins: the dialect composes the specific mixin ahead of
    the generic one, and these two methods win by that position. Inheriting
    would put the base ahead of the other generic mixins and make the
    ordering the dialect has to reason about depend on this class instead.
    """

    def format_binary_value(self, expr: "TypedValue") -> Tuple[str, tuple]:
        """``TO_BINARY('0102', 'HEX')`` -- hex digits named as such.

        The one-argument ``TO_BINARY`` reads the ``BINARY_INPUT_FORMAT``
        session parameter (default ``HEX``); a dialect must neither read nor
        assume a session setting, so the literal names its encoding and stays
        the same value on every session. The digits go through
        :meth:`format_literal` so the quoting is the base's, and uppercase
        hex matches what Snowflake itself prints for a binary value.

        Rendered from the bytes rather than from any encoded spelling: the
        node holds ``bytes`` precisely because only the dialect layer knows
        which text form its engine accepts.

        https://docs.snowflake.com/en/sql-reference/functions/to_binary
        https://docs.snowflake.com/en/sql-reference/binary-input-output
        """
        if not type(expr).inline_params:
            return self._bind_value(expr)
        hex_text = bytes(expr.value).hex().upper()
        return f"TO_BINARY({self.format_literal(hex_text)}, 'HEX')", ()

    def format_uuid_value(self, expr: "TypedValue") -> Tuple[str, tuple]:
        """A UUID as the quoted canonical text -- the ANSI literal form.

        "The ANSI literal form of UUID is supported as input"; the page's own
        INSERT example is a bare quoted string, and the canonical form a
        Python ``UUID`` stringifies to is exactly the 8-4-4-4-12 pattern the
        page describes. Quoting goes through :meth:`format_literal`, so the
        escaping is the base's rather than a second copy of it.

        https://docs.snowflake.com/en/sql-reference/data-types-uuid
        """
        if not type(expr).inline_params:
            return self._bind_value(expr)
        return self.format_literal(str(expr.value)), ()
