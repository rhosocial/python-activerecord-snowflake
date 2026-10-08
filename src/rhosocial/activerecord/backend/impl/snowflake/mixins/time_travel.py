# src/rhosocial/activerecord/backend/impl/snowflake/mixins/time_travel.py
"""SnowflakeTimeTravelMixin — time travel query support.

Time travel is a *clause*, never part of an object's name. Snowflake spells it
``AT`` / ``BEFORE`` appended after the relation reference::

    SELECT * FROM "DB"."APP"."events" AT(OFFSET => -60)

Keeping it here is what lets the relation itself stay a plain three-level name.
Folding the suffix into the name instead is what used to force a per-engine
``format_table`` override: the name renderer would have to know about
clauses, and ``db.schema.table`` could no longer come from the shared one.
"""

from typing import Any, Dict, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.datetime import (
        TemporalOptionsExpression,
    )


class SnowflakeTimeTravelMixin:
    """Mixin for Snowflake time travel query support.

    Implements ``format_temporal_options``, the clause hook that the shared
    ``format_named_relation`` calls when a reference carries temporal options.
    Snowflake deliberately does not claim the generic
    :class:`~...dialect.protocols.TemporalTableSupport`: that protocol is the
    SQL-standard ``FOR SYSTEM_TIME AS OF`` form, which is not what Snowflake
    speaks.
    """

    #: The two time-travel keywords Snowflake accepts, in its own spelling.
    _TIME_TRAVEL_KEYWORDS = ("AT", "BEFORE")

    def supports_time_travel(self) -> bool:
        """Snowflake supports time travel queries."""
        return True

    def format_time_travel_point(self, keyword: str, point: Tuple[str, Any]) -> str:
        """Render one ``AT`` / ``BEFORE`` clause.

        Args:
            keyword: ``AT`` or ``BEFORE``, in any case.
            point: A ``(kind, value)`` pair where *kind* is ``OFFSET``,
                ``TIMESTAMP`` or ``STATEMENT``. An offset counts seconds and is
                emitted unquoted; the other two are literals and are quoted and
                escaped.

        Returns:
            The clause as SQL text.

        Raises:
            UnsupportedFeatureError: *keyword* is not a Snowflake time-travel
                keyword, so there is no clause this dialect can render.
            ValueError: *point* is not a ``(kind, value)`` pair.
        """
        clause = str(keyword).upper()
        if clause not in self._TIME_TRAVEL_KEYWORDS:
            raise UnsupportedFeatureError(
                self.name,
                f"temporal option {clause}",
                suggestion=(
                    "Snowflake time travel uses "
                    f"{' / '.join(self._TIME_TRAVEL_KEYWORDS)}, not {clause}."
                ),
            )
        try:
            kind, value = point
        except (TypeError, ValueError):
            raise ValueError(
                f"{clause} expects a (kind, value) pair, got {point!r}"
            ) from None
        kind = str(kind).upper()
        if kind == "OFFSET":
            return f"{clause}(OFFSET => {int(value)})"
        escaped = self._escape_sql_string(str(value))
        return f"{clause}({kind} => '{escaped}')"

    def format_temporal_options(
        self, expr: "TemporalOptionsExpression"
    ) -> Tuple[str, tuple]:
        """Render a relation's time-travel clause.

        The options mapping is a single ``at`` or ``before`` key whose value is
        a ``(kind, value)`` pair -- the same shape
        :class:`~...expression.ddl.stream.SnowflakeCreateStreamExpression`
        takes, so one point definition serves both statements.

        Args:
            expr: Carrying the ``options`` mapping.

        Returns:
            Tuple of (SQL clause, empty params tuple).

        Raises:
            ValueError: no temporal options were given.
            UnsupportedFeatureError: an option Snowflake cannot express.
        """
        options: Dict[str, Any] = getattr(expr, "options", None) or {}
        if not options:
            raise ValueError(
                "Temporal options cannot be empty. If no temporal options are needed, "
                "don't call format_temporal_options."
            )
        if len(options) > 1:
            raise UnsupportedFeatureError(
                self.name,
                "multiple time-travel points",
                suggestion=(
                    "Snowflake accepts one time-travel point per relation; "
                    f"got {sorted(options)}."
                ),
            )
        keyword, point = next(iter(options.items()))
        return self.format_time_travel_point(keyword, point), ()
