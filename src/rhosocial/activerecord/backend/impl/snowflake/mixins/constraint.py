# src/rhosocial/activerecord/backend/impl/snowflake/mixins/constraint.py
"""Snowflake constraint capability declarations, read off the official grammar.

Every switch here is declared **in this package**, even where core's
``ConstraintMixin`` / ``DDLColumnMixin`` already defaults it to the same value.
That is deliberate: those two mixins are shared with the dummy dialect and are
exactly the kind of default that can move, and a silent move of a core default
would move Snowflake's contract with it.  A declaration here is the pin.  Before
this module the backend declared **three** constraint switches in total
(:meth:`supports_constraints`, :meth:`supports_drop_constraint_if_exists` and
:meth:`supports_column_comment`), so every other answer below was whatever core
happened to say -- and for three of them (the two enforcement probes and the
deferral probe) core's default licensed a render this backend never measured.
Every such answer is now a local declaration, stated here rather than inherited.

Evidence level: not server-verified (文档（待云验）)
--------------------------------------------------
**Every value below is official-grammar-only.  Nothing here was measured.**
There is no Snowflake instance reachable from this repository's test environment
-- no account credentials exist, and the repository has no Snowflake emulator --
so none of this could be checked against a server even in principle.  The two
reference pages were transcribed on 2026-10-12 and are named at
:data:`OFFICIAL_GRAMMAR_URL` and :data:`ALTER_TABLE_GRAMMAR_URL`; a ``待云验``
marker means "a real Snowflake run must confirm this before a caller relies on
it".  The contract tests assert the *declaration*, never the server's agreement
with it, and every test for this file is render-only -- a rendering assertion
here is **not** a measurement and must never be read as one.

Modifier policy: the grammar has the tokens; this dialect does not render them
---------------------------------------------------------------------------
``supports_constraint_enforced``, ``supports_alter_constraint_enforced`` and
``supports_deferrable_constraint`` are declared **explicitly ``False``** even
though the grammar productions transcribed below contain ``[ [ NOT ] ENFORCED ]``
and ``[ [ NOT ] DEFERRABLE ]``.  Three reasons, in order of weight:

* **Not verified.**  No Snowflake instance is reachable, so a ``True`` here would
  license SQL nobody has seen the server accept.  The project's rule for the
  clauses it cannot measure is to fail closed, and the two probes core's
  renderers consult are exactly where a guess would turn into emitted SQL.
* **``ENFORCED`` is worse than a syntax error on this server.**  The reference
  states that for a standard table a PRIMARY KEY, UNIQUE or FOREIGN KEY is not
  enforced *regardless of the property*, and that specifying the non-default
  ``ENABLE`` / ``VALIDATE`` when creating one means *"the constraint isn't
  created"* -- silently, with no error.  Rendering the marker would therefore
  hand a caller a success that enforces nothing.
* **Precedent in this repository.**  ``supports_alter_constraint_enforced`` was
  already declared ``False`` before this file existed, and the clause-pair guard
  asserts the two spellings are refused by name.  Flipping it without a server
  would be a regression in the honest direction.

The per-level and per-kind grammar probes (``supports_{column,table}_*``,
``supports_*_enforced_*_constraint``, ``supports_*_deferrable_*_constraint``)
stay as the record of *what the grammar contains*: they are backend-only, no core
formatter consults them, and they are what an eventual live measurement would be
checked against.  The two families are kept apart deliberately and each
docstring says which one it is.

Two corrections to the inherited answers are unusually load-bearing, because they
turn a refusal of real grammar into a render:

* :meth:`supports_fk_match` moves **``False`` -> ``True``**.  Core reaches
  ``False`` by accident of MRO -- ``DDLColumnMixin`` declares the probe with a
  ``False`` default and is composed *ahead* of ``ConstraintMixin``, which
  declares the same probe with a ``True`` default.  Snowflake is one of the few
  backends in this group that genuinely has ``MATCH``, so the inherited answer
  was refusing SQL Snowflake's own grammar contains.
* :meth:`supports_alter_constraint_enforced` stays **``False``**, but is now a
  *declaration* rather than an inherited default (core's P1 flipped the shared
  default to ``False`` as well, so the value is unchanged and the ownership is
  what moved).  Snowflake's ``constraintAction`` lists
  ``[ [ NOT ] ENFORCED ]`` as one of only three properties the ALTER branch can
  set.
* :meth:`supports_constraint_enforced` and
  :meth:`supports_deferrable_constraint` likewise stay **``False``** as explicit
  declarations where the core default used to license a render: before P1,
  ``ConstraintMixin`` answered ``True`` for both, so Snowflake emitted
  ``ENFORCED`` / ``DEFERRABLE`` it had never measured.  See the modifier-policy
  section above for why the declaration outweighs the grammar reading.

Source, transcribed 2026-10-12 from the two pages every production below is on

Inline and out-of-line constraint definitions --
https://docs.snowflake.com/en/sql-reference/sql/create-table-constraint
ALTER TABLE's ``constraintAction`` --
https://docs.snowflake.com/en/sql-reference/sql/alter-table

Column level, verbatim (``CREATE | ALTER TABLE ... CONSTRAINT``)::

    inlineUniquePK ::=
      [ CONSTRAINT <constraint_name> ]
      { UNIQUE | PRIMARY KEY }
      [ [ NOT ] ENFORCED ]
      [ [ NOT ] DEFERRABLE ]
      [ INITIALLY { DEFERRED | IMMEDIATE } ]
      [ { ENABLE | DISABLE } ]
      [ { VALIDATE | NOVALIDATE } ]
      [ { RELY | NORELY } ]

    inlineFK ::=
      [ CONSTRAINT <constraint_name> ]
      [ FOREIGN KEY ]
      REFERENCES <ref_table_name> [ ( <ref_col_name> ) ]
      [ MATCH { FULL | SIMPLE | PARTIAL } ]
      [ ON [ UPDATE { CASCADE | SET NULL | SET DEFAULT | RESTRICT | NO ACTION } ]
           [ DELETE { CASCADE | SET NULL | SET DEFAULT | RESTRICT | NO ACTION } ] ]
      [ [ NOT ] ENFORCED ]
      [ [ NOT ] DEFERRABLE ]
      [ INITIALLY { DEFERRED | IMMEDIATE } ]
      [ { ENABLE | DISABLE } ]
      [ { VALIDATE | NOVALIDATE } ]
      [ { RELY | NORELY } ]

    inlineCH ::=
      [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
      [ ENABLE { VALIDATE | NOVALIDATE } ]

``inlineCH`` carries **one** property.  That single line is the reason half of
this module exists: within one backend, three constraint kinds, three different
capability sets.

Table level, verbatim (same page)::

    outoflineUniquePK ::=
      [ CONSTRAINT <constraint_name> ]
      { UNIQUE | PRIMARY KEY } ( <col_name> [ , <col_name> , ... ] )
      [ [ NOT ] ENFORCED ] [ [ NOT ] DEFERRABLE ] [ INITIALLY { DEFERRED | IMMEDIATE } ]
      [ { ENABLE | DISABLE } ] [ { VALIDATE | NOVALIDATE } ] [ { RELY | NORELY } ]
      [ COMMENT '<string_literal>' ]

    outoflineFK ::=
      [ CONSTRAINT <constraint_name> ]
      FOREIGN KEY ( <col_name> [ , <col_name> , ... ] )
      REFERENCES <ref_table_name> [ ( <ref_col_name> [ , <ref_col_name> , ... ] ) ]
      [ MATCH { FULL | SIMPLE | PARTIAL } ]
      [ ON [ UPDATE { ... } ] [ DELETE { ... } ] ]
      [ [ NOT ] ENFORCED ] [ [ NOT ] DEFERRABLE ] [ INITIALLY { DEFERRED | IMMEDIATE } ]
      [ { ENABLE | DISABLE } ] [ { VALIDATE | NOVALIDATE } ] [ { RELY | NORELY } ]
      [ COMMENT '<string_literal>' ]

    outoflineCH ::=
      [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
      [ ENABLE { VALIDATE | NOVALIDATE } ]

Note the tail: the table-level ``COMMENT`` exists on ``outoflineUniquePK`` and
``outoflineFK`` and is **absent from ``outoflineCH``**.  See
:meth:`supports_table_constraint_comment`.

ALTER TABLE level, verbatim (``ALTER TABLE``)::

    constraintAction ::=
      {
         ADD outoflineConstraint
       | RENAME CONSTRAINT <constraint_name> TO <new_constraint_name>
       | { ALTER | MODIFY } {   CONSTRAINT <constraint_name>
                              | PRIMARY KEY
                              | UNIQUE
                              | FOREIGN KEY } ( <col_name> [ , ... ] )
                            }
            [ [ NOT ] ENFORCED ] [ VALIDATE | NOVALIDATE ] [ RELY | NORELY ]
       | DROP {   CONSTRAINT <constraint_name>
                | PRIMARY KEY
                | UNIQUE | FOREIGN KEY } ( <col_name> [ , ... ] )
            [ CASCADE | RESTRICT ]
      }

Five properties that invert the SQL standard
--------------------------------------------

The reference states each default in its own right.  Four of them are the
**opposite** of what every other backend in this group does, and the renderer
must never supply one implicitly:

======================  =========================  =================
Property                Snowflake's default        SQL standard
======================  =========================  =================
``{ ENFORCED |          ``NOT ENFORCED``           ``ENFORCED``
NOT ENFORCED }``
``INITIALLY { DEFERRED  ``INITIALLY DEFERRED``      ``IMMEDIATE``
| IMMEDIATE }``
``MATCH { FULL |         ``MATCH FULL``             ``SIMPLE``
SIMPLE | PARTIAL }``
``{ ENABLE | DISABLE }`` ``DISABLE``                --
======================  =========================  =================

Plus two that are kind-dependent rather than global:

* ``{ VALIDATE | NOVALIDATE }`` -- "Default for PRIMARY KEY and FOREIGN KEY
  constraints: NOVALIDATE" / "Default for CHECK constraints: VALIDATE".
* ``{ RELY | NORELY }`` -- ``NORELY``.

**Practical consequence, stated as a hard constraint on this module: core must
not render ``ENFORCED``, ``INITIALLY``, ``MATCH`` or ``ENABLE`` for Snowflake
unless a caller asked for it explicitly.**  Writing any of them changes the
backend's meaning, not merely its spelling.  The four switches below that answer
"may this dialect spell it?" are all ``True``; that says the *clause* is
available, never that it should be emitted by default.

And the fact that governs all of the above, verbatim from the reference::

    For standard tables, NOT NULL and CHECK are the only types of constraints
    that are enforced by Snowflake, regardless of this property.

So on a **standard** table a Snowflake ``PRIMARY KEY``, ``FOREIGN KEY`` or
``UNIQUE`` is declarative metadata: it records the intent and it is not
maintained.  A caller that relies on a Snowflake primary key to reject duplicate
rows is relying on something the grammar does not promise.

Four shapes no other backend in this group has
-----------------------------------------------

1. **{ ``ALTER | MODIFY``} are two spellings of ONE operation.**  They are
   synonyms, not alternatives, so they collapse to a single semantic state with
   the spelling chosen by a formatter.  They are deliberately **not** two
   switches here: two booleans both defaulting to ``True`` would encode nothing
   and invite an ``alter=``/``modify=`` pair that the grammar cannot
   distinguish.  (The same reasoning was applied to SQLite's
   ``TEMP``/``TEMPORARY`` earlier this session.)
2. **A constraint can be addressed by name *or* by kind + column list** on both
   the ALTER and the DROP branch -- ``ALTER CONSTRAINT <name> (cols)`` and
   ``ALTER PRIMARY KEY (cols)`` are both in the production.  **CHECK is the
   exception and must be addressed by name**, twice in the page's own prose:
   *"For CHECK constraints, the ``constraint_name`` is required."* -- under both
   ``{ ALTER | MODIFY } CONSTRAINT ...`` and under ``DROP``.
3. **``DROP`` can address by kind.**  ``DROP PRIMARY KEY (cols)`` /
   ``DROP UNIQUE (cols)`` / ``DROP FOREIGN KEY (cols)`` are the only backend of
   the ten compared this session that can remove a constraint without naming it.
   See :meth:`supports_drop_constraint_by_kind`.
4. **The ALTER surface is strictly smaller than the ADD surface.**
   ``ADD outoflineConstraint`` can set the full property set -- including
   ``[ [ NOT ] DEFERRABLE ]`` and ``INITIALLY { DEFERRED | IMMEDIATE }`` -- while
   ``{ ALTER | MODIFY }`` offers only three: ``[ [ NOT ] ENFORCED ]``,
   ``VALIDATE | NOVALIDATE`` and ``RELY | NORELY``.  **Deferral is ADD-only.**
   An ALTER path that could set ``DEFERRABLE`` would be writing a clause
   Snowflake's parser does not accept in that position.  The asymmetry is
   restated as a comment on the constraint render path in
   :mod:`rhosocial.activerecord.backend.impl.snowflake.mixins.ddl`, which is
   where someone reaching for it will be.

Documented restriction on hybrid tables, verbatim::

    For hybrid tables, you can specify a CHECK constraint only in a
    CREATE HYBRID TABLE statement, not in an ALTER TABLE ... ADD CONSTRAINT
    statement.

That is a property of the *table kind*, not of the dialect, so it is recorded
here rather than encoded in a switch: a boolean cannot say "CHECK is addable
except on hybrid tables", and the render path has no way to know the table kind
today.

Two places the two official pages disagree with each other
---------------------------------------------------------
Recorded rather than resolved, because both pages are official and this module
must not pick a winner and call it a measurement.

* **Is the out-of-line column list required?**  The constraint page's
  ``outoflineUniquePK`` / ``outoflineFK`` productions make it mandatory --
  ``{ UNIQUE | PRIMARY KEY } ( <col_name> [ , <col_name> , ... ] )`` -- while
  the ALTER TABLE page's ``outoflineConstraint`` brackets it:
  ``UNIQUE [ ( <col_name> [ , <col_name> , ... ] ) ]``.  Core always renders
  the list, so it happens to satisfy the stricter reading; noted so no one
  "simplifies" it away.  (This corrects
  ``.claude/plan/2026-10-11/snowflake-constraint-coverage.md`` item 4, which
  transcribes all four ADD branches as having *optional* column lists.  The
  stricter page is the one the plan's own switch table was derived from.)
* **Does ``ALTER CONSTRAINT`` take a column list?**  The ALTER TABLE page's
  grammar puts ``( <col_name> [ , ... ] )`` after the name-or-kind head, but the
  constraint page's own ``RELY`` example is
  ``ALTER TABLE table_with_primary_key ALTER CONSTRAINT a_primary_key_constraint RELY;``
  -- a name and a property, no list.  No switch depends on the answer.

Known gaps a switch cannot close (recorded, not worked around)
--------------------------------------------------------------
These are **render-path** problems.  The values below are right; the generic core
formatters do not act on all of them, and teaching them to is a formatter change
that is out of this module's scope.  Each is named here so the next reader does
not mistake the pins for working behaviour:

* **The enforcement marker is unreachable on a column-level primary key.**
  ``inlineUniquePK`` has ``[ [ NOT ] ENFORCED ]``, and
  :meth:`supports_column_enforced_primary_key_constraint` is ``True`` -- but
  core's ``format_constraint_traits`` renders a trait only after the flat
  :meth:`supports_constraint_enforced` agrees, and that flat probe is ``False``
  here (see the modifier-policy section above).  So the per-kind ``True`` records
  the grammar while the render path refuses the spelling, and the refusal is a
  decision (fail closed without a server) rather than an accident of core's
  internals.  The same applies to ``UNIQUE``.
* **``NOT ENFORCED`` is not rendered at all, and that is a decision.**  This is
  the more awkward half of the same problem on Snowflake than on any other
  backend, because ``NOT ENFORCED`` **is** the Snowflake default: a caller who
  omits it already gets ``NOT ENFORCED`` semantics from the server.  Not
  emitting it is therefore *correct* here and wrong on BigQuery, where the token
  is compulsory -- do not "fix" one backend by copying the other.
* **``ENFORCED`` / ``ENABLE`` / ``VALIDATE`` are refused by the flat probes, and
  on a standard table they are worse than a syntax error.**  The reference is
  explicit: *"for PRIMARY KEY, UNIQUE, and FOREIGN KEY constraints, if you
  specify ENABLE or VALIDATE (the non-default values for these properties) when
  creating a new constraint, the constraint isn't created."*  A renderer that
  honoured a caller who asked for them would emit SQL that **silently succeeds
  while creating no constraint at all** -- which is why the flat
  ``supports_constraint_enforced`` answers ``False`` rather than leaving the
  spelling reachable.
* **``NOT VALID`` is not a Snowflake spelling; ``NOVALIDATE`` is.**
  ``_format_constraint_validation`` emits the two-word ``" NOT VALID"``, which
  Snowflake's grammar does not contain anywhere.  That is why
  :meth:`supports_constraint_novalidate` is ``False``: it gates the ``NOT VALID``
  spelling specifically, and is a different question from the backend-only
  :meth:`supports_table_constraint_novalidate`, which gates the
  ``{ VALIDATE | NOVALIDATE }`` *property*.
* **Drop-by-kind has no node to hang on.**  ``DropTableConstraint`` carries a
  ``constraint_name`` only, so ``DROP PRIMARY KEY (cols)`` -- the shape
  :meth:`supports_drop_constraint_by_kind` records -- cannot be expressed.  A
  node that carries kind-plus-columns is core S1 work.
* **``CASCADE`` sits on the by-kind ``DROP`` branch.**  Core appends ``CASCADE``
  to ``DROP CONSTRAINT <name>``, which is grammatically fine; what has no gate
  is ``RESTRICT``, the other value the same bracket allows.
* **``{ ALTER | MODIFY }``, by-kind addressing, and "CHECK must be by name"**
  have no node on this core either.  All three are grammar facts recorded above
  so that the S1/S3 shape work has them written down.

Name note
---------
The per-level (``supports_{column,table}_*``) and per-kind
(``supports_*_check_constraint``, ``supports_{column,table}_enforced_*``)
probes, the ``naming_*`` family, ``supports_{column,table}_constraint_rely``,
``supports_{column,table}_constraint_novalidate``,
``supports_{column,table}_constraint_enable_disable``,
``supports_{column,table}_on_update_action``, ``supports_add_constraint_if_not_exists``,
``supports_table_rename_constraint``, ``supports_table_alter_constraint``,
``supports_table_add_{primary_key,unique,check,foreign_key}_constraint``,
``supports_table_constraint_comment`` and ``supports_drop_constraint_by_kind``
are **backend-only** on this core: no ``ConstraintMixin`` or ``DDLColumnMixin``
in ``rhosocial.activerecord.backend.dialect.mixins`` declares or consults any
of them.  They are the names from
``.claude/plan/2026-10-11/snowflake-constraint-coverage.md`` and they are
declared here so the grammar answer is written down in one place next to its
evidence, **on the understanding that core S3 may rename or absorb them**.  The
flat switches are the ones core's renderers actually consult today; the two
groups are kept apart deliberately, and every docstring says which it is.
"""

