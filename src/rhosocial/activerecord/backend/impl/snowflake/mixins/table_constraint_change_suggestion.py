# src/rhosocial/activerecord/backend/impl/snowflake/mixins/table_constraint_change_suggestion.py
"""Snowflake's table-constraint-change change suggestion.

A complete old -> new constraint transition has to remove what the new
declaration no longer declares and add what it newly declares.  Snowflake's
``constraintAction`` grammar is real but narrow:

* ``ADD outoflineConstraint`` -- every kind, with a wide property set;
* ``RENAME CONSTRAINT <name> TO <new>``;
* ``{ ALTER | MODIFY }`` -- only three mutable properties;
* ``DROP { CONSTRAINT <name> | PRIMARY KEY | UNIQUE | FOREIGN KEY } ( cols )``.

Core's enriched point carries the live ``TableConstraint`` declarations
(``old_constraint_declarations`` / ``new_constraint_declarations``), whose
``branch`` keeps the kind.  That is enough to build both halves for the key
kinds (PRIMARY KEY / UNIQUE / FOREIGN KEY):

* removal -- ``DropTableConstraintAction(constraint=<decl>)`` rendered as
  ``DROP PRIMARY KEY`` / ``DROP UNIQUE (cols)`` / ``DROP FOREIGN KEY (cols)``;
  a named constraint still uses the by-kind form, so the chain does not depend
  on a name Snowflake may have generated;
* addition -- ``AddTableConstraintAction(<decl>)`` rendered from the same
  declaration;
* a same-name redefinition is drop-then-add, because the old declaration no
  longer matches the new one.

What is still refused, and why the answer is the explicit ``False``
(unaddressable) rather than a partial chain:

1. **A CHECK must be named.**  CHECK is not one of the by-kind alternatives and
   the reference states *"For CHECK constraints, the constraint_name is
   required."*  A named CHECK can be *removed* by name, but an unnamed CHECK
   cannot be removed at all.
2. **A CHECK cannot be added by this node.**  ``ALTER TABLE ... ADD CONSTRAINT
   ... CHECK`` requires ``ENABLE NOVALIDATE`` on a standard table; the
   ``AddTableConstraintAction`` / ``TableConstraint`` nodes do not carry that
   combined property, so a rendered ADD would omit a required token.  A hybrid
   table forbids the ADD outright, and this backend does not model hybrid
   tables.  Any transition whose new side carries a CHECK is therefore refused.
3. **Properties the dialect refuses to render.**  ``ENFORCED`` / ``NOT
   ENFORCED``, ``DEFERRABLE`` / ``INITIALLY``, and the ``NOT VALID`` spelling
   are all declined by this dialect's probes (see :mod:`.constraint`), so an
   ADD carrying one would fail at render time; the suggestion refuses instead.
4. **Kinds with no kind alternative.**  Only PRIMARY KEY / UNIQUE / FOREIGN KEY
   are in the ``DROP`` kind list; an unnamed declaration of any other branch
   has no address, so the transition is refused rather than guessed.

No two-anchor ``IF EXISTS`` / ``IF NOT EXISTS`` guard is emitted:
``supports_drop_constraint_if_exists()`` and
``supports_add_constraint_if_not_exists()`` are both ``False``.  The chain is
driven by the declared old -> new transition, not by live catalogue state.  It
contains only single-action ``AlterTableStatement`` nodes -- never a
``DROP TABLE`` or ``DROP SCHEMA`` -- so the consumer's one-expression ->
one-statement guard holds.

Evidence: https://docs.snowflake.com/en/sql-reference/sql/alter-table and
https://docs.snowflake.com/en/sql-reference/sql/create-table-constraint
(read 2026-10-12 and 2026-11-25), the ``supports_*_constraint`` probes in
:mod:`..constraint`, and the IF EXISTS / IF NOT EXISTS answers in :mod:`..ddl`.
"""

from dataclasses import replace
from enum import Enum
from typing import Any

from rhosocial.activerecord.backend.expression import (
    TableCheckConstraint,
    TableConstraint,
    TableForeignKeyConstraint,
    TablePrimaryKeyConstraint,
    TableUniqueConstraint,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import ConstraintValidation
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddTableConstraintAction,
    AlterTableStatement,
    DropTableConstraintAction,
)
from rhosocial.activerecord.backend.suggestion.definitions import (
    TableConstraintChangeSuggestion,
)

#: The branches whose drop Snowflake can spell by kind plus column list.
_KEY_BRANCHES = (
    TablePrimaryKeyConstraint,
    TableUniqueConstraint,
    TableForeignKeyConstraint,
)


