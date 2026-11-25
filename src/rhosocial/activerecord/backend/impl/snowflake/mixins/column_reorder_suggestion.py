# src/rhosocial/activerecord/backend/impl/snowflake/mixins/column_reorder_suggestion.py
"""Snowflake's column-reorder change suggestion.

Snowflake's ``ALTER TABLE`` grammar has no column-position clause:

* ``ADD [ COLUMN ] ...`` appends a column at the end of the table;
* ``ALTER | MODIFY [ COLUMN ] ...`` changes a column's type, default,
  nullability, comment or policy -- never its ordinal position;
* neither branch carries ``FIRST`` / ``AFTER`` or any equivalent placement
  keyword.

Reordering columns therefore requires rebuilding the table and copying its
rows. The frozen decision point cannot describe that chain: it carries column
*names* (``old_order`` / ``new_order`` / ``reordered_columns``) but no column
types, so even a ``CREATE TABLE`` node cannot be built from it. Core has no
reorder expression node to put in an action chain, and inventing one would be
inventing SQL. The explicit ``False`` state is returned instead of ``None`` so
a caller can report the gap as "unsupported" rather than "nothing to do".

Evidence: the ``tableColumnAction`` production of ``ALTER TABLE``,
https://docs.snowflake.com/en/sql-reference/sql/alter-table (read 2026-11-25).
The dialect also declares ``supports_multi_action_alter_table() == False``:
one action per statement, with no positional action among them.
"""
from dataclasses import replace

from rhosocial.activerecord.backend.suggestion.definitions import (
    ColumnReorderSuggestion,
)


class SnowflakeColumnReorderSuggestionMixin:
    """Answer the column-reorder decision point as explicitly unsupported."""

    def suggest_column_reorder(
        self, point: ColumnReorderSuggestion
    ) -> ColumnReorderSuggestion:
        """Return ``point`` with ``operations=False`` (unaddressable).

        ``dataclasses.replace`` keeps the table name and the two column orders
        on the answer, so the caller sees exactly which request was refused.
        No expression instances are constructed and no SQL is rendered.
        """
        return replace(point, operations=False)


__all__ = ["SnowflakeColumnReorderSuggestionMixin"]
