# src/rhosocial/activerecord/backend/impl/snowflake/mixins/table_constraint_change_suggestion.py
"""Snowflake's table-constraint-change change suggestion.

Snowflake's ``constraintAction`` grammar is real but narrow:

* ``ADD outoflineConstraint`` -- every kind, with a wide property set;
* ``RENAME CONSTRAINT <name> TO <new>``;
* ``{ ALTER | MODIFY }`` -- only three mutable properties;
* ``DROP { CONSTRAINT <name> | PRIMARY KEY | UNIQUE | FOREIGN KEY } ( cols )``.

Two facts make a complete, honest action chain impossible from the frozen
decision point:

1. The point carries ``old_constraints`` / ``new_constraints`` as dialect
   neutral *projections* (``("params", ...)`` / ``("repr", ...)`` tuples from
   core's ``_freeze``), not expression instances. Constructing the existing
   ``AddTableConstraintAction`` requires a real ``TableConstraint`` node with
   a dialect, a branch, columns and references; none of that can be recovered
   from a projection without inventing a declaration. ``DROP CONSTRAINT`` has
   no ``IF EXISTS`` on Snowflake (``supports_drop_constraint_if_exists()`` is
   ``False``), so there is no guarded drop to lean on either.
2. Drop-by-kind -- Snowflake's distinctive ``DROP PRIMARY KEY (cols)`` shape
   -- has no node on this core: ``DropTableConstraintAction`` carries a
   ``constraint_name`` only. CHECK must be addressed by name, and a CHECK
   cannot be added by ``ALTER TABLE`` on a hybrid table, which this backend
   does not model.

The limited DDL that does exist cannot express an arbitrary old -> new
declaration change with the nodes that are available, so the explicit ``False``
state is returned rather than a guessed chain or silence.

Evidence: https://docs.snowflake.com/en/sql-reference/sql/alter-table and
https://docs.snowflake.com/en/sql-reference/sql/create-table-constraint
(read 2026-10-12 and 2026-11-25), the ``supports_*_constraint`` probes in
:mod:`..constraint`, and ``supports_drop_constraint_if_exists()`` in
:mod:`..ddl`.
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
        """Return ``point`` with ``operations=False`` (unaddressable)."""
        return replace(point, operations=False)


__all__ = ["SnowflakeTableConstraintChangeSuggestionMixin"]
