# src/rhosocial/activerecord/backend/impl/snowflake/mixins/wildcard.py
"""Snowflake's wildcard formatters: the two asterisk positions, both spellable.

Core split the asterisk by grammar position (spec 4.10) and gave each position
its own formatter: ``format_all_columns_wildcard`` for the select list and
RETURNING, ``format_row_count_wildcard`` for ``COUNT``'s argument.  A dialect
overrides the one whose *spelling* differs, and Snowflake's differs in two ways,
both on the ``COUNT`` reference page and in the ``SELECT`` grammar:

* ``COUNT(<alias>.*)`` counts the records that contain no NULL, so the row-count
  position accepts a qualifier here where the standard spelling never does;
* both positions accept a filter -- ``* ILIKE '<pattern>'`` or ``* EXCLUDE
  <col> | ( <col>, ... )``.

Neither override changes the plain forms: a bare ``*`` and a bare ``COUNT(*)``
render exactly as core renders them, and the qualifier/alias rule is core's (the
name the query itself uses), so it is delegated rather than restated.

Each position has one formatter and one formatter only: the two methods below
share no private renderer, because the defect this file was split from was
exactly a shared body reaching two independent spellings.  The grammar overlap
(``*`` / ``rel.*``) is delegated to core's all-columns renderer inside each
method; the Snowflake-only filter is written once per method, so a change to one
position cannot move the other.

**No capability probe sits behind the filter, and that is deliberate.**  The
nodes that carry it (``impl/snowflake/expression/wildcard.py``) exist only in
this backend, so there is no dialect that has the node and lacks the spelling --
a probe would answer a question nobody can ask, and registering one in a
protocol would add public surface for it.  What is gated by a probe is the
*core* wildcard contract, and that is core's ``WildcardSupport``, which this
dialect already satisfies.

**Evidence level: not server-verified.**  Transcribed from
https://docs.snowflake.com/en/sql-reference/functions/count and
https://docs.snowflake.com/en/sql-reference/sql/select ; nothing here was
measured.
"""

from typing import Tuple, Union

from rhosocial.activerecord.backend.expression.core import (
    AllColumnsWildcard,
    RowCountWildcard,
)

from ..expression.wildcard import (
    SnowflakeAllColumnsWildcard,
    SnowflakeRowCountWildcard,
)

class SnowflakeWildcardMixin:
    """Render Snowflake's filtered wildcards, and delegate everything else.

    Both methods test the *class*, never for a missing attribute: core's
    ``AllColumnsWildcard`` has no ``ilike`` at all, and probing for one anyway is
    the reflection the project's rule 9.8 forbids.  Anything that is not the
    Snowflake node has no filter to render, so ``super()`` answers it -- which
    keeps core's bare ``*`` and ``rel.*`` paths byte-identical.
    """

    def format_all_columns_wildcard(
        self, expr: "Union[AllColumnsWildcard, SnowflakeAllColumnsWildcard]"
    ) -> Tuple[str, tuple]:
        """Render ``*`` / ``rel.*``, optionally followed by ``ILIKE`` / ``EXCLUDE``.

        Self-contained: the asterisk half and the filter are both spelled here,
        because this is the select-list position's own grammar.  The asterisk
        half is delegated to core's all-columns renderer (through a core node
        carrying the same relation) so the qualifier rule -- alias when aliased,
        the qualified name otherwise -- is not restated; the filter is
        Snowflake's, and this method is its only writer for this position.

        Args:
            expr: The wildcard being rendered.

        Returns:
            A ``(sql, params)`` tuple; ``params`` is empty (the pattern is
            inlined, because a SELECT-list filter is not a bind parameter).
        """
        if not isinstance(expr, SnowflakeAllColumnsWildcard):
            return super().format_all_columns_wildcard(expr)

        view = AllColumnsWildcard(self, relation=expr.relation)
        sql, params = super().format_all_columns_wildcard(view)
        params = tuple(params)

        if expr.ilike is not None:
            return f"{sql} ILIKE {self.inline_sql_literal(expr.ilike)}", params
        if expr.exclude is not None:
            if isinstance(expr.exclude, str):
                suffix = f" EXCLUDE {self.format_identifier(expr.exclude)}"
            else:
                rendered = ", ".join(self.format_identifier(name) for name in expr.exclude)
                suffix = f" EXCLUDE ({rendered})"
            return f"{sql}{suffix}", params
        return sql, params

    def format_row_count_wildcard(
        self, expr: "Union[RowCountWildcard, SnowflakeRowCountWildcard]"
    ) -> Tuple[str, tuple]:
        """Render ``COUNT``'s argument: the bare ``*``, or Snowflake's qualified form.

        Core's node renders ``*`` and carries no relation; the Snowflake node adds
        one, and the reference defines the result as a different number.  The
        body is spelled here rather than borrowed from the select-list position:
        this formatter owns the row-count spelling outright, including the
        ``*`` / ``rel.*`` body, so the two positions cannot drift together.  The
        relation spelling itself is still delegated to core's all-columns
        renderer, which is the single owner of "which name does this query call
        the relation".

        Args:
            expr: The wildcard being rendered.

        Returns:
            A ``(sql, params)`` tuple; ``params`` is empty.
        """
        if not isinstance(expr, SnowflakeRowCountWildcard):
            return super().format_row_count_wildcard(expr)

        view = AllColumnsWildcard(self, relation=expr.relation)
        sql, params = super().format_all_columns_wildcard(view)
        params = tuple(params)

        if expr.ilike is not None:
            return f"{sql} ILIKE {self.inline_sql_literal(expr.ilike)}", params
        if expr.exclude is not None:
            if isinstance(expr.exclude, str):
                suffix = f" EXCLUDE {self.format_identifier(expr.exclude)}"
            else:
                rendered = ", ".join(self.format_identifier(name) for name in expr.exclude)
                suffix = f" EXCLUDE ({rendered})"
            return f"{sql}{suffix}", params
        return sql, params


__all__ = ["SnowflakeWildcardMixin"]
