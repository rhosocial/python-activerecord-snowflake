# src/rhosocial/activerecord/backend/impl/snowflake/mixins/column_suggestion.py
"""Snowflake's answer to "what column does this common Python type mean here".

:class:`SnowflakeColumnSuggestionMixin` fills the closed entry list of
:data:`~rhosocial.activerecord.backend.expression.column_suggestions.COLUMN_TYPE_ENTRIES`
with the column class each Python type gets on Snowflake, and declares which
column-class operations this server can actually perform.

Evidence level: 文档（待云验）
---------------------------
**Every entry in this module is read from Snowflake's official documentation.
No Snowflake instance was reachable while this table was written, so nothing
here is 活验-backed.** Each entry group below carries the URL it was read from,
and the ones whose answer is a *judgement* rather than a fact are marked
provisional. A cloud probe is what turns any of these from 文档（待云验） into
实测; until then this table is the backend's stated position, not a verified
one.

The one thing this module deliberately does **not** do is restate storage
facts. ``FLOAT`` collapsing onto ``DOUBLE``, ``TEXT`` onto ``VARCHAR``,
``INT`` onto ``NUMBER(38, 0)`` -- those belong to the DDL layer and are
already carried there (see :mod:`..expression.types` and
:class:`~.types.SnowflakeTypeSupportMixin`). A column class says what a value
can *do*, so where a storage collapse would change no operation, the collapse
is not mentioned here at all; where it would, the docstring says so and points
at the DDL side.

Two provisional cells
---------------------
``dict`` and ``list``/``tuple``/``set``/``frozenset`` are the cells the plan's
§12 table marks 🔶, and they are provisional **in the plan's own sense**: not
because Snowflake's behaviour is unknown (it is documented), but because the
*design decision* is open -- 议题 B, the three semi-structured concepts.

The facts 议题 B turns on, all three from
<https://docs.snowflake.com/en/sql-reference/data-types-semistructured>:

* ``VARIANT``, ``OBJECT`` and ``ARRAY`` are **three distinct server types**,
  each with its own section and its own row in
  <https://docs.snowflake.com/en/sql-reference/intro-summary-data-types>;
* the same page's ``DESC TABLE`` example reports them **verbatim and
  separately** -- declaring ``ARRAY`` yields ``type`` = ``ARRAY``, not
  ``VARIANT``;
* semantically they are one container family: ``OBJECT`` "can directly contain
  a VARIANT value", ``ARRAY`` likewise, and ``VARIANT`` "can contain a value
  of any other data type";
* an array's elements are **always** ``VARIANT`` -- "Snowflake doesn't support
  arrays of elements of a specific non-VARIANT type".

So this backend parses ``VARIANT``/``OBJECT``/``ARRAY`` to one concept (a
*design choice*, documented in this repo's
``.claude/plan/2026-10-08/secondary-gaps-investigation.md`` §B, not a
limitation the docs impose), and the column table follows that same choice:
``dict`` is a document and ``list`` is a document holding an array. The
alternative -- three core concepts, or ``ArrayColumn`` for lists backed by the
``ARRAY_SIZE``/``FLATTEN``/``ARRAY_CONTAINS`` family
(<https://docs.snowflake.com/en/sql-reference/functions-semistructured>) -- is
exactly what 议题 B has to decide. Until it does, ``JSONColumn`` for both is the
answer, and it is marked provisional wherever it is stated.
"""

from __future__ import annotations

import datetime
import decimal
import enum
import uuid
from typing import Any, Dict, Tuple, Type

from rhosocial.activerecord.backend.dialect.mixins.column_suggestion import (
    ColumnSuggestionMixin,
)
from rhosocial.activerecord.backend.expression.column_types import (
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    DateTimeColumn,
    DecimalColumn,
    FloatColumn,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    UUIDColumn,
)

#: The evidence level of this whole table, stated once so a reader (and a test)
#: can find it without reading every entry. See the module docstring.
SNOWFLAKE_COLUMN_SUGGESTION_EVIDENCE = "文档（待云验）"

#: The entries whose answer is a provisional decision rather than a settled
#: one, because 议题 B (Snowflake's VARIANT / OBJECT / ARRAY concepts) has not
#: been decided. Exported so the marking is checkable from outside instead of
#: only being prose: see the test that asserts every one of these is present in
#: the table and documented as provisional.
SNOWFLAKE_PROVISIONAL_COLUMN_SUGGESTIONS: Tuple[Any, ...] = (
    dict,
    list,
    tuple,
    set,
    frozenset,
)


