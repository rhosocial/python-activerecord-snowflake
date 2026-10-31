# src/rhosocial/activerecord/backend/impl/snowflake/expression/wildcard.py
"""Snowflake's own wildcard spellings: ``* EXCLUDE`` / ``* ILIKE`` and ``COUNT(t.*)``.

Core splits the one asterisk into two by grammar position (spec 4.10): the
select-list ``*`` expands columns and belongs to ``AllColumnsWildcard``, while
``COUNT(*)``'s asterisk counts rows and belongs to ``RowCountWildcard``.  Core
draws the line at the bare asterisk -- ``RowCountWildcard`` accepts no relation,
because standard ``COUNT(*)`` never qualifies it.

Snowflake then adds two spellings core deliberately leaves to the backends that
have them, both documented on the ``COUNT`` reference page:

* ``COUNT(<alias>.*)`` -- "Returns the number of records that don't contain any
  NULL values."  That is not the question ``COUNT(*)`` answers (``COUNT(*)`` is
  the total number of records, NULLs included), so it is a different node rather
  than a flag on the same one, exactly as PostgreSQL's own row-count wildcard is.
* ``* ILIKE '<pattern>'`` / ``* EXCLUDE <col> | ( <col>, ... )`` -- a filter on
  the expansion, valid only in a SELECT list or GROUP BY on this server.  The
  page states the two keywords *can't be combined in a single call*, so the node
  refuses a request that carries both instead of rendering SQL the parser will
  reject.

**Evidence level: not server-verified.**  There is no Snowflake instance
reachable from this repository.  Every claim above is transcribed from

  https://docs.snowflake.com/en/sql-reference/functions/count

(the ``*`` argument's own text, including its worked ``COUNT(n.*)`` example),
and both ``SELECT``-list spellings are named there as valid "only in a SELECT
list or GROUP BY clause".  Nothing here was measured; a rendering assertion is
not a measurement.

**Known core gap, recorded rather than worked around.**  Core's shared
``format_function_call`` answers a ``RowCountWildcard`` argument with the bare
asterisk *before* any formatter is consulted, so
``FunctionCall(dialect, "COUNT", SnowflakeRowCountWildcard(...))`` renders
``COUNT(*)`` even though the node carries a relation.  The qualified spelling is
therefore reachable through the node's own ``to_sql()`` (and through a clause
that dispatches to it), not through the aggregate's factory -- the same gap
PostgreSQL's derived row-count wildcard has, and fixing it means changing core's
shared formatter, which this branch does not do.  The behaviour is pinned in
``test_snowflake_wildcards.py`` so a change in core fails there rather than
passing quietly.
"""

from typing import Optional, Sequence, Union, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.core import (
    AllColumnsWildcard,
    RowCountWildcard,
)

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase
    from rhosocial.activerecord.backend.expression.sources import NamedRelationRef


def _validate_filter(
    ilike: Optional[str],
    exclude: Optional[Union[str, Sequence[str]]],
) -> None:
    """Refuse a filter combination or shape Snowflake's grammar does not take.

    Called from both nodes' constructors, so a malformed filter is refused where
    it is written rather than at render time -- the same reason the branch nodes
    validate in ``__init__``.

    Raises:
        TypeError: A pattern or a column name is not a string, or ``exclude`` is
            neither a string nor a sequence of strings.
        ValueError: Both keywords are given (the reference says they cannot be
            combined), or a filter is given empty.
    """
    if ilike is not None and exclude is not None:
        raise ValueError(
            "Snowflake's * ILIKE and * EXCLUDE keywords can't be combined in a "
            "single call; ask for one or the other."
        )
    if ilike is not None:
        if not isinstance(ilike, str):
            raise TypeError(
                f"* ILIKE takes one pattern string, got {type(ilike).__name__}"
            )
        if not ilike:
            raise ValueError("* ILIKE needs a pattern: an empty pattern filters nothing")
        return
    if exclude is None:
        return
    if isinstance(exclude, str):
        if not exclude:
            raise ValueError("* EXCLUDE needs a column name or a list of them")
        return
    if isinstance(exclude, (list, tuple)):
        if not exclude:
            raise ValueError("* EXCLUDE needs at least one column name")
        for column in exclude:
            if not isinstance(column, str):
                raise TypeError(
                    f"* EXCLUDE takes column names, got {type(column).__name__}"
                )
        return
    raise TypeError(
        f"* EXCLUDE takes a column name or a sequence of them, got "
        f"{type(exclude).__name__}"
    )


class SnowflakeAllColumnsWildcard(AllColumnsWildcard):
    """Snowflake's filtered all-columns wildcard: ``[* | rel.*] [ILIKE p | EXCLUDE c]``.

    The unfiltered forms are core's: a bare ``*`` or a qualified ``rel.*``.  What
    this node adds is the Snowflake-only filter, which is a second thing to say
    about the same expansion rather than a different expansion -- so it extends
    the core node instead of replacing it, and core's ``format_all_columns_wildcard``
    still renders the asterisk itself.

    Args:
        dialect: The dialect that renders the node.
        relation: The relation whose columns the expansion spans, or ``None`` for
            the bare ``*``.  Rendered as the query's own spelling for it, which is
            core's rule and not restated here.
        ilike: A single pattern; renders ``* ILIKE '<pattern>'``.
        exclude: One column name or a sequence of them; renders
            ``* EXCLUDE (<c1>, <c2>)``.  A single name renders bare, without
            parentheses, because the reference shows both spellings.

    Raises:
        TypeError: The pattern or a column name is not a string.
        ValueError: Both ``ilike`` and ``exclude`` are given.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        relation: Optional["NamedRelationRef"] = None,
        *,
        ilike: Optional[str] = None,
        exclude: Optional[Union[str, Sequence[str]]] = None,
    ):
        _validate_filter(ilike, exclude)
        super().__init__(dialect, relation=relation)
        self.ilike = ilike
        self.exclude = exclude


class SnowflakeRowCountWildcard(RowCountWildcard):
    """``COUNT(<alias>.*)`` -- rows of *relation* with no NULL, not rows of the join.

    Core's ``RowCountWildcard`` is the bare asterisk and takes no relation by
    contract.  Snowflake accepts the qualified form (and filters it too), and the
    reference defines it as a *different* count -- "the number of records that
    don't contain any NULL values" -- so it is a derived node here, not a flag on
    core's.

    With no relation this renders ``*`` and is the plain ``COUNT(*)``; the
    relation is what makes the qualified form possible at all.

    Args:
        dialect: The dialect that renders the node.
        relation: The relation whose rows are counted, or ``None`` for ``*``.
        ilike: A single pattern; renders ``... ILIKE '<pattern>'``.
        exclude: One column name or a sequence of them.

    Raises:
        TypeError: The pattern or a column name is not a string.
        ValueError: Both ``ilike`` and ``exclude`` are given.  Note this is the
            same rule as ``SnowflakeAllColumnsWildcard``: the reference states it
            once, for the argument, not per clause.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        relation: Optional["NamedRelationRef"] = None,
        *,
        ilike: Optional[str] = None,
        exclude: Optional[Union[str, Sequence[str]]] = None,
    ):
        _validate_filter(ilike, exclude)
        super().__init__(dialect)
        self.relation = relation
        self.ilike = ilike
        self.exclude = exclude


__all__ = [
    "SnowflakeAllColumnsWildcard",
    "SnowflakeRowCountWildcard",
]
