# src/rhosocial/activerecord/backend/impl/snowflake/mixins/sequence.py
"""Snowflake's own ``CREATE`` / ``ALTER`` / ``DROP SEQUENCE`` formatters.

Snowflake has real sequence objects, but its sequence grammar is not the
SQL-standard shape core's
:class:`~rhosocial.activerecord.backend.dialect.mixins.SequenceMixin` renders.
Three differences force this dialect to state its own formatters:

* Snowflake accepts ``START``, ``INCREMENT``, ``ORDER`` / ``NOORDER``,
  ``IF NOT EXISTS``, ``OR REPLACE`` and ``COMMENT`` on ``CREATE SEQUENCE``,
  and nothing else. It rejects ``MINVALUE``, ``MAXVALUE``, ``CYCLE``,
  ``CACHE`` and ``OWNED BY`` outright -- its own ``SEQUENCES`` metadata view
  reports ``MINIMUM_VALUE``, ``MAXIMUM_VALUE`` and ``CYCLE_OPTION`` as "Not
  applicable for Snowflake". Core's mixin emits all five of those shapes, so
  inheriting it would hand Snowflake SQL the server refuses to parse.
* ``ALTER SEQUENCE`` cannot change the initial value. The reference's usage
  notes say the first value cannot be changed after the sequence is created,
  and the command has neither a ``START`` nor a ``RESTART`` clause. An
  ``AlterSequenceExpression`` asking for either is refused rather than
  rendered.
* The order spelling is ``NOORDER``, one word, where core's shared renderer
  writes ``NO ORDER``.

``COMMENT`` is a Snowflake-only option that core's ``CreateSequenceExpression``
has no field for. It is recorded here rather than carried: adding a field to a
core expression is core's decision, not this backend's. When core grows one,
the clause belongs after ``ORDER`` / ``NOORDER``, as the reference grammar
shows.

Retrieving a value is ``seq.nextval`` -- a property on the sequence, not the
``nextval('seq')`` function form -- and is not a DDL concern; this mixin carries
only the three statements.

The capability probes live in
:class:`~rhosocial.activerecord.backend.impl.snowflake.mixins.capabilities.SnowflakeCapabilityMixin`,
which precedes the core ``SequenceMixin`` in the dialect's base list; the
formatters here are placed immediately before ``SequenceMixin`` so they win the
same way.
"""
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements import (
        AlterSequenceExpression,
        CreateSequenceExpression,
        DropSequenceExpression,
    )


