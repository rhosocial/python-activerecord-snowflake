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

from typing import Tuple, TYPE_CHECKING

from ..expression.wildcard import (
    SnowflakeAllColumnsWildcard,
    SnowflakeRowCountWildcard,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.bases import BaseExpression


class SnowflakeWildcardMixin:
    """Render Snowflake's filtered wildcards, and delegate everything else.

    Both methods test the *class*, never for a missing attribute: core's
    ``AllColumnsWildcard`` has no ``ilike`` at all, and probing for one anyway is
    the reflection the project's rule 9.8 forbids.  Anything that is not the
    Snowflake node has no filter to render, so ``super()`` answers it -- which
    keeps core's bare ``*`` and ``rel.*`` paths byte-identical.
    """

    def format_all_columns_wildcard(
        self, expr: "BaseExpression"
    ) -> Tuple[str, tuple]:
        """Render ``*`` / ``rel.*``, optionally followed by ``ILIKE`` / ``EXCLUDE``.

        The asterisk half is core's, including the rule that the qualifier is the
        spelling the query uses (the alias when aliased); this method only appends
        the filter, so the two spellings cannot drift apart.

        Args:
            expr: The wildcard being rendered.

        Returns:
            A ``(sql, params)`` tuple; ``params`` is empty (the pattern is
            inlined, because a SELECT-list filter is not a bind parameter).
        """
        if not isinstance(expr, SnowflakeAllColumnsWildcard):
            return super().format_all_columns_wildcard(expr)
        return self._render_snowflake_wildcard(expr)

    def format_row_count_wildcard(self, expr: "BaseExpression") -> Tuple[str, tuple]:
        """Render ``COUNT``'s argument: the bare ``*``, or Snowflake's qualified form.

        Core's node renders ``*`` and carries no relation; the Snowflake node adds
        one, and the reference defines the result as a different number.  Both
        forms go through the same body renderer, so the qualifier and the filter
        are spelled once for the two positions.

        Args:
            expr: The wildcard being rendered.

        Returns:
            A ``(sql, params)`` tuple; ``params`` is empty.
        """
        if not isinstance(expr, SnowflakeRowCountWildcard):
            return super().format_row_count_wildcard(expr)
        return self._render_snowflake_wildcard(expr)

    # ------------------------------------------------------------------
    # The two pieces both positions share.
    # ------------------------------------------------------------------

    def _render_snowflake_wildcard(self, expr) -> Tuple[str, tuple]:
        """The ``*`` / ``rel.*`` body plus whichever filter the node carries.

        The node refuses ``ilike`` and ``exclude`` together at construction (the
        reference says they cannot be combined), so this reads at most one.
        """
        sql, params = self._render_asterisk_body(expr)
        if expr.ilike is not None:
            pattern = self.inline_sql_literal(expr.ilike)
            return f"{sql} ILIKE {pattern}", params
        if expr.exclude is not None:
            return f"{sql}{self._render_exclude_suffix(expr.exclude)}", params
        return sql, params

    def _render_asterisk_body(self, expr) -> Tuple[str, tuple]:
        """The ``*`` or ``rel.*`` half.

        Delegated to core's all-columns renderer, because "which name does this
        query call the relation" is the same question in both positions and core
        already answers it (alias when aliased, otherwise the qualified name).
        The node is handed over as an ``AllColumnsWildcard``, so the rule is not
        restated here where it could drift.
        """
        from rhosocial.activerecord.backend.expression.core import (
            AllColumnsWildcard,
        )

        view = AllColumnsWildcard(self, relation=expr.relation)
        sql, params = super().format_all_columns_wildcard(view)
        return sql, tuple(params)

    def _render_exclude_suffix(self, exclude) -> str:
        """`` EXCLUDE <col>`` or `` EXCLUDE (<c1>, <c2>)``.

        The reference shows both shapes -- ``* EXCLUDE col`` and ``* EXCLUDE
        (col1, col2)`` -- and writes a single name without parentheses.  Names
        are identifier-quoted, because that is what they are.
        """
        if isinstance(exclude, str):
            return f" EXCLUDE {self.format_identifier(exclude)}"
        rendered = ", ".join(self.format_identifier(name) for name in exclude)
        return f" EXCLUDE ({rendered})"


__all__ = ["SnowflakeWildcardMixin"]