#: The page the inline/out-of-line constraint productions and every property
#: default were transcribed from.  Kept as a constant so the docstrings, the
#: tests and the plan document cannot drift onto different pages.
OFFICIAL_GRAMMAR_URL = "https://docs.snowflake.com/en/sql-reference/sql/create-table-constraint"

#: The page ``constraintAction`` was transcribed from.  Separate from the above
#: because the two pages disagree in two places -- see the module docstring.
ALTER_TABLE_GRAMMAR_URL = "https://docs.snowflake.com/en/sql-reference/sql/alter-table"


class SnowflakeConstraintMixin:
    """Snowflake constraint capability declarations.

    Every value in this class comes from the official ``inlineConstraint`` /
    ``outoflineConstraint`` / ``constraintAction`` grammar productions
    transcribed at :data:`OFFICIAL_GRAMMAR_URL` and
    :data:`ALTER_TABLE_GRAMMAR_URL` on 2026-10-12.  **None of them is a live
    measurement** -- no Snowflake instance is reachable from this repository,
    and the repository has no emulator, so nothing here could have been checked
    against a server.  Read each value as "this is what the grammar says", not
    as "this is what a server was seen to do"; see the module docstring for the
    evidence level, the five inverted defaults and the known render-path gaps.
    """

    # ------------------------------------------------------------------
    # Column level -- ``inlineConstraint``
    #
    #     inlineUniquePK ::= [ CONSTRAINT <n> ] { UNIQUE | PRIMARY KEY }
    #                        [ [NOT] ENFORCED ] [ [NOT] DEFERRABLE ]
    #                        [ INITIALLY { DEFERRED | IMMEDIATE } ]
    #                        [ { ENABLE | DISABLE } ]
    #                        [ { VALIDATE | NOVALIDATE } ]
    #                        [ { RELY | NORELY } ]
    #
    #     inlineFK       ::= [ CONSTRAINT <n> ] [ FOREIGN KEY ]
    #                        REFERENCES <ref_table_name> [ ( <ref_col_name> ) ]
    #                        [ MATCH { FULL | SIMPLE | PARTIAL } ]
    #                        [ ON [ UPDATE {...} ] [ DELETE {...} ] ]
    #                        ... the same six properties ...
    #
    #     inlineCH       ::= [ CONSTRAINT <n> ] CHECK ( <expr> )
    #                        [ ENABLE { VALIDATE | NOVALIDATE } ]
    #
    # All four kinds are True here.  Snowflake is the one backend in this group
    # whose grammar has every kind at both levels; the ``False`` answers in this
    # backend are all about *properties* a kind does not have, never about kinds
    # it lacks.
    # ------------------------------------------------------------------

    def supports_column_primary_key_constraint(self) -> bool:
        """True: ``PRIMARY KEY`` is the second alternative of ``inlineUniquePK``.

        Official grammar, verbatim::

            inlineUniquePK ::=
              [ CONSTRAINT <constraint_name> ]
              { UNIQUE | PRIMARY KEY }
              [ [ NOT ] ENFORCED ]
              ...

        Declared locally even though core's ``ConstraintMixin`` already answers
        ``True``: it is the gate on the refusal in
        ``format_column_primary_key_constraint``, so the value is load-bearing
        and must not be able to move with a core default.

        Distinct from :meth:`supports_primary_key_constraint`, the flat probe
        core's formatter actually consults.  Both are ``True`` and both are
        declared, so a change to one cannot silently change the other.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_unique_constraint(self) -> bool:
        """True: ``UNIQUE`` is the first alternative of ``inlineUniquePK``.

        Official grammar: ``{ UNIQUE | PRIMARY KEY }`` inside ``inlineUniquePK``
        (quoted in full at :meth:`supports_column_primary_key_constraint`).

        Core consults :meth:`supports_unique_constraint` -- not this one -- for
        the ``UNIQUE`` branch in ``format_column_constraint``; both are declared
        and both are ``True``.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_check_constraint(self) -> bool:
        """True: ``inlineCH`` exists, and its one property is ``ENABLE``-shaped.

        Official grammar, verbatim::

            inlineCH ::=
              [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
              [ ENABLE { VALIDATE | NOVALIDATE } ]

        ``CHECK`` is present, so the kind is supported.  Note what is *not*
        present: ``[NOT] ENFORCED``, ``[NOT] DEFERRABLE``, ``INITIALLY``,
        ``{ ENABLE | DISABLE }`` as a standalone property and ``{ RELY |
        NORELY }`` -- hence the ``False`` answers at
        :meth:`supports_column_enforced_check_constraint` and
        :meth:`supports_column_deferrable_check_constraint`.

        Worth stating because ``inlineCH`` is a genuine anomaly rather than a
        transcription artefact: the reference states the same three-way split in
        prose ("Some properties apply to all keys (unique, primary, and foreign).
        Other properties apply only to foreign keys"), and the CHECK branch is
        the odd one out with a single combined ``ENABLE { VALIDATE | NOVALIDATE }``
        property instead of the six the other two branches carry separately.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_foreign_key_constraint(self) -> bool:
        """True: ``inlineFK`` is the column grammar's foreign-key branch.

        Official grammar, verbatim::

            inlineFK ::=
              [ CONSTRAINT <constraint_name> ]
              [ FOREIGN KEY ]
              REFERENCES <ref_table_name> [ ( <ref_col_name> ) ]
              [ MATCH { FULL | SIMPLE | PARTIAL } ]
              ...

        Two details in that quote.  ``FOREIGN KEY`` itself is optional -- the
        ``REFERENCES`` clause is what identifies the branch, so both
        ``c INT REFERENCES t(id)`` and ``c INT FOREIGN KEY REFERENCES t(id)``
        are in the grammar.  And the referenced column list is optional
        (a single ``<ref_col_name>``, not ``[, ...]``), because the reference
        allows it to be omitted when the referenced table's primary key signature
        matches exactly.

        Known coupling, inherited from core and worth restating:
        ``format_column_fk_constraint`` consults the **table**-level
        :meth:`supports_foreign_key_constraint` -- there is no column-level
        probe on this core.  Snowflake answers ``True`` at both levels, so the
        coupling costs nothing here.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_naming_primary_key_constraint(self) -> bool:
        """True: ``[ CONSTRAINT <constraint_name> ]`` opens ``inlineUniquePK``.

        Official grammar::

            inlineUniquePK ::=
              [ CONSTRAINT <constraint_name> ]
              { UNIQUE | PRIMARY KEY }
              ...

        The name is optional at every level and for every kind on Snowflake --
        the keyword appears in all three inline branches and in all three
        out-of-line branches.  That is what makes ``ALTER CONSTRAINT <name>``
        and ``RENAME CONSTRAINT <name> TO`` reachable for a Snowflake primary
        key; compare BigQuery, where a primary key cannot be named at all.

        Name note: no core probe is per-level or ``naming_*`` yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_naming_unique_constraint(self) -> bool:
        """True: same ``[ CONSTRAINT <constraint_name> ]`` as the primary key.

        Official grammar: the name is bracketed in front of the
        ``{ UNIQUE | PRIMARY KEY }`` pair of ``inlineUniquePK``, so it covers
        ``UNIQUE`` as well as ``PRIMARY KEY``.

        Name note: no core probe is per-level or ``naming_*`` yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_naming_check_constraint(self) -> bool:
        """True: ``inlineCH`` is nameable -- and that is what makes it droppable.

        Official grammar::

            inlineCH ::=
              [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
              [ ENABLE { VALIDATE | NOVALIDATE } ]

        Pairs with the "CHECK must be addressed by name" rule on the ALTER side
        (see the module docstring).  The two facts fit together: a CHECK is the
        one kind Snowflake will not address by kind-plus-column-list, and it is
        also one of only two kinds that is nameable at column level on every
        backend in this group.  Without this ``True`` there would be no way to
        reach a column CHECK at all.

        Name note: no core probe is per-level or ``naming_*`` yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_naming_foreign_key_constraint(self) -> bool:
        """True: ``[ CONSTRAINT <constraint_name> ] [ FOREIGN KEY ] REFERENCES``.

        Official grammar: the name is the first bracketed group of ``inlineFK``
        (quoted at :meth:`supports_column_foreign_key_constraint`), ahead of the
        optional ``FOREIGN KEY`` keyword.

        Name note: no core probe is per-level or ``naming_*`` yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    # ------------------------------------------------------------------
    # Table level -- ``outoflineConstraint``
    #
    # Same four kinds, but composite, and the ``COMMENT`` tail exists on two of
    # the three branches only.  The plan's name for the ADD-side switch is
    # ``supports_table_add_constraint``; the name core's
    # ``format_add_table_constraint_action`` actually consults is the flat
    # :meth:`supports_add_constraint`, and that is the one declared -- see its
    # docstring for the mapping.
    # ------------------------------------------------------------------

    def supports_table_primary_key_constraint(self) -> bool:
        """True: ``outoflineUniquePK`` is a table element.

        Official grammar, verbatim::

            outoflineUniquePK ::=
              [ CONSTRAINT <constraint_name> ]
              { UNIQUE | PRIMARY KEY } ( <col_name> [ , <col_name> , ... ] )
              [ [ NOT ] ENFORCED ] ...

        The comma in ``[ , <col_name> , ... ]`` is what makes this composite
        primary key the only way to express a multi-column one: the reference
        states *"Multi-column constraints (composite unique or primary keys) can
        only be defined out-of-line."*

        The column list is mandatory on this page's production.  The ALTER TABLE
        page brackets it instead; see the module docstring for that conflict.
        Either way core always renders it, so the stricter reading holds.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_unique_constraint(self) -> bool:
        """True: ``UNIQUE`` is the first alternative of ``outoflineUniquePK``.

        Official grammar: ``{ UNIQUE | PRIMARY KEY } ( <col_name> [ , <col_name>
        , ... ] )`` inside ``outoflineUniquePK``, quoted in full at
        :meth:`supports_table_primary_key_constraint`.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_check_constraint(self) -> bool:
        """True: ``outoflineCH`` is a table element, with the same one property.

        Official grammar, verbatim::

            outoflineCH ::=
              [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
              [ ENABLE { VALIDATE | NOVALIDATE } ]

        Identical to ``inlineCH`` including the single property, so the
        column-level and table-level ``False`` answers agree:
        :meth:`supports_table_enforced_check_constraint` and
        :meth:`supports_table_deferrable_check_constraint`.

        One behaviour the reference attaches to this branch specifically, and
        which no switch can express: on a **hybrid** table a CHECK may be
        specified only in ``CREATE HYBRID TABLE``, never in
        ``ALTER TABLE ... ADD CONSTRAINT``.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_foreign_key_constraint(self) -> bool:
        """True: ``outoflineFK`` is a table element and takes composite columns.

        Official grammar, verbatim::

            outoflineFK ::=
              [ CONSTRAINT <constraint_name> ]
              FOREIGN KEY ( <col_name> [ , <col_name> , ... ] )
              REFERENCES <ref_table_name> [ ( <ref_col_name> [ , <ref_col_name> , ... ] ) ]
              [ MATCH { FULL | SIMPLE | PARTIAL } ]
              [ ON [ UPDATE { ... } ] [ DELETE { ... } ] ]
              ...

        Unlike ``inlineFK``, both column lists are composite here.  This is also
        the flat probe ``format_column_fk_constraint`` reaches for at column
        level; Snowflake answers ``True`` at both, so the coupling is harmless.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_naming_primary_key_constraint(self) -> bool:
        """True: ``[ CONSTRAINT <constraint_name> ]`` opens ``outoflineUniquePK``.

        Official grammar: ``outoflineUniquePK ::= [ CONSTRAINT <constraint_name>
        ] { UNIQUE | PRIMARY KEY } ( ... )``.

        Name note: no core probe is per-level or ``naming_*`` yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_naming_unique_constraint(self) -> bool:
        """True: same bracketed name as the table-level primary key.

        Official grammar: ``outoflineUniquePK`` brackets the name ahead of the
        ``{ UNIQUE | PRIMARY KEY }`` pair, so it covers both.

        Name note: no core probe is per-level or ``naming_*`` yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_naming_check_constraint(self) -> bool:
        """True: ``outoflineCH`` is nameable.

        Official grammar::

            outoflineCH ::=
              [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
              [ ENABLE { VALIDATE | NOVALIDATE } ]

        This is the precondition for the "CHECK must be addressed by name" rule
        the ALTER TABLE page states twice, verbatim: *"For CHECK constraints,
        the constraint_name is required."*

        Name note: no core probe is per-level or ``naming_*`` yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_naming_foreign_key_constraint(self) -> bool:
        """True: ``[ CONSTRAINT <constraint_name> ]`` opens ``outoflineFK``.

        Official grammar: ``outoflineFK ::= [ CONSTRAINT <constraint_name> ]
        FOREIGN KEY ( ... ) REFERENCES ...``.

        Name note: no core probe is per-level or ``naming_*`` yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_constraint_comment(self) -> bool:
        """True, but only on the primary-key / unique / foreign-key branches.

        Official grammar, verbatim -- the tail of ``outoflineUniquePK`` and of
        ``outoflineFK``::

            [ { RELY | NORELY } ]
            [ COMMENT '<string_literal>' ]

        and ``outoflineCH`` in full::

            outoflineCH ::=
              [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
              [ ENABLE { VALIDATE | NOVALIDATE } ]

        **The ``COMMENT`` tail is absent from the CHECK branch.**  A switch is a
        boolean and a boolean cannot say "yes for three of the four kinds", so
        this records the branch that carries the clause and
        :meth:`supports_table_check_constraint`'s neighbourhood carries the
        exception.  Per-kind gates are core S1/S3 work.

        Table-level only, and that is a real asymmetry rather than an oversight:
        the column-level ``COMMENT`` (:meth:`supports_column_comment`, declared
        on ``SnowflakeAlterColumnModifierMixin``) comments the *column*, and the
        reference distinguishes them -- *"The DESCRIBE TABLE command shows
        comments defined on columns, but not comments defined on constraints."*

        Name note: no core probe is per-kind or ``*_constraint_comment`` yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    # ------------------------------------------------------------------
    # Per-kind property probes: enforcement and deferral.
    #
    # These are the cleanest instance in this group of why the split is by kind
    # rather than by clause.  ``ENFORCED`` and ``DEFERRABLE`` are both ``True``
    # for primary key / unique / foreign key and both ``False`` for CHECK -- on
    # the same backend, on the same page, for the same clause.  A single boolean
    # per clause cannot represent it.
    #
    # The three inverted defaults make the ``True``s subtle: the clause is
    # available, but writing it is never the right default on Snowflake.
    # ------------------------------------------------------------------

    def supports_column_enforced_primary_key_constraint(self) -> bool:
        """True: ``[ [ NOT ] ENFORCED ]`` is in ``inlineUniquePK``.

        Official grammar::

            inlineUniquePK ::=
              [ CONSTRAINT <constraint_name> ]
              { UNIQUE | PRIMARY KEY }
              [ [ NOT ] ENFORCED ]
              ...

        **The default is the opposite of the SQL standard** -- the reference
        states ``Default: NOT ENFORCED`` -- and on a standard table the property
        changes nothing anyway: *"For standard tables, NOT NULL and CHECK are the
        only types of constraints that are enforced by Snowflake, regardless of
        this property."*  So on a standard table the marker is documentation, and
        on a hybrid table it is the one that matters (the reference notes you
        cannot set ``NOT ENFORCED`` on a hybrid ``PRIMARY KEY`` at all).

        Reachability, so the ``True`` is not over-read: it records the grammar
        only.  Core's render path consults the flat
        :meth:`supports_constraint_enforced`, which is ``False`` here, so the
        marker is refused for a primary key (and for every other kind) rather
        than emitted.  See the modifier-policy section of the module docstring
        for why the grammar answer and the render answer differ.

        Name note: no core probe is per-level or per-kind for enforcement yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_enforced_unique_constraint(self) -> bool:
        """True: ``[ [ NOT ] ENFORCED ]`` is in ``inlineUniquePK``, same branch.

        Official grammar: ``{ UNIQUE | PRIMARY KEY }`` then
        ``[ [ NOT ] ENFORCED ]`` -- one production covers both kinds, so this is
        the same fact as :meth:`supports_column_enforced_primary_key_constraint`
        and inherits every caveat in its docstring, including the note that the
        flat render gate is ``False`` here (``UNIQUE`` is refused by it).

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_enforced_foreign_key_constraint(self) -> bool:
        """True: ``[ [ NOT ] ENFORCED ]`` is in ``inlineFK``.

        Official grammar::

            inlineFK ::=
              [ CONSTRAINT <constraint_name> ]
              [ FOREIGN KEY ]
              REFERENCES <ref_table_name> [ ( <ref_col_name> ) ]
              [ MATCH { FULL | SIMPLE | PARTIAL } ]
              [ ON [ UPDATE { ... } ] [ DELETE { ... } ] ]
              [ [ NOT ] ENFORCED ]
              ...

        ``Default: NOT ENFORCED``, the SQL-standard inverse.  Like every other
        kind, the flat :meth:`supports_constraint_enforced` is ``False`` here, so
        the render path refuses the spelling; this ``True`` is the grammar record
        and nothing more.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_enforced_check_constraint(self) -> bool:
        """False -- and this is the pin, because core would otherwise say ``True``.

        Official grammar, in full, with nothing elided::

            inlineCH ::=
              [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
              [ ENABLE { VALIDATE | NOVALIDATE } ]

        **Two properties and neither is an enforcement marker.**  There is no
        ``ENFORCED``, no ``NOT ENFORCED``, not even in a ``[NOT]`` optional
        bracket.  A ``NOT ENFORCED`` on a Snowflake CHECK constraint is not
        "unavailable" in the ordinary sense -- it is not in the language.

        The direction of the core default is what makes this the one to pin
        hardest.  ``ConstraintMixin.supports_constraint_enforced`` once answered
        ``True``, and core's P1 flipped that default to ``False``; this
        declaration pins Snowflake's own answer either way.  CHECK is the one
        kind Snowflake *does* enforce on a standard table, so the marker would
        be the most consequential clause available to get wrong.

        Name note: no core probe is per-level or per-kind for enforcement yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return False

    def supports_table_enforced_primary_key_constraint(self) -> bool:
        """True: ``[ [ NOT ] ENFORCED ]`` is in ``outoflineUniquePK``.

        Official grammar::

            outoflineUniquePK ::=
              [ CONSTRAINT <constraint_name> ]
              { UNIQUE | PRIMARY KEY } ( <col_name> [ , <col_name> , ... ] )
              [ [ NOT ] ENFORCED ]
              ...

        Same inverted default (``NOT ENFORCED``) and same "not enforced on a
        standard table regardless of this property" as the column level; see
        :meth:`supports_column_enforced_primary_key_constraint`.

        The reference's own worked example spells the marker out at table level,
        which is the clearest evidence that callers should::

            CONSTRAINT pkey_1 PRIMARY KEY (col1, col2) NOT ENFORCED

        Name note: no core probe is per-level or per-kind for enforcement yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_enforced_unique_constraint(self) -> bool:
        """True: same ``outoflineUniquePK`` branch as the table-level primary key.

        Official grammar: ``[ [ NOT ] ENFORCED ]`` follows
        ``{ UNIQUE | PRIMARY KEY } ( ... )`` in the single ``outoflineUniquePK``
        production, so it covers both kinds.  Same inverted default, same
        standard-table caveat.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_enforced_foreign_key_constraint(self) -> bool:
        """True: ``[ [ NOT ] ENFORCED ]`` is in ``outoflineFK``.

        Official grammar::

            outoflineFK ::=
              [ CONSTRAINT <constraint_name> ]
              FOREIGN KEY ( <col_name> [ , <col_name> , ... ] )
              REFERENCES <ref_table_name> [ ( <ref_col_name> [ , ... ] ) ]
              [ MATCH { FULL | SIMPLE | PARTIAL } ]
              [ ON [ UPDATE { ... } ] [ DELETE { ... } ] ]
              [ [ NOT ] ENFORCED ]
              ...

        The reference's second worked example writes it at table level::

            CONSTRAINT fkey_1 FOREIGN KEY (col_a, col_b) REFERENCES table2 (col1, col2) NOT ENFORCED

        ``Default: NOT ENFORCED``; and on a standard table the property does not
        change what is enforced.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_enforced_check_constraint(self) -> bool:
        """False: ``outoflineCH`` has one property and it is not an enforcement one.

        Official grammar, in full::

            outoflineCH ::=
              [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
              [ ENABLE { VALIDATE | NOVALIDATE } ]

        Same absence as :meth:`supports_column_enforced_check_constraint`, at the
        other level.  The two agreeing is the point: Snowflake's CHECK capability
        set is identical inline and out-of-line, which is what makes CHECK the
        clean case for a per-kind gate rather than a per-level one.

        文档（待云验）: grammar-only, not server-verified.
        """
        return False

    def supports_column_deferrable_primary_key_constraint(self) -> bool:
        """True: ``[ [ NOT ] DEFERRABLE ] [ INITIALLY ... ]`` is in ``inlineUniquePK``.

        Official grammar::

            inlineUniquePK ::=
              [ CONSTRAINT <constraint_name> ]
              { UNIQUE | PRIMARY KEY }
              [ [ NOT ] ENFORCED ]
              [ [ NOT ] DEFERRABLE ]
              [ INITIALLY { DEFERRED | IMMEDIATE } ]
              ...

        **``INITIALLY`` is the third inverted default**: the reference states
        ``Default: INITIALLY DEFERRED`` where the SQL standard says ``IMMEDIATE``.
        ``DEFERRABLE`` itself defaults to ``NOT DEFERRABLE``, which is the standard
        direction.

        Neither spelling may be emitted implicitly.  A caller who omits both
        already gets ``NOT DEFERRABLE``; a caller who omits ``INITIALLY`` already
        gets ``INITIALLY DEFERRED`` *as far as the default goes*, which is the
        opposite of what writing nothing would mean on any other backend in this
        group.

        Name note: no core probe is per-level or per-kind for deferral yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_deferrable_unique_constraint(self) -> bool:
        """True: same ``inlineUniquePK`` branch as the column-level primary key.

        Official grammar: ``[ [ NOT ] DEFERRABLE ]`` and
        ``[ INITIALLY { DEFERRED | IMMEDIATE } ]`` follow
        ``{ UNIQUE | PRIMARY KEY }`` in the single production, so this is the same
        fact as :meth:`supports_column_deferrable_primary_key_constraint`.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_deferrable_foreign_key_constraint(self) -> bool:
        """True: the deferral pair is in ``inlineFK`` too.

        Official grammar: ``inlineFK`` ends its property block with the same
        ``[ [ NOT ] ENFORCED ] [ [ NOT ] DEFERRABLE ] [ INITIALLY { DEFERRED |
        IMMEDIATE } ] [ { ENABLE | DISABLE } ] [ { VALIDATE | NOVALIDATE } ]
        [ { RELY | NORELY } ]`` sequence that ``inlineUniquePK`` carries.

        Of the three kinds that have deferral, the foreign key is the one where
        it could plausibly matter -- except that Snowflake does not enforce
        foreign keys on standard tables either ("NOT NULL and CHECK are the only
        types of constraints that are enforced by Snowflake"), so on a standard
        table the property is metadata there too.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_deferrable_check_constraint(self) -> bool:
        """False -- the other half of the per-kind split, pinned against core's ``True``.

        Official grammar, in full::

            inlineCH ::=
              [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
              [ ENABLE { VALIDATE | NOVALIDATE } ]

        No ``DEFERRABLE``, no ``NOT DEFERRABLE``, no ``INITIALLY``.  The
        reference says why the shape is what it is: the CHECK branch's single
        property is the *combined* ``ENABLE { VALIDATE | NOVALIDATE }``, which
        has no room for a separate deferral.

        ``ConstraintMixin.supports_deferrable_constraint`` once answered ``True``
        and core's P1 flipped it to ``False``; this declaration pins Snowflake's
        own answer.  The flat probe is the gate ``format_references_clause``
        raises on -- so it is declared ``False`` here (see the modifier-policy
        section of the module docstring) while the per-kind pair below carries
        the grammar record.  Those two are different questions, which is why
        they are kept apart.

        文档（待云验）: grammar-only, not server-verified.
        """
        return False

    def supports_table_deferrable_primary_key_constraint(self) -> bool:
        """True: ``outoflineUniquePK`` carries the deferral pair.

        Official grammar::

            outoflineUniquePK ::=
              [ CONSTRAINT <constraint_name> ]
              { UNIQUE | PRIMARY KEY } ( <col_name> [ , <col_name> , ... ] )
              [ [ NOT ] ENFORCED ]
              [ [ NOT ] DEFERRABLE ]
              [ INITIALLY { DEFERRED | IMMEDIATE } ]
              ...

        Same inverted ``INITIALLY DEFERRED`` default as the column level; see
        :meth:`supports_column_deferrable_primary_key_constraint`.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_deferrable_unique_constraint(self) -> bool:
        """True: same ``outoflineUniquePK`` branch as the table-level primary key.

        Official grammar: the deferral pair follows
        ``{ UNIQUE | PRIMARY KEY } ( ... )`` in the single production.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_deferrable_foreign_key_constraint(self) -> bool:
        """True: ``outoflineFK`` carries the deferral pair.

        Official grammar: the property block of ``outoflineFK`` is the same six
        optional groups as ``inlineFK``'s.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_deferrable_check_constraint(self) -> bool:
        """False: ``outoflineCH`` has one property and it is not a deferral one.

        Official grammar, in full::

            outoflineCH ::=
              [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
              [ ENABLE { VALIDATE | NOVALIDATE } ]

        Same absence as :meth:`supports_column_deferrable_check_constraint`, at
        the other level.

        文档（待云验）: grammar-only, not server-verified.
        """
        return False

    # ------------------------------------------------------------------
    # The four remaining property families, present on primary key / unique /
    # foreign key at both levels.  ``ENABLE | DISABLE``, ``VALIDATE |
    # NOVALIDATE`` and ``RELY | NORELY`` are named by the reference as
    # Snowflake's own extensions to the ANSI properties; ``MATCH`` and the
    # referential actions are foreign-key-only.
    # ------------------------------------------------------------------

    def supports_column_constraint_enable_disable(self) -> bool:
        """True: ``[ { ENABLE | DISABLE } ]`` is in ``inlineUniquePK``.

        Official grammar::

            inlineUniquePK ::=
              ...
              [ { ENABLE | DISABLE } ]
              [ { VALIDATE | NOVALIDATE } ]
              [ { RELY | NORELY } ]

        ``Default: DISABLE``, and the reference says why it exists at all:
        *"Specifies whether the constraint is enabled or disabled.  These
        properties are provided for compatibility with Oracle."*

        **This is a constraint *property*, not an ``ENABLE CONSTRAINT`` lifecycle
        statement.**  Snowflake has no standalone enable/disable verb; of the ten
        backends compared this session Oracle is the only one that does.  A
        switch named for the property must not be read as the capability to
        issue ``ALTER TABLE ... ENABLE CONSTRAINT``.

        The hazard worth knowing before rendering it: *"For CHECK constraints,
        ENABLE is the default and is required.  If you specify DISABLE, then the
        CHECK constraint isn't created."*

        Name note: no core probe is per-level for constraint properties yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_constraint_enable_disable(self) -> bool:
        """True: ``[ { ENABLE | DISABLE } ]`` is in ``outoflineUniquePK`` / ``outoflineFK``.

        Official grammar: the same ``[ { ENABLE | DISABLE } ]`` group, ahead of
        ``[ { VALIDATE | NOVALIDATE } ]``, in both out-of-line key productions.

        Same ``DISABLE`` default and same "compatibility with Oracle" rationale as
        :meth:`supports_column_constraint_enable_disable`, and the same warning:
        on a **standard** table, specifying ``ENABLE`` when creating a PRIMARY
        KEY / UNIQUE / FOREIGN KEY means *"the constraint isn't created"* --
        silently, with no error.

        Name note: no core probe is per-level for constraint properties yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_constraint_novalidate(self) -> bool:
        """True: ``[ { VALIDATE | NOVALIDATE } ]`` is in ``inlineUniquePK``.

        Official grammar::

            inlineUniquePK ::=
              ...
              [ { ENABLE | DISABLE } ]
              [ { VALIDATE | NOVALIDATE } ]
              [ { RELY | NORELY } ]

        ``Default for PRIMARY KEY and FOREIGN KEY constraints: NOVALIDATE`` /
        ``Default for CHECK constraints: VALIDATE`` -- so the default is
        kind-dependent and a single boolean cannot carry it; the per-kind
        ``ENABLE { VALIDATE | NOVALIDATE }`` shape of ``inlineCH`` is recorded at
        :meth:`supports_column_check_constraint`.

        Distinct from the flat :meth:`supports_constraint_novalidate`, which is
        ``False``.  **These two are not in conflict and must not be reconciled:**
        the flat switch gates the ``" NOT VALID"`` *spelling* core emits on the
        ADD path, and Snowflake has no such token; this one gates the
        ``{ VALIDATE | NOVALIDATE }`` *property*, which Snowflake does have.
        Collapsing them would either license ``NOT VALID`` or lose ``NOVALIDATE``.

        Name note: no core probe is per-level for constraint properties yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_constraint_novalidate(self) -> bool:
        """True: ``[ { VALIDATE | NOVALIDATE } ]`` is in the out-of-line key productions.

        Official grammar: the same ``[ { VALIDATE | NOVALIDATE } ]`` group in
        ``outoflineUniquePK`` and ``outoflineFK``.

        Also the property the ALTER branch can set -- the ``constraintAction``
        production carries ``[ VALIDATE | NOVALIDATE ]`` on
        ``{ ALTER | MODIFY }``.  See :meth:`supports_table_alter_constraint` and
        the flat :meth:`supports_constraint_novalidate` for why the two
        differently-spelled switches disagree on purpose.

        Name note: no core probe is per-level for constraint properties yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_constraint_rely(self) -> bool:
        """True: ``[ { RELY | NORELY } ]`` is in ``inlineUniquePK``.

        Official grammar::

            inlineUniquePK ::=
              ...
              [ { VALIDATE | NOVALIDATE } ]
              [ { RELY | NORELY } ]

        ``Default: NORELY``.  ``RELY`` is the one property the reference singles
        out as doing real work on a standard table: *"An exception is the RELY
        property.  If you have ensured that the data in your standard tables
        complies with UNIQUE, PRIMARY KEY, and FOREIGN KEY constraints, you can
        set the RELY property for those constraints"* -- it lets the optimizer
        eliminate joins.

        The same reference section is blunt about the risk: *"For standard
        tables, it is your responsibility to enforce RELY constraints; otherwise,
        you might risk unintended behavior and unexpected results"* and *"If the
        RELY property is set for a constraint and a violation of referential
        integrity occurs, DML and CTAS statements might insert incorrect data."*

        Name note: no core probe is per-level for constraint properties yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_constraint_rely(self) -> bool:
        """True: ``[ { RELY | NORELY } ]`` is in the out-of-line key productions.

        Official grammar: the same ``[ { RELY | NORELY } ]`` group in
        ``outoflineUniquePK`` and ``outoflineFK``.

        This is also one of only three properties the ALTER branch can set -- the
        reference's own example uses it::

            ALTER TABLE table_with_primary_key ALTER CONSTRAINT a_primary_key_constraint RELY;
            ALTER TABLE table_with_foreign_key ALTER CONSTRAINT a_foreign_key_constraint RELY;

        Note the reference's advice to set ``RELY`` on **both** sides of a
        primary-key / foreign-key pair.  That is a caller obligation, not a
        capability.

        Name note: no core probe is per-level for constraint properties yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_fk_match(self) -> bool:
        """True: ``[ MATCH { FULL | SIMPLE | PARTIAL } ]`` is in ``inlineFK``.

        Official grammar::

            inlineFK ::=
              [ CONSTRAINT <constraint_name> ]
              [ FOREIGN KEY ]
              REFERENCES <ref_table_name> [ ( <ref_col_name> ) ]
              [ MATCH { FULL | SIMPLE | PARTIAL } ]

        The third default that inverts the standard: the reference states
        ``Default: MATCH FULL`` where SQL says ``SIMPLE``.  So a caller who omits
        ``MATCH`` already has ``FULL`` semantics on Snowflake -- and a caller who
        omits it on any other backend in this group would have ``SIMPLE``.  That
        is a behavioural difference, not a rendering one, and it is why the
        renderer must not add ``MATCH`` on its own.

        Snowflake is one of the few backends here where ``MATCH`` is genuinely
        supported; the 2026-10-11 live measurement found PostgreSQL supports it
        and MySQL/MariaDB **silently discard** it (which is why they must refuse
        it).  Do not read this ``True`` as transferable to those backends.

        Name note: no core probe is per-level for ``fk_match`` yet; the flat
        :meth:`supports_fk_match` is the gate with teeth.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_fk_match(self) -> bool:
        """True: ``[ MATCH { FULL | SIMPLE | PARTIAL } ]`` is in ``outoflineFK`` too.

        Official grammar: the same group, positioned after the ``REFERENCES`` line
        of ``outoflineFK``, ahead of the ``ON [ UPDATE ... ] [ DELETE ... ]``
        pair.  Same ``MATCH FULL`` default as
        :meth:`supports_column_fk_match`.

        Name note: no core probe is per-level for ``fk_match`` yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_column_on_update_action(self) -> bool:
        """True: ``ON [ UPDATE { ... } ]`` is in ``inlineFK``.

        Official grammar::

            inlineFK ::=
              ...
              [ ON [ UPDATE { CASCADE | SET NULL | SET DEFAULT | RESTRICT | NO ACTION } ]
                   [ DELETE { CASCADE | SET NULL | SET DEFAULT | RESTRICT | NO ACTION } ] ]

        Five actions, all of them.  ``Default: UPDATE NO ACTION``.  Note the
        shape: **one ``ON`` governs both the ``UPDATE`` and the ``DELETE``
        keyword**, so a caller wanting only ``ON DELETE CASCADE`` writes
        ``ON DELETE CASCADE`` -- a single ``ON`` with one following keyword --
        where the SQL-standard spelling uses two ``ON`` keywords.  The render
        path's separator is load-bearing on this point.

        Worth noting alongside Oracle 21c, which the 2026-10-11 live
        measurement found has **no** ``ON UPDATE`` syntax at all.  Snowflake is at
        the other extreme, and the switch is how that is recorded.

        Name note: no core probe is per-level for referential actions yet; see
        :meth:`supports_fk_on_update`.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_on_update_action(self) -> bool:
        """True: ``ON [ UPDATE { ... } ]`` is in ``outoflineFK``.

        Official grammar: the same ``ON`` group, after ``MATCH`` and before the
        six-property block.  Same five actions, same ``UPDATE NO ACTION`` default,
        same single-``ON`` shape as :meth:`supports_column_on_update_action`.

        Name note: no core probe is per-level for referential actions yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    # ------------------------------------------------------------------
    # Flat kind switches -- the probes core's renderers actually consult
    # today.
    #
    # Read this section next to the two above.  Those describe the grammar's
    # per-level, per-kind shape; these are what a formatter asks.  Where the two
    # could be read as disagreeing, the entry that differs says so -- most
    # importantly :meth:`supports_constraint_enforced` versus
    # :meth:`supports_column_enforced_check_constraint`: the flat probe is
    # ``False`` (the render decision; see the module docstring) while the
    # per-kind grammar record is ``True`` for the key kinds and ``False`` for
    # CHECK.
    # ------------------------------------------------------------------

    def supports_constraint_naming(self) -> bool:
        """True: ``[ CONSTRAINT <constraint_name> ]`` opens every constraint production.

        Official grammar.  All three column-level branches::

            inlineUniquePK ::= [ CONSTRAINT <constraint_name> ] { UNIQUE | PRIMARY KEY } ...
            inlineFK       ::= [ CONSTRAINT <constraint_name> ] [ FOREIGN KEY ] REFERENCES ...
            inlineCH       ::= [ CONSTRAINT <constraint_name> ] CHECK ( <expr> ) ...

        and all three table-level ones, from the same page::

            outoflineUniquePK ::= [ CONSTRAINT <constraint_name> ] { UNIQUE | PRIMARY KEY } ( ... )
            outoflineFK       ::= [ CONSTRAINT <constraint_name> ] FOREIGN KEY ( ... ) REFERENCES ...
            outoflineCH       ::= [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )

        So the name is optional, universal and not kind-dependent: every kind at
        both levels carries the prefix.  That is the contract's "Snowflake 待核"
        item answered from the reference -- there is no Snowflake page that
        omits the bracket, and the ALTER TABLE page depends on the name being
        there (``ALTER CONSTRAINT <name>`` and ``RENAME CONSTRAINT <name> TO``
        are by-name verbs).

        This is the flat probe core's ``format_column_constraint`` /
        ``format_table_constraint`` consult before rendering the prefix, so the
        declaration is load-bearing.  The per-level, per-kind
        :meth:`supports_column_naming_*` / :meth:`supports_table_naming_*` probes
        below record the same fact kind by kind; both families are declared so a
        change to one cannot move the other silently.

        Declared locally even though core's default is ``True``: the value is the
        gate on a refusal, so it must be Snowflake's statement.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_primary_key_constraint(self) -> bool:
        """True: core's ``format_column_primary_key_constraint`` may emit ``PRIMARY KEY``.

        Official grammar: ``{ UNIQUE | PRIMARY KEY }`` in ``inlineUniquePK`` at
        column level and in ``outoflineUniquePK`` at table level -- the keyword is
        in both, so ``True`` at both.

        ``True`` says the keyword may be emitted.  It says nothing about what
        Snowflake then *does*: on a standard table a primary key is not enforced
        ("NOT NULL and CHECK are the only types of constraints that are enforced
        by Snowflake").  A caller must not read this as an integrity guarantee.

        Declared locally even though core already answers ``True``: this is the
        gate on the refusal, so the value is load-bearing and must not move.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_unique_constraint(self) -> bool:
        """True: core's ``format_column_constraint`` may emit ``UNIQUE``.

        Official grammar: the same ``{ UNIQUE | PRIMARY KEY }`` pair in
        ``inlineUniquePK`` and ``outoflineUniquePK``.

        Load-bearing detail: ``format_column_unique_constraint`` pairs the
        ``UNIQUE`` branch with **this** probe and raises
        ``UnsupportedFeatureError(self.name, "UNIQUE column constraint")`` when it
        declines, so the ``True`` is the gate on that refusal.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_not_null_constraint(self) -> bool:
        """True: ``[ NOT NULL ]`` is in the column definition.

        Official grammar: ``NOT NULL`` sits between the column type and the
        inline constraint on both pages::

            CREATE TABLE <name> (
              <col1_name> <col1_type>  [ NOT NULL ] { inlineUniquePK | inlineFK | inlineCH }
              [ , <col2_name> <col2_type> [ NOT NULL ] { inlineUniquePK | inlineFK | inlineCH } ]
              [ , ... ]
            )

            ADD [ COLUMN ] [ IF NOT EXISTS ] <col_name> <col_type> [ ... ] [ NOT NULL ]
              { inlineUniquePK | inlineFK | inlineCH }

        Two facts beyond the ``True``:

        * it is **inline only** -- the reference says it "can be specified only as
          an inline constraint within the column definition", and there is no
          ``NOT NULL`` branch in ``outoflineConstraint``;
        * ``NOT NULL`` is one of the **two** constraint kinds Snowflake enforces
          on a standard table, so this is the most load-bearing ``True`` on the
          backend and the one most worth getting right.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_check_constraint(self) -> bool:
        """True: core's ``format_column_check_constraint`` may emit ``CHECK``.

        Official grammar, verbatim::

            inlineCH ::=
              [ CONSTRAINT <constraint_name> ] CHECK ( <expr> )
              [ ENABLE { VALIDATE | NOVALIDATE } ]

        The kind exists at both levels, so ``True``.  Two limitations that are
        properties of the clause rather than of the kind, and are recorded
        because they bound what a rendered CHECK can mean:

        * *"An inline CHECK constraint can reference only the column it's defined
          on.  To enforce a condition that spans multiple columns, define the
          constraint out of line."*
        * the predicate may not contain UDFs, aggregate/window/table functions,
          subqueries, state-changing or environment-dependent functions --
          *"System-defined functions that rely on the environment or execution
          context, such as the CURRENT_DATE function or the CURRENT_ROLE
          function."*
        * on a **hybrid** table, a CHECK may be created only in
          ``CREATE HYBRID TABLE``.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_foreign_key_constraint(self) -> bool:
        """True: core's ``format_column_fk_constraint`` may emit ``REFERENCES``.

        Official grammar: ``[ FOREIGN KEY ] REFERENCES <ref_table_name> [
        ( <ref_col_name> ) ]`` in ``inlineFK``, and ``FOREIGN KEY ( ... )
        REFERENCES ...`` in ``outoflineFK``.  Both levels, so ``True``.

        Known coupling, inherited from core and worth restating because it is the
        only switch where a per-level question has no per-level probe: this flat
        probe is what ``format_column_fk_constraint`` consults for the *column*
        level.  Snowflake answers ``True`` at both levels -- recorded separately
        at :meth:`supports_column_foreign_key_constraint` and
        :meth:`supports_table_foreign_key_constraint` -- so the coupling costs
        nothing here.

        Not enforced on standard tables: see
        :meth:`supports_primary_key_constraint` for the shared caveat.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_exclude_constraint(self) -> bool:
        """False: ``EXCLUDE`` is a PostgreSQL-family feature, absent here.

        Official grammar: neither page contains an ``EXCLUDE`` production.  The
        inline grammar's three branches are ``inlineUniquePK``, ``inlineFK`` and
        ``inlineCH``; the out-of-line grammar's three are ``outoflineUniquePK``,
        ``outoflineFK`` and ``outoflineCH``; and ``constraintAction``'s four
        alternatives are ``ADD``, ``RENAME``, ``{ ALTER | MODIFY }`` and
        ``DROP``.

        Declared locally because this switch is one of the few *table*-level
        probes core's ``format_table_constraint`` actually gates on -- the only
        kind there whose absence refuses by name rather than rendering.  So the
        ``False`` is load-bearing in a way the neighbouring kind switches are
        not, and it must not be left to an inherited default.

        Declared ``False`` rather than omitted: Snowflake's clustering keys are
        not exclusion constraints, and nothing on this dialect can express one.

        文档（待云验）: grammar-only, not server-verified.
        """
        return False

    # ------------------------------------------------------------------
    # Referential actions and ``MATCH`` -- the ``ConstraintMixin`` half of
    # each question.  The ``DDLColumnMixin`` halves are further down and are
    # the ones with teeth; both are declared so the halves cannot drift.
    # ------------------------------------------------------------------

    def supports_fk_on_delete(self) -> bool:
        """True: ``ON [ DELETE { ... } ]`` is in ``inlineFK`` and ``outoflineFK``.

        Official grammar::

            [ ON [ UPDATE { CASCADE | SET NULL | SET DEFAULT | RESTRICT | NO ACTION } ]
                 [ DELETE { CASCADE | SET NULL | SET DEFAULT | RESTRICT | NO ACTION } ] ]

        All five actions, ``Default: DELETE NO ACTION``.  One spelling note that
        affects rendering: a single ``ON`` covers both ``UPDATE`` and ``DELETE``,
        so ``ON DELETE CASCADE`` and ``ON UPDATE ... ON DELETE ...`` are not the
        same shape.

        Distinct from the flat declaration and from
        :meth:`supports_foreign_key_on_delete`, which is the probe
        ``format_references_clause`` raises on.  All three are ``True`` and all
        three are declared.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_fk_on_update(self) -> bool:
        """True: ``ON [ UPDATE { ... } ]`` is in ``inlineFK`` and ``outoflineFK``.

        Official grammar: the same ``ON`` group, quoted at
        :meth:`supports_fk_on_delete`.  Five actions, ``Default: UPDATE NO
        ACTION``.

        Distinct from :meth:`supports_foreign_key_on_update``, the
        ``DDLColumnMixin`` probe that ``format_references_clause`` raises on.
        Both ``True``; both declared.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_fk_match(self) -> bool:
        """**True -- corrected from the inherited ``False``.**  Snowflake has ``MATCH``.

        Official grammar::

            inlineFK ::=
              [ CONSTRAINT <constraint_name> ]
              [ FOREIGN KEY ]
              REFERENCES <ref_table_name> [ ( <ref_col_name> ) ]
              [ MATCH { FULL | SIMPLE | PARTIAL } ]
              ...

        and identically in ``outoflineFK``.  ``Default: MATCH FULL``.

        **How the inherited answer was ``False``, and why that was wrong.**  The
        probe is declared by *two* core mixins with *opposite* defaults --
        ``ConstraintMixin.supports_fk_match`` returns ``True`` and
        ``DDLColumnMixin.supports_fk_match`` returns ``False`` -- and C3
        linearisation gives priority to the one that appears earlier in the
        dialect's base list.  On this dialect that is ``DDLColumnMixin``, so the
        answer a caller got was ``False``: the shape of an accident, not a
        decision.

        The consequence was a refusal of the grammar's own clause.
        ``format_references_clause`` raises
        ``UnsupportedFeatureError(self.name, "FOREIGN KEY MATCH")`` whenever
        ``expr.match_type`` is set and this probe declines, so a caller writing
        ``match_type="FULL"`` against Snowflake was told Snowflake does not
        support ``MATCH`` -- while Snowflake's reference page lists all three
        modes and names ``FULL`` as the default.

        Declared locally so the ``True`` is Snowflake's statement rather than a
        side effect of two mixins' base-list order.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_deferrable_constraint(self) -> bool:
        """**False** -- the render decision, not the grammar answer.

        Official grammar: ``[ [ NOT ] DEFERRABLE ] [ INITIALLY { DEFERRED |
        IMMEDIATE } ]`` appear in ``inlineUniquePK``, ``inlineFK``,
        ``outoflineUniquePK`` and ``outoflineFK`` -- and in **neither** ``CHECK``
        branch.

        So the tokens are in the language, and the per-kind probes below record
        that.  This flat probe is the gate ``format_references_clause`` and
        ``format_constraint_traits`` raise on, and it answers ``False`` anyway,
        because this backend has no live server to confirm that Snowflake
        honours the clause: *"For standard tables, NOT NULL and CHECK are the
        only types of constraints that are enforced by Snowflake"*, so a
        rendered ``DEFERRABLE`` would be a promise nobody has seen kept.  Core's
        P1 flipped the shared default to ``False``; this declaration pins the
        answer locally so a core change cannot move it.  See the
        modifier-policy section of the module docstring.

        **The per-kind grammar answer lives elsewhere**, at
        :meth:`supports_column_deferrable_primary_key_constraint` and its
        siblings.  That is not a contradiction to tidy up: core has one flat
        probe, this server has no measurement, and the per-kind pair is the
        record a live run would be checked against.

        ``INITIALLY``'s inverted default (``INITIALLY DEFERRED``) is recorded at
        :meth:`supports_column_deferrable_primary_key_constraint`.

        文档（待云验）: grammar-only, not server-verified.
        """
        return False

    def supports_constraint_enforced(self) -> bool:
        """**False** -- the render decision, taken deliberately.

        Official grammar, in the two branches that have the token::

            inlineUniquePK ::= [ CONSTRAINT <n> ] { UNIQUE | PRIMARY KEY } [ [ NOT ] ENFORCED ] ...
            inlineFK       ::= [ CONSTRAINT <n> ] [ FOREIGN KEY ] REFERENCES ... [ [ NOT ] ENFORCED ] ...

        and in the two that do not::

            inlineCH ::= [ CONSTRAINT <n> ] CHECK ( <expr> ) [ ENABLE { VALIDATE | NOVALIDATE } ]
            outoflineCH ::= [ CONSTRAINT <n> ] CHECK ( <expr> ) [ ENABLE { VALIDATE | NOVALIDATE } ]

        So the clause is in the grammar for the key kinds, and the per-kind
        probes record exactly that.  This flat probe is what
        ``_format_constraint_enforcement`` consumes, and it answers ``False``:
        with no Snowflake instance reachable, a ``True`` would licence
        ``ENFORCED`` and ``NOT ENFORCED`` SQL nobody has seen the server accept,
        and the reference says the non-default spelling is worse than an error --
        *"for PRIMARY KEY, UNIQUE, and FOREIGN KEY constraints, if you specify
        ENABLE or VALIDATE ... the constraint isn't created."*  Core's P1 flipped
        the shared default to ``False``; this declaration pins it here so the
        answer is Snowflake's, not an inherited one.

        The kind-accurate grammar record lives at
        :meth:`supports_{column,table}_enforced_{primary_key,unique,foreign_key}_constraint`
        (``True``) and :meth:`supports_{column,table}_enforced_check_constraint`
        (``False``).  The two families disagree on purpose; see the
        modifier-policy section of the module docstring.

        ``Default: NOT ENFORCED`` -- the SQL-standard inverse -- and on a standard
        table the property changes nothing either way: *"For standard tables, NOT
        NULL and CHECK are the only types of constraints that are enforced by
        Snowflake, regardless of this property."*  A caller who sets nothing
        already gets ``NOT ENFORCED`` semantics, which is why refusing to spell it
        costs this backend nothing it actually relies on.

        文档（待云验）: grammar-only, not server-verified.
        """
        return False

    def supports_alter_constraint_enforced(self) -> bool:
        """**False -- declared explicitly, not inherited.**  The ALTER branch lists it.

        Official grammar, the ``{ ALTER | MODIFY }`` branch of
        ``constraintAction``, in full::

            | { ALTER | MODIFY } {   CONSTRAINT <constraint_name>
                                   | PRIMARY KEY
                                   | UNIQUE
                                   | FOREIGN KEY } ( <col_name> [ , ... ] )
                                 }
                [ [ NOT ] ENFORCED ] [ VALIDATE | NOVALIDATE ] [ RELY | NORELY ]

        ``[ [ NOT ] ENFORCED ]`` is the **first** of the three properties this
        branch can set, so the grammar answer is "the token is there".  This
        declaration is the *render* answer and it is ``False``, for the same
        reason as :meth:`supports_constraint_enforced`: no Snowflake instance is
        reachable, so ``ALTER CONSTRAINT ... [NOT] ENFORCED`` cannot be emitted
        on anyone's word; core's ``format_alter_constraint_action`` refuses it by
        name.  The backend already declared this ``False`` before this file
        existed, and the clause-pair guard pins both spellings to the refusal, so
        keeping it is the honest direction.

        Declared locally -- rather than left to core's shared default, which P1
        also flipped to ``False`` -- so the verdict is Snowflake's and the MRO
        guard can see which class owns it.

        This answers the property side of the fact
        :meth:`supports_table_alter_constraint` records: Snowflake's ALTER
        surface is **strictly smaller** than its ADD surface, and the properties
        it does have are exactly the three in the production above.  Deferral is
        ADD-only -- see the module docstring, and the comment on the render path
        in
        :mod:`~rhosocial.activerecord.backend.impl.snowflake.mixins.ddl`.

        文档（待云验）: grammar-only, not server-verified.
        """
        return False

    # ------------------------------------------------------------------
    # ALTER TABLE constraint lifecycle.
    #
    # Four verbs, and Snowflake is the most complete of the ten backends
    # compared this session -- all four are present:
    #
    #   ADD     -- out-of-line, all four kinds
    #   RENAME  -- ``RENAME CONSTRAINT <name> TO <new>``
    #   ALTER   -- ``{ ALTER | MODIFY } ...`` with three mutable properties
    #   DROP    -- by name *or* by kind + column list
    #
    # What it does **not** have is the set of standalone guard statements the
    # other backends reach for: no ``IF EXISTS`` on ``DROP CONSTRAINT``, no
    # ``IF NOT EXISTS`` on ``ADD``, no standalone ``VALIDATE CONSTRAINT``, and
    # no ``ENABLE``/``DISABLE CONSTRAINT``.  Those four absences are the ``False``
    # values below and each one is a grammar fact, not a gap in Snowflake.
    # ------------------------------------------------------------------

    def supports_add_constraint(self) -> bool:
        """True: ``ADD outoflineConstraint`` is the first branch of ``constraintAction``.

        Official grammar, verbatim::

            constraintAction ::=
              {
                 ADD outoflineConstraint
               | RENAME CONSTRAINT <constraint_name> TO <new_constraint_name>
               ...

        and ``outoflineConstraint``'s four branches, which reach all four kinds::

            outoflineConstraint ::=
              [ CONSTRAINT <constraint_name> ]
              {
                   UNIQUE [ ( <col_name> [ , <col_name> , ... ] ) ]
                 | PRIMARY KEY [ ( <col_name> [ , <col_name> , ... ] ) ]
                 | [ FOREIGN KEY ] [ ( <col_name> [ , <col_name> , ... ] ) ]
                                    REFERENCES <ref_table_name> [ ( <ref_col_name> [ , <ref_col_name> , ... ] ) ]
                 | CHECK ( <expr> )
              }
              [ <constraint_properties> ]

        This is the name core's ``format_add_table_constraint_action`` consults.
        The plan document's name for the same fact is
        ``supports_table_add_constraint``; the core name is declared because it is
        the one a formatter reads, and the per-kind entries just below carry the
        "which kinds" half.  Declaring both under two names would encode nothing
        and let the two drift.

        All four per-kind answers are ``True``, which is why this backend is the
        only one of the ten for which ``ADD CONSTRAINT`` reaches every kind.
        (BigQuery is the mirror image: the operation exists but adds a foreign key
        and nothing else.  SQLite adds none at all -- live-measured 2026-10-11.)

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_add_constraint_if_not_exists(self) -> bool:
        """False: the ``ADD`` branch has no ``IF NOT EXISTS``.

        Official grammar: ``ADD outoflineConstraint`` -- five tokens, no guard.
        Compare the column action on the same page, which **does** have one::

            ADD [ COLUMN ] [ IF NOT EXISTS ] <col_name> <col_type> ...

        So the absence is specific to the constraint branch and not to Snowflake's
        ``ADD`` vocabulary.  ``SnowflakeAlterColumnModifierMixin`` answers
        ``True`` for the column-level guard; this is the constraint-level answer,
        and BigQuery's ``True`` for the same switch is BigQuery's grammar
        (``ADD [CONSTRAINT [IF NOT EXISTS] constraint_name] FOREIGN KEY ...``),
        not a shared default.

        Name note: no core probe of this name exists; the guard is a per-branch
        question and this is its record.

        文档（待云验）: grammar-only, not server-verified.
        """
        return False

    def supports_table_add_primary_key_constraint(self) -> bool:
        """True: ``PRIMARY KEY [ ( ... ) ]`` is a branch of ``outoflineConstraint``.

        Official grammar: ``PRIMARY KEY [ ( <col_name> [ , <col_name> , ... ] ) ]``
        inside ``outoflineConstraint``, which is what ``ADD`` takes.

        Name note: no core probe is per-kind for ADD yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_add_unique_constraint(self) -> bool:
        """True: ``UNIQUE [ ( ... ) ]`` is a branch of ``outoflineConstraint``.

        Official grammar: ``UNIQUE [ ( <col_name> [ , <col_name> , ... ] ) ]``
        inside ``outoflineConstraint``.

        Name note: no core probe is per-kind for ADD yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_add_check_constraint(self) -> bool:
        """True for a standard table -- and ``False`` on a hybrid table, which no boolean can say.

        Official grammar: ``CHECK ( <expr> )`` is the fourth branch of
        ``outoflineConstraint``, so ``ADD CHECK (...)`` is in the grammar.

        The restriction is a property of the **table kind**, quoted verbatim from
        the reference::

            For hybrid tables, you can specify a CHECK constraint only in a
            CREATE HYBRID TABLE statement, not in an ALTER TABLE ... ADD
            CONSTRAINT statement.

        A boolean cannot express "addable, unless the table is hybrid", and the
        render path has no way to know the table kind today, so the honest
        dialect-level answer is ``True`` and the condition is recorded here.  A
        caller targeting a hybrid table must not rely on it.

        Name note: no core probe is per-kind for ADD yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_add_foreign_key_constraint(self) -> bool:
        """True: ``[ FOREIGN KEY ] [ ( ... ) ] REFERENCES ...`` is a branch of ``outoflineConstraint``.

        Official grammar: the third branch of ``outoflineConstraint``, quoted in
        full at :meth:`supports_add_constraint`.

        Note ``FOREIGN KEY`` is bracketed here even though the constraint page's
        dedicated ``outoflineFK`` production requires it.  The branch is
        identified by its ``REFERENCES`` clause either way.

        Name note: no core probe is per-kind for ADD yet.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_drop_constraint(self) -> bool:
        """True, and more capable here than on any other backend in this group.

        Official grammar, verbatim::

            | DROP {   CONSTRAINT <constraint_name>
                    | PRIMARY KEY
                    | UNIQUE | FOREIGN KEY } ( <col_name> [ , ... ] )
                [ CASCADE | RESTRICT ]

        Two addressable forms in one production: **by name** and **by kind plus
        column list**.  The 2026-10-11 live measurement found this is the only
        backend of the ten that can remove a constraint without naming it --
        MySQL's ``DROP CONSTRAINT`` namespace does not even contain the primary
        key, so there a primary key needs a different statement entirely.

        ``[ CASCADE | RESTRICT ]`` is on the branch.  Core's
        ``format_drop_table_constraint_action`` appends ``CASCADE`` when asked and
        has no ``RESTRICT`` gate; see the module docstring's known gaps.

        The by-name branch is also what a CHECK constraint must use: *"For CHECK
        constraints, the constraint_name is required."*

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_drop_constraint_by_kind(self) -> bool:
        """True -- Snowflake's one distinctive capability among the ten backends.

        Official grammar, verbatim::

            | DROP {   CONSTRAINT <constraint_name>
                    | PRIMARY KEY
                    | UNIQUE | FOREIGN KEY } ( <col_name> [ , ... ] )
                [ CASCADE | RESTRICT ]

        Read the four alternatives: ``PRIMARY KEY``, ``UNIQUE`` and
        ``FOREIGN KEY`` are constraint **kinds** in the drop position, each
        followed by a mandatory column list.  So ``ALTER TABLE t DROP PRIMARY KEY
        (a, b)`` is in the grammar without any constraint ever having been
        named.

        **Nothing else in this group can do this.**  The 2026-10-11 live
        measurement across nine reachable instances found drop-by-kind working
        nowhere: MySQL needs ``DROP PRIMARY KEY`` as a separate statement and its
        named drop will not touch a primary key at all; MariaDB, PostgreSQL,
        SQL Server, ClickHouse and Firebird drop by name only; Oracle and SQLite
        by name only.  Nine of ten drop by name; this is the tenth, and it drops
        both ways.

        **CHECK is excluded**, twice over: it is not in the kind list, and the
        reference adds *"For CHECK constraints, the constraint_name is required."*

        **Known gap, recorded not worked around.**  ``DropTableConstraint``
        carries a ``constraint_name`` only, so this shape has no node to hang on
        and cannot be rendered today.  A node carrying kind-plus-columns is core
        S1 work; the value here records that the capability exists so that work
        knows what to aim at.

        Name note: no core probe of this name exists.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_rename_constraint(self) -> bool:
        """True: ``RENAME CONSTRAINT <name> TO <new>`` is the second branch.

        Official grammar, verbatim::

            | RENAME CONSTRAINT <constraint_name> TO <new_constraint_name>

        The ALTER TABLE page's parameter text is the whole of the description:
        *"Renames the specified constraint."*

        Snowflake is one of only three backends in this group with a real rename
        verb -- PostgreSQL and Oracle are the others, and SQL Server reaches the
        same effect through ``sp_rename`` with its two-argument form.  MySQL,
        MariaDB, ClickHouse, Firebird and SQLite have none of the three.

        Reachable in practice because every Snowflake constraint is nameable
        (:meth:`supports_{column,table}_naming_*_constraint`), which is not
        something every backend can say.

        Name note: no core probe of this name exists; ``format_*`` for a rename
        action is core S1 work.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_table_alter_constraint(self) -> bool:
        """True: ``{ ALTER | MODIFY } ...`` is the third branch.

        Official grammar, verbatim::

            | { ALTER | MODIFY } {   CONSTRAINT <constraint_name>
                                   | PRIMARY KEY
                                   | UNIQUE
                                   | FOREIGN KEY } ( <col_name> [ , ... ] )
                                 }
                [ [ NOT ] ENFORCED ] [ VALIDATE | NOVALIDATE ] [ RELY | NORELY ]

        Three things in that production, all of them facts worth having written
        down:

        * **``ALTER`` and ``MODIFY`` are one operation with two spellings.**  They
          are alternatives in the grammar but they are *synonyms*, not
          distinguishable behaviours, so they collapse to a single semantic state
          with the spelling chosen by a formatter.  Two booleans would encode
          nothing.
        * **Addressable by name or by kind plus column list** -- and ``CHECK``
          by name only: *"For CHECK constraints, the constraint_name is
          required."*
        * **Only three mutable properties**, and deferral is not among them.
          ``[NOT] ENFORCED``, ``VALIDATE | NOVALIDATE``, ``RELY | NORELY`` --
          where ``ADD outoflineConstraint`` can set all six.  **Snowflake's ALTER
          surface is strictly smaller than its ADD surface**, which is the
          backend's defining asymmetry and the reason an ALTER path that could set
          ``DEFERRABLE`` would be wrong.

        The 2026-10-11 live measurement found this backend's ALTER verb together
        with MySQL's (which only manages ``[NOT] ENFORCED``) -- MySQL and
        Snowflake are the only two of the ten with any ``ALTER CONSTRAINT`` at
        all, and they are the two ends of the range: one property versus three.

        Name note: no core probe of this name exists.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_constraint_novalidate(self) -> bool:
        """False -- and this is about the ``NOT VALID`` *spelling*, not the ``NOVALIDATE`` property.

        Official grammar, on every production that can express the idea::

            [ { VALIDATE | NOVALIDATE } ]

        There is no ``NOT VALID`` token anywhere in Snowflake's constraint
        grammar, on either page.  ``NOVALIDATE`` is a single word.

        Core's ``_format_constraint_validation`` emits the two-word ``" NOT
        VALID"`` and gates it on this probe, so declaring ``False`` is what keeps
        that spelling out of Snowflake DDL.  Before the declaration the probe was
        simply **absent** from the backend, and core consulted it defensively; an
        absence doing the work of a decision.  Now it is a decision.

        **Must not be reconciled with**
        :meth:`supports_table_constraint_novalidate` / ``_column_``, which are
        ``True``.  Those gate the ``{ VALIDATE | NOVALIDATE }`` *property*, which
        Snowflake has and which is a different token from the ``NOT VALID``
        spelling.  Collapsing the two would either license a token that is not in
        the grammar or drop a property that is.

        文档（待云验）: grammar-only, not server-verified.
        """
        return False

    def supports_validate_constraint(self) -> bool:
        """False: there is no standalone ``VALIDATE CONSTRAINT`` statement.

        Official grammar: ``constraintAction`` has four alternatives -- ``ADD``,
        ``RENAME CONSTRAINT``, ``{ ALTER | MODIFY } ...`` and ``DROP ...``.  The
        only ``VALIDATE`` in the whole production is
        ``[ VALIDATE | NOVALIDATE ]``, which is an **attribute of the
        ``{ ALTER | MODIFY }`` branch** -- ``ALTER TABLE t ALTER CONSTRAINT c
        VALIDATE`` -- not a verb of its own.

        That distinction decides this switch, because its one consumer in core,
        ``format_validate_constraint_action``, renders a standalone
        ``VALIDATE CONSTRAINT <name>``:

            return f"VALIDATE CONSTRAINT {self.format_identifier(action.constraint_name)}", ()

        Declaring ``True`` would license a statement Snowflake's grammar does not
        contain.  The capability Snowflake *does* have -- validating a constraint
        through ``ALTER`` -- is recorded at
        :meth:`supports_table_alter_constraint` and, as a property, at
        :meth:`supports_table_constraint_novalidate`.

        **Recorded conflict.**  The 2026-10-11 live-findings matrix gives
        Snowflake a tick in its ``VALIDATE CONSTRAINT`` row, while the protocol
        list in the same document says ``supports_validate_constraint`` is True
        for PostgreSQL and Oracle only, *"其余 False"*.  The two rows of that one
        document disagree, and the grammar is what settles it: there is no
        standalone statement.  The matrix's tick is best read as "Snowflake can
        validate a constraint", which is true and is what the property switch
        says.

        Declared locally: core already answers ``False``; this is the pin.

        文档（待云验）: grammar-only, not server-verified.
        """
        return False

    # ------------------------------------------------------------------
    # The ``DDLColumnMixin`` pair that ``format_references_clause`` raises on,
    # plus the column ``COLLATE`` probe.  Declared here so every constraint
    # answer Snowflake gives comes from one file.
    # ------------------------------------------------------------------

    def supports_foreign_key_on_delete(self) -> bool:
        """True -- and this is the gate that stops ``ON DELETE`` being *refused*.

        Official grammar::

            [ ON [ UPDATE { CASCADE | SET NULL | SET DEFAULT | RESTRICT | NO ACTION } ]
                 [ DELETE { CASCADE | SET NULL | SET DEFAULT | RESTRICT | NO ACTION } ] ]

        ``DDLColumnMixin.format_references_clause`` consults this probe and
        raises ``UnsupportedFeatureError(self.name, "FOREIGN KEY ON DELETE")``
        when it declines.  ``DDLColumnMixin`` defaults it to ``True``, so the
        inherited answer happened to be right -- but it was inherited, and this
        backend declared nothing about it.

        All five actions.  Note the single-``ON`` spelling: Snowflake writes one
        ``ON`` covering both the optional ``UPDATE`` and the optional ``DELETE``
        keyword, where the SQL standard uses two.  A renderer that joins two
        separately-rendered clauses with ``" ON "`` twice will produce SQL
        Snowflake does not accept.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    def supports_foreign_key_on_update(self) -> bool:
        """True -- and this is the gate that stops ``ON UPDATE`` being *refused*.

        Official grammar: the same ``ON`` group, quoted at
        :meth:`supports_foreign_key_on_delete`.  ``DDLColumnMixin`` defaults this
        probe to ``True`` and ``format_references_clause`` raises on a ``False``,
        so again the inherited answer was right by default rather than by
        decision.

        All five actions, ``Default: UPDATE NO ACTION``.  Contrast Oracle 21c,
        which the 2026-10-11 live measurement found has **no** ``ON UPDATE``
        syntax at all -- Snowflake is at the opposite extreme and this is the
        record of it.

        文档（待云验）: grammar-only, not server-verified.
        """
        return True

    # ``supports_column_collation`` deliberately has **no** declaration here.
    # It is a column-attribute question (``COLLATE '<spec>'`` in the column
    # definition), not a constraint answer, and ``SnowflakeCollationMixin`` --
    # which precedes this class in the dialect's MRO -- already declares it
    # ``True`` next to the ``format_column_attribute`` that renders the quotes.
    # A second copy here would be dead code that the MRO never reaches, and two
    # owners for one switch is the thing the local-declaration rule exists to
    # prevent.  The draft that became this module carried such a copy; it was
    # dropped rather than kept in parallel with the runtime home.


__all__ = ["ALTER_TABLE_GRAMMAR_URL", "OFFICIAL_GRAMMAR_URL", "SnowflakeConstraintMixin"]