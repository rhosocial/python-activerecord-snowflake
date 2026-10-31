# src/rhosocial/activerecord/backend/impl/snowflake/mixins/literal.py
"""Snowflake's tier-2 value literals.

``SQLDialectBase.format_literal`` is the single entry point for writing a value
as SQL text, and it resolves in three tiers: the portable scalars it knows, the
types a backend spells for itself, and the literal-construction protocol. This
module is Snowflake's second tier, and it spells the two types Snowflake's
grammar spells for itself:

* ``bytes`` becomes ``TO_BINARY('0102', 'HEX')``, the two-argument conversion.
  The one-argument ``TO_BINARY`` reads the ``BINARY_INPUT_FORMAT`` session
  parameter, which a dialect must neither read nor assume; naming ``'HEX'``
  makes the literal deterministic across sessions. Upper-case hex is
  Snowflake's own binary-to-string convention.
* ``UUID`` becomes the bare quoted canonical text. Snowflake's UUID page says
  "The ANSI literal form of UUID is supported as input" and inserts a quoted
  canonical string; there is no ``::uuid`` suffix to add.

**INTERVAL stays unimplemented on purpose.** ``timedelta`` has no branch here,
so the base's explicit ``TypeError`` is the answer. Snowflake's interval
*constant* (the ``INTERVAL '...'`` keyword form) is a date-arithmetic operand
only -- the page says such constants "can't be inserted into a column that has
an interval data type" -- and the interval *data types* take a string whose
shape depends on the column's qualifier (``+Y-MM`` for year-month,
``+D HH24:MI:SS.F`` for day-time), a qualifier a value node does not carry.
A ``timedelta`` also holds days, seconds and microseconds, never years or
months, and Snowflake's two interval families cannot be mixed, so no single
qualifier could carry an arbitrary ``timedelta`` faithfully.

The tier-1 forms (NULL / booleans / numbers / strings / dates / times /
timestamps) are the base's and are not overridden here: Snowflake's grammar
spells them exactly as core does -- ``TRUE`` / ``FALSE`` keywords, numeric
constants taken verbatim (``repr`` for floats, ``str`` for ``Decimal``),
strings with doubled single quotes, and quoted ISO 8601 text for the three
temporal types. The base's refusal of NaN and the infinities is Snowflake's
answer too: the FLOAT special values ``'NaN'`` / ``'inf'`` require quotes, so
they are never a bare numeric literal.

**not server-verified** -- this repository reaches no Snowflake instance, so
every spelling above is transcribed from the official documentation, quoted
per branch, and checked only as a rendering assertion. When a live server
contradicts a spelling here, change the spelling, not the test.

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

import uuid
from typing import Any


class SnowflakeLiteralValueMixin:
    """Snowflake's tier-2 branches of :meth:`format_literal`.

    Stands alone rather than inheriting the base, and the dialect composes it
    ahead of :class:`SQLDialectBase` -- the one base that defines
    ``format_literal`` -- because a mixin placed after the class it overrides
    never wins.
    """

    def format_literal(self, value: Any) -> str:
        """Render *value* as inline SQL text, Snowflake's spelling where it has one.

        Args:
            value: The host value to write into the statement.

        Returns:
            The escaped literal text, without a bind parameter.

        Raises:
            TypeError: The base implementation refuses a type Snowflake has no
                literal form for -- ``timedelta`` among them, which is the
                documented answer rather than a gap.
        """
        if isinstance(value, (bytes, bytearray)):
            # Rendered from the bytes rather than from the base64 spelling an
            # artifact carries: only the dialect layer knows which text form
            # its engine accepts. The digits go through ``format_literal`` so
            # the quoting is the base's, never a second copy of it.
            hex_text = bytes(value).hex().upper()
            return f"TO_BINARY({self.format_literal(hex_text)}, 'HEX')"
        if isinstance(value, uuid.UUID):
            # The canonical 8-4-4-4-12 text is exactly the pattern the UUID
            # page describes, and quoting stays the base's escaping.
            return self.format_literal(str(value))
        return super().format_literal(value)