def _freeze(value: Any) -> Any:
    """A comparable projection of a declaration value.

    Mirrors core's projection of the same name: it walks ``get_params`` so two
    separately built expressions of the same shape compare equal without
    rendering SQL or depending on an object's address.  It is local because it
    answers a backend question -- "is this the same declaration?" -- that must
    not be coupled to a private core helper.
    """
    if value is None or isinstance(value, (str, int, float, bool, bytes, tuple)):
        return value
    if isinstance(value, Enum):
        return ("enum", type(value).__name__, value.name)
    getter = getattr(value, "get_params", None)
    if callable(getter):
        try:
            return ("params", _freeze(getter()))
        except Exception:  # pragma: no cover -- a node that cannot introspect
            pass
    if isinstance(value, (list, set, frozenset)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    return ("repr", repr(value))


def _signature(declaration: TableConstraint) -> Any:
    """The identity of one declaration: name, kind-specific body and traits."""
    branch = declaration.branch
    if isinstance(branch, (TablePrimaryKeyConstraint, TableUniqueConstraint)):
        body: Any = (type(branch).__name__, tuple(branch.columns or ()))
    elif isinstance(branch, TableForeignKeyConstraint):
        body = (
            type(branch).__name__,
            tuple(branch.columns or ()),
            _freeze(branch.references),
            _freeze(branch.on_delete),
            _freeze(branch.on_update),
            _freeze(branch.match_type),
        )
    elif isinstance(branch, TableCheckConstraint):
        body = (type(branch).__name__, _freeze(branch.condition))
    else:
        body = (type(branch).__name__, _freeze(branch))
    return (
        declaration.name,
        declaration.deferrable,
        declaration.not_deferrable,
        declaration.initially_deferred,
        declaration.initially_immediate,
        _freeze(declaration.validation),
        declaration.enforced,
        declaration.not_enforced,
        body,
    )


def _by_kind_addressable(declaration: TableConstraint) -> bool:
    """Whether this key declaration has the columns the by-kind form needs."""
    branch = declaration.branch
    if isinstance(branch, TablePrimaryKeyConstraint):
        # ``DROP PRIMARY KEY`` names the kind alone -- one primary key exists.
        return True
    return bool(branch.columns)


class SnowflakeTableConstraintChangeSuggestionMixin:
    """Answer the table-constraint-change decision point with a real chain."""

    def suggest_table_constraint_change(
        self, point: TableConstraintChangeSuggestion
    ) -> TableConstraintChangeSuggestion:
        """Return ``point`` with the ADD / DROP chain, or explicit ``False``.

        The chain is built only from the live declarations the point carries.
        Drops precede adds; a same-name redefinition is both.  A transition
        whose every step is not expressible is answered ``False`` as a whole,
        never as a partial chain.
        """
        old = tuple(point.old_constraint_declarations)
        new = tuple(point.new_constraint_declarations)

        if any(not isinstance(declaration, TableConstraint) for declaration in old + new):
            return replace(point, operations=False)

        if not old and not new:
            # No declarations means there is nothing to rebuild.  When the
            # frozen projections claim a change anyway, the point is missing
            # the context this answer needs, which is unaddressable rather than
            # "nothing to do".
            no_action = not (point.old_constraints or point.new_constraints)
            return replace(point, operations=None if no_action else False)

        kept: set = set()
        drops = []
        for old_declaration in old:
            match = next(
                (
                    index
                    for index, new_declaration in enumerate(new)
                    if _signature(old_declaration) == _signature(new_declaration)
                ),
                None,
            )
            if match is not None:
                kept.add(match)
                continue
            if not self._can_drop_constraint(old_declaration):
                return replace(point, operations=False)
            drops.append(
                AlterTableStatement(
                    self,
                    Table(self, point.table_name),
                    [self._drop_constraint_action(old_declaration)],
                )
            )

        adds = []
        for index, new_declaration in enumerate(new):
            if index in kept:
                continue
            if not self._can_add_constraint(new_declaration):
                return replace(point, operations=False)
            adds.append(
                AlterTableStatement(
                    self,
                    Table(self, point.table_name),
                    [AddTableConstraintAction(self, new_declaration)],
                )
            )

        chain = tuple(drops + adds)
        if not chain:
            return replace(point, operations=None)
        return replace(point, operations=chain)

    def _can_drop_constraint(self, declaration: TableConstraint) -> bool:
        """Whether this old declaration has an address Snowflake can spell."""
        if not self.supports_drop_constraint():
            return False
        branch = declaration.branch
        if isinstance(branch, _KEY_BRANCHES):
            if _by_kind_addressable(declaration):
                return self.supports_drop_constraint_by_kind()
            # A key with no column list cannot be spelled by kind; its name
            # still can.
            return bool(declaration.name)
        # CHECK and every non-kind branch: by name or not at all.
        return bool(declaration.name)

    def _drop_constraint_action(
        self, declaration: TableConstraint
    ) -> DropTableConstraintAction:
        """The action for one old declaration.

        Key kinds use the by-kind form, which does not depend on a possibly
        generated name.  Everything else -- CHECK in practice -- uses the name.
        """
        if isinstance(declaration.branch, _KEY_BRANCHES) and _by_kind_addressable(
            declaration
        ):
            return DropTableConstraintAction(self, constraint=declaration)
        return DropTableConstraintAction(self, declaration.name)

    def _can_add_constraint(self, declaration: TableConstraint) -> bool:
        """Whether this new declaration is renderable as an ``ADD``."""
        branch = declaration.branch
        if isinstance(branch, TableCheckConstraint):
            # ALTER TABLE ADD CHECK needs ENABLE NOVALIDATE, which the node
            # does not carry; a hybrid table forbids the ADD entirely.
            return False
        if not isinstance(branch, _KEY_BRANCHES):
            return False
        if not self.supports_add_constraint():
            return False
        if declaration.name and not self.supports_constraint_naming():
            return False
        if declaration.enforced or declaration.not_enforced:
            return False
        if (
            declaration.deferrable
            or declaration.not_deferrable
            or declaration.initially_deferred
            or declaration.initially_immediate
        ):
            return False
        if (
            declaration.validation is not None
            and declaration.validation is not ConstraintValidation.VALIDATE
        ):
            return False
        if not branch.columns:
            return False
        if isinstance(branch, TableForeignKeyConstraint):
            referenced_table, referenced_columns = branch.references
            if referenced_table is None or not referenced_columns:
                return False
        return True


__all__ = ["SnowflakeTableConstraintChangeSuggestionMixin"]