class SnowflakeSequenceMixin:
    """Snowflake's own ``CREATE`` / ``ALTER`` / ``DROP SEQUENCE`` renderers."""

    def format_create_sequence_statement(
        self, expr: "CreateSequenceExpression"
    ) -> Tuple[str, tuple]:
        """Render ``CREATE SEQUENCE`` in Snowflake's grammar.

        Syntax (Snowflake SQL reference)::

            CREATE [ OR REPLACE ] SEQUENCE [ IF NOT EXISTS ] <name>
              [ WITH ]
              [ START [ WITH ] [ = ] <initial_value> ]
              [ INCREMENT [ BY ] [ = ] <sequence_interval> ]
              [ { ORDER | NOORDER } ]
              [ COMMENT = '<string_literal>' ]

        ``OR REPLACE`` and ``COMMENT`` have no field on core's
        ``CreateSequenceExpression`` and so are never emitted here; the class
        docstring above says where ``COMMENT`` belongs when core grows one.

        Raises:
            TypeError: ``expr.sequence`` is not a
                :class:`~rhosocial.activerecord.backend.expression.objects.Sequence`.
                A table would render its own name, producing a well-formed
                ``CREATE SEQUENCE`` over that table's name.
            UnsupportedFeatureError: an option Snowflake has no clause for was
                requested -- ``minvalue``, ``maxvalue``, ``cycle``, ``cache`` or
                ``owned_by``. The clause is refused rather than dropped, because
                dropping it would change the statement's meaning.
        """
        from rhosocial.activerecord.backend.expression.objects import Sequence

        if not isinstance(expr.sequence, Sequence):
            raise TypeError(
                f"{type(expr).__name__}.sequence must be a Sequence, "
                f"got {type(expr.sequence).__name__}"
            )

        parts = ["CREATE SEQUENCE"]
        if expr.if_not_exists:
            parts.append("IF NOT EXISTS")
        parts.append(expr.sequence.to_sql()[0])

        if expr.start is not None:
            parts.append(f"START WITH {expr.start}")
        if expr.increment is not None:
            parts.append(f"INCREMENT BY {expr.increment}")
        if expr.minvalue is not None:
            raise UnsupportedFeatureError(
                self.name,
                "SEQUENCE MINVALUE",
                suggestion=(
                    "Snowflake has no MINVALUE clause; its SEQUENCES view "
                    "reports MINIMUM_VALUE as not applicable."
                ),
            )
        if expr.maxvalue is not None:
            raise UnsupportedFeatureError(
                self.name,
                "SEQUENCE MAXVALUE",
                suggestion=(
                    "Snowflake has no MAXVALUE clause; its SEQUENCES view "
                    "reports MAXIMUM_VALUE as not applicable."
                ),
            )
        if expr.cycle:
            raise UnsupportedFeatureError(
                self.name,
                "SEQUENCE CYCLE",
                suggestion=(
                    "Snowflake has no CYCLE clause; its SEQUENCES view reports "
                    "CYCLE_OPTION as not applicable."
                ),
            )
        if expr.cache is not None:
            raise UnsupportedFeatureError(
                self.name,
                "SEQUENCE CACHE",
                suggestion="Snowflake has no CACHE clause on sequences.",
            )
        if expr.order:
            parts.append("ORDER")
        if expr.owned_by is not None:
            raise UnsupportedFeatureError(
                self.name,
                "SEQUENCE OWNED BY",
                suggestion="Snowflake sequences are not owned by a table column.",
            )

        return " ".join(parts), ()

    def format_drop_sequence_statement(
        self, expr: "DropSequenceExpression"
    ) -> Tuple[str, tuple]:
        """Render ``DROP SEQUENCE`` in Snowflake's grammar.

        Syntax (Snowflake SQL reference)::

            DROP SEQUENCE [ IF EXISTS ] <name> [ CASCADE | RESTRICT ]

        ``CASCADE`` / ``RESTRICT`` have no field on core's
        ``DropSequenceExpression`` and are not emitted; Snowflake accepts the
        words but does not act on them, so omitting them changes nothing.

        Raises:
            TypeError: ``expr.sequence`` is not a
                :class:`~rhosocial.activerecord.backend.expression.objects.Sequence`.
                A table would render its own name, producing a well-formed
                ``DROP SEQUENCE`` over that table's name.
        """
        from rhosocial.activerecord.backend.expression.objects import Sequence

        if not isinstance(expr.sequence, Sequence):
            raise TypeError(
                f"{type(expr).__name__}.sequence must be a Sequence, "
                f"got {type(expr.sequence).__name__}"
            )

        parts = ["DROP SEQUENCE"]
        if expr.if_exists:
            parts.append("IF EXISTS")
        parts.append(expr.sequence.to_sql()[0])
        return " ".join(parts), ()

    def format_alter_sequence_statement(
        self, expr: "AlterSequenceExpression"
    ) -> Tuple[str, tuple]:
        """Render ``ALTER SEQUENCE`` in Snowflake's grammar.

        Syntax (Snowflake SQL reference)::

            ALTER SEQUENCE [ IF EXISTS ] <name> RENAME TO <new_name>

            ALTER SEQUENCE [ IF EXISTS ] <name> [ SET ]
              [ INCREMENT [ BY ] [ = ] <sequence_interval> ]

            ALTER SEQUENCE [ IF EXISTS ] <name> SET
              [ { ORDER | NOORDER } ]
              [ COMMENT = '<string_literal>' ]

            ALTER SEQUENCE [ IF EXISTS ] <name> UNSET COMMENT

        ``RENAME TO`` and ``UNSET COMMENT`` have no field on core's
        ``AlterSequenceExpression``; ``IF EXISTS`` has none either, so it is
        never emitted.

        ``ALTER SEQUENCE`` cannot change the initial value: the reference's
        usage notes say the first value cannot be changed after creation, and
        the command has no ``START`` or ``RESTART`` clause. An expression asking
        for either is refused rather than rendered. The ``start`` refusal is
        answered by :meth:`supports_alter_sequence_start` -- the ALTER-side
        question, kept apart from the CREATE-side
        :meth:`supports_sequence_start` -- so the decision lives with the
        capability declaration rather than being hard-coded here. ``restart`` has
        no such probe and is refused directly, because no dialect in the tree
        varies it.

        ``cycle=False`` asks for the SQL default, and ``NO CYCLE`` is the words
        Snowflake rejects, so neither ``CYCLE`` nor ``NO CYCLE`` is emitted for
        it; only an explicit ``cycle=True`` is refused.

        Raises:
            TypeError: ``expr.sequence`` is not a
                :class:`~rhosocial.activerecord.backend.expression.objects.Sequence`.
                A table would render its own name, producing a well-formed
                ``ALTER SEQUENCE`` over that table's name.
            UnsupportedFeatureError: ``restart`` or ``start`` was requested --
                Snowflake cannot change the initial value -- or an option
                Snowflake has no clause for (``minvalue``, ``maxvalue``,
                ``cycle``, ``cache``, ``owned_by``) was requested.
        """
        from rhosocial.activerecord.backend.expression.objects import Sequence

        if not isinstance(expr.sequence, Sequence):
            raise TypeError(
                f"{type(expr).__name__}.sequence must be a Sequence, "
                f"got {type(expr.sequence).__name__}"
            )

        parts = [f"ALTER SEQUENCE {expr.sequence.to_sql()[0]}"]

        if expr.restart is not None:
            raise UnsupportedFeatureError(
                self.name,
                "ALTER SEQUENCE RESTART",
                suggestion=(
                    "Snowflake cannot change a sequence's initial value after "
                    "creation; there is no RESTART clause. Drop and recreate "
                    "the sequence instead."
                ),
            )
        if expr.start is not None:
            if not self.supports_alter_sequence_start():
                raise UnsupportedFeatureError(
                    self.name,
                    "ALTER SEQUENCE START",
                    suggestion=(
                        "Snowflake cannot change a sequence's initial value after "
                        "creation; there is no START clause on ALTER SEQUENCE."
                    ),
                )
            parts.append(f"START WITH {expr.start}")
        if expr.minvalue is not None:
            raise UnsupportedFeatureError(
                self.name,
                "ALTER SEQUENCE MINVALUE",
                suggestion=(
                    "Snowflake has no MINVALUE clause; its SEQUENCES view "
                    "reports MINIMUM_VALUE as not applicable."
                ),
            )
        if expr.maxvalue is not None:
            raise UnsupportedFeatureError(
                self.name,
                "ALTER SEQUENCE MAXVALUE",
                suggestion=(
                    "Snowflake has no MAXVALUE clause; its SEQUENCES view "
                    "reports MAXIMUM_VALUE as not applicable."
                ),
            )
        if expr.cycle:
            raise UnsupportedFeatureError(
                self.name,
                "ALTER SEQUENCE CYCLE",
                suggestion=(
                    "Snowflake has no CYCLE clause; its SEQUENCES view reports "
                    "CYCLE_OPTION as not applicable."
                ),
            )
        if expr.cache is not None:
            raise UnsupportedFeatureError(
                self.name,
                "ALTER SEQUENCE CACHE",
                suggestion="Snowflake has no CACHE clause on sequences.",
            )
        if expr.owned_by is not None:
            raise UnsupportedFeatureError(
                self.name,
                "ALTER SEQUENCE OWNED BY",
                suggestion="Snowflake sequences are not owned by a table column.",
            )

        if expr.increment is not None:
            parts.append(f"INCREMENT BY {expr.increment}")
        if expr.order is not None:
            parts.append("ORDER" if expr.order else "NOORDER")
        return " ".join(parts), ()


__all__ = ["SnowflakeSequenceMixin"]