class SnowflakeColumnSuggestionMixin(ColumnSuggestionMixin):
    """Snowflake's column-class suggestions, and the operations it supports.

    Subclasses core's :class:`~...dialect.mixins.column_suggestion.ColumnSuggestionMixin`
    so this backend carries the protocol's own resolution
    (:meth:`~...column_suggestion.ColumnSuggestionMixin.column_class_for`)
    unchanged -- what differs here is the *answer*, not the question.

    No entry is :data:`~...expression.column_suggestions.UNSUPPORTED`: every one
    of the eighteen has a column class here, including ``dict`` and the four
    sequence types. That is a real difference from the backends with no JSON
    functions at all (Firebird), where an entry genuinely has nowhere to go.
    """

    #: Snowflake's full answer, one column class per entry of the closed core
    #: list. Read in groups; each group names the page it was read from.
    #:
    #: **Group 1 -- text and binary.** ``VARCHAR`` carries strings and ``BINARY``
    #: carries bytes; ``STRING``/``TEXT`` are listed as "Synonymous with
    #: VARCHAR" and ``VARBINARY`` as "Synonymous with BINARY", which is a
    #: storage fact and changes no text or byte operation.
    #: 文档（待云验）<https://docs.snowflake.com/en/sql-reference/data-types-text>
    COLUMN_TYPE_SUGGESTIONS: Dict[Any, Type[ColumnBase]] = {
        str: StringColumn,
        bytes: BinaryColumn,
        bytearray: BinaryColumn,
        # **Group 2 -- numbers.** ``INT``/``INTEGER``/... are "Synonymous with
        # NUMBER" at NUMBER(38, 0); ``DECIMAL``/``NUMERIC`` are "Synonymous
        # with NUMBER" and keep precision and scale (default 38, 0; maximum
        # scale 37). Three classes rather than one ``NumericColumn`` because
        # the three value families are what the operations are about: integer
        # arithmetic, decimal arithmetic with explicit scale, and IEEE-754
        # floating point. ``FLOAT``/``FLOAT4``/``FLOAT8`` and
        # ``DOUBLE``/``DOUBLE PRECISION``/``REAL`` being one 64-bit storage type
        # is a DDL-side collapse (the DataType layer renders the requested
        # spelling) and does not make a float behave differently here.
        # 文档（待云验）<https://docs.snowflake.com/en/sql-reference/data-types-numeric>
        int: IntegerColumn,
        decimal.Decimal: DecimalColumn,
        float: FloatColumn,
        # **Group 3 -- truth.** Snowflake has a single logical type, ``BOOLEAN``,
        # which "can have TRUE or FALSE values" plus NULL for UNKNOWN, and is
        # usable in both expressions and predicates -- so the boolean family
        # needs no substitute here.
        # 文档（待云验）<https://docs.snowflake.com/en/sql-reference/data-types-logical>
        bool: BooleanColumn,
        # **Group 4 -- date and time.** ``DATE``, ``TIME``, and the three
        # ``TIMESTAMP_*`` variants are distinct server types, and ``TIMESTAMP``
        # is an alias that is "never stored in tables" (its variant comes from
        # the ``TIMESTAMP_TYPE_MAPPING`` session parameter, ``TIMESTAMP_NTZ`` by
        # default). Core has one ``DateTimeColumn`` for all of them and no
        # ``DateColumn`` / ``TimeColumn`` yet, so ``date`` and ``time`` answer
        # it too; the split is a core gap, not a Snowflake one. Which variant
        # a *value* gets -- ``TIMESTAMP_NTZ`` for a naive datetime,
        # ``TIMESTAMP_TZ`` for an aware one -- is the DataType layer's decision.
        # 文档（待云验）<https://docs.snowflake.com/en/sql-reference/data-types-datetime>
        datetime.date: DateTimeColumn,
        datetime.time: DateTimeColumn,
        datetime.datetime: DateTimeColumn,
        # **Group 5 -- duration.** ``NumericColumn``, and the reason is *not*
        # that Snowflake lacks an interval type: the date & time page documents
        # twelve storable interval data types ("To store interval values in a
        # column, you can use interval data types") down to
        # ``INTERVAL DAY TO SECOND``. Two things keep the answer numeric:
        # core declares no interval column class yet, so there is nothing more
        # precise to answer; and Snowflake's own interval storage is
        # restricted enough that it is not the portable default -- "VARIANT
        # values can't contain interval values", and clustered tables, dynamic
        # tables and Iceberg tables "can't have interval columns". If core ever
        # adds an interval column class, this cell is the one to revisit.
        # 文档（待云验）<https://docs.snowflake.com/en/sql-reference/data-types-datetime>
        datetime.timedelta: NumericColumn,
        # **Group 6 -- UUID.** ``UUIDColumn`` at every version. Core's
        # ``UUIDColumn`` carries no UUID-specific operator (portable SQL has
        # none), so the arrival of a native ``UUID`` type in server 10.2
        # changes the DDL spelling and nothing on the operation side -- the
        # version gate lives in ``SNOWFLAKE_UUID_TYPE_MIN_VERSION`` and has no
        # business branching this table.
        # 文档（待云验）<https://docs.snowflake.com/en/sql-reference/data-types-uuid>
        uuid.UUID: UUIDColumn,
        # **Group 7 -- semi-structured documents. 🔶 PROVISIONAL, pending 议题 B.**
        # A ``dict`` is a document; the DDL layer spells it ``VARIANT`` and the
        # operation surface is ``GET`` / ``GET_PATH`` / the ``:`` operator, all
        # of which take "An expression that evaluates to a VARIANT, OBJECT, or
        # ARRAY column". ``OBJECT`` would serve the same operations, but
        # choosing between the two is 议题 B's question, not this table's.
        # 文档（待云验）<https://docs.snowflake.com/en/sql-reference/functions/get_path>
        dict: JSONColumn,
        # **Group 8 -- sequences. 🔶 PROVISIONAL, pending 议题 B.**
        # Snowflake's ``ARRAY`` is a real type and its function family
        # (``ARRAY_SIZE``, ``ARRAY_SLICE``, ``ARRAY_CONTAINS``, ``FLATTEN``,
        # ...) is real, so this is *not* "Snowflake cannot do arrays". It is:
        # an array's elements are always ``VARIANT`` ("Snowflake doesn't
        # support arrays of elements of a specific non-VARIANT type"), which is
        # why the document route is the honest default here while core has no
        # array column class whose Snowflake operations are written and
        # verified. ``tuple`` rides along because Snowflake's other structured
        # container, ``ARRAY(<element type>)``, is not modelled by this backend
        # either. Declaring ``UseColumnType(ArrayColumn)`` explicitly remains
        # the way to ask for the array surface before 议题 B is decided.
        # 文档（待云验）<https://docs.snowflake.com/en/sql-reference/data-types-semistructured>
        list: JSONColumn,
        tuple: JSONColumn,
        set: JSONColumn,
        frozenset: JSONColumn,
        # **Group 9 -- enumerations.** Snowflake has no ``ENUM`` type -- it is
        # absent from the summary-of-data-types table -- so an enum is carried
        # as text, which is what ``StringColumn`` means everywhere.
        # 文档（待云验）<https://docs.snowflake.com/en/sql-reference/intro-summary-data-types>
        enum.Enum: StringColumn,
    }

    def supports_column_operation(self, column_name: str, op: str) -> bool:
        """Snowflake narrows nothing on this backend. 文档（待云验）

        The protocol's default is ``True``, and a backend that over-declares is
        wrong in the direction that hides an incompatibility. A docs-only pass
        found **no** operation to narrow, and the two that looked like
        candidates both came back supported:

        * ``ilike`` -- Snowflake has a native ``[ NOT ] ILIKE``, "Performs a
          case-insensitive comparison to determine whether a string matches",
          with its own ``ESCAPE`` clause. Five of the ten backends have to
          synthesise it as ``LOWER(x) LIKE LOWER(y)`` and pay for it; this one
          does not, so narrowing it here would refuse a query that works.
          文档（待云验）<https://docs.snowflake.com/en/sql-reference/functions/ilike>
        * the JSON path operations ``json_path`` / ``json_value`` -- served by
          ``GET_PATH`` and its ``:`` shorthand, which the reference defines for
          "An expression that evaluates to a VARIANT, OBJECT, or ARRAY column"
          and which this dialect already renders
          (:attr:`~.capabilities.SnowflakeCapabilityMixin._JSON_FUNCTION_NAMES`).
          文档（待云验）<https://docs.snowflake.com/en/sql-reference/functions/get_path>

        **Two candidates were left open rather than answered.** Core's
        ``ArrayColumn`` offers ``array_length`` and ``unnest``, which render
        ``ARRAY_LENGTH(col, dim)`` and ``UNNEST(col)``. Snowflake's documented
        spellings are ``ARRAY_SIZE`` and the ``FLATTEN`` *table* function, and
        neither name appears in the reference's function index. Absence from an
        index is not proof of absence, and the protocol requires narrowing to be
        backed by a real server -- so nothing is narrowed here, and this is
        recorded as a **待云验** probe: render ``ARRAY_LENGTH`` against a live
        instance, and if it is rejected, narrow ``ArrayColumn.array_length``
        and ``ArrayColumn.unnest`` then. The same probe should cover whether
        ``FLATTEN`` can be reached from the ``UNNEST`` shape at all, because
        that decides whether the explicit ``UseColumnType(ArrayColumn)`` escape
        hatch works on Snowflake before 议题 B is settled.

        Args:
            column_name: The column class name, as ``type(column).__name__``.
            op: The operation name, as the public method that provides it.

        Returns:
            ``True`` for every ``(column_name, op)`` pair.
        """
        return True


__all__ = [
    "SNOWFLAKE_COLUMN_SUGGESTION_EVIDENCE",
    "SNOWFLAKE_PROVISIONAL_COLUMN_SUGGESTIONS",
    "SnowflakeColumnSuggestionMixin",
]