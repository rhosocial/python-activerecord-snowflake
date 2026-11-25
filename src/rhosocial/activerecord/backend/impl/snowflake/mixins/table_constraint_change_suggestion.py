# src/rhosocial/activerecord/backend/impl/snowflake/mixins/table_constraint_change_suggestion.py
"""Snowflake's table-constraint-change change suggestion.

Re-evaluated against core commit ``52bc48a``: the decision point now carries
``old_constraint_declarations`` / ``new_constraint_declarations`` as real
``TableConstraint`` nodes whose ``branch`` keeps PK / UNIQUE / FK / CHECK, so an
``AddTableConstraintAction`` can be built from them without guessing. The old
objection that a declaration could not be reconstructed is resolved; the answer
below is a grammar/capability judgement about the whole old -> new transition,
not a loss of information in the point.

Snowflake's ``constraintAction`` grammar is real but narrow:

* ``ADD outoflineConstraint`` -- every kind, with a wide property set;
* ``RENAME CONSTRAINT <name> TO <new>``;
* ``{ ALTER | MODIFY }`` -- only three mutable properties;
* ``DROP { CONSTRAINT <name> | PRIMARY KEY | UNIQUE | FOREIGN KEY } ( cols )``.

ADD is expressible with the enriched declarations. A complete change answer
also has to remove what the new declaration no longer declares, and that half
is where the grammar and the available nodes stop us:

1. Neither side has a guard. ``supports_drop_constraint_if_exists()`` and
   ``supports_add_constraint_if_not_exists()`` are both ``False``: there is no
   two-anchor ``IF EXISTS`` / ``IF NOT EXISTS`` gate around the drop of an old
   declaration and the add of a new one, so an unguarded chain would be guessing
   at live catalog state.
2. ``DROP CONSTRAINT <name>`` needs a name. ``DropTableConstraintAction`` carries
   only ``constraint_name``; the distinctive ``DROP PRIMARY KEY | UNIQUE |
   FOREIGN KEY (cols)`` shape is in Snowflake's grammar and recorded by
   ``supports_drop_constraint_by_kind()`` but has no node here. Core synthesizes
   a table PRIMARY KEY with ``name=None``, so exactly the common unnamed PK case
   cannot be dropped with any available action.
3. CHECK is by name twice over: it is not one of the drop-by-kind alternatives,
   and the reference requires ``constraint_name`` for CHECK. An unnamed CHECK
   cannot be removed at all; a CHECK cannot be added by ``ALTER TABLE`` on a
   hybrid table, which this backend does not model.

Because the answer has to cover the reconstructed kinds in the point, not only
the addable subset, the explicit ``False`` (unaddressable) is returned rather
than a partial chain or a guessed drop.

Evidence: https://docs.snowflake.com/en/sql-reference/sql/alter-table and
https://docs.snowflake.com/en/sql-reference/sql/create-table-constraint
(read 2026-10-12 and 2026-11-25), the ``supports_*_constraint`` probes in
:mod:`..constraint`, and the IF EXISTS / IF NOT EXISTS answers in :mod:`..ddl`.
"""

from dataclasses import replace

from rhosocial.activerecord.backend.suggestion.definitions import (
    TableConstraintChangeSuggestion,
)


class SnowflakeTableConstraintChangeSuggestionMixin:
    """Answer the table-constraint-change decision point as unsupported."""

    def suggest_table_constraint_change(
        self, point: TableConstraintChangeSuggestion
    ) -> TableConstraintChangeSuggestion:
        """Return ``point`` with ``operations=False`` (capability-blocked)."""
        return replace(point, operations=False)


__all__ = ["SnowflakeTableConstraintChangeSuggestionMixin"]
