# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_snowflake_constraint_switches.py
"""Snowflake constraint capability switches: values, locality, and evidence level.

**not server-verified.**  There is no Snowflake instance reachable from this
repository, so nothing asserted here is a measurement.  Every verdict is read
off the two official grammar pages transcribed in
``impl/snowflake/mixins/constraint.py`` (``create-table-constraint`` for the
inline/out-of-line productions and ``alter-table`` for ``constraintAction``),
and each switch's docstring carries that record next to the ``待云验`` marker.
A rendering assertion below pins *what this dialect does with* a switch; it says
nothing about what a server would do with the SQL.

Three things are asserted, and the second two are the easy ones to lose:

* **the value** -- what the declaration answers;
* **the locality** -- that the answer resolves to a class in *this* backend's
  package.  A switch that silently fell back to core's ``ConstraintMixin`` could
  have its default moved out from under Snowflake by a commit in another
  repository, with nothing failing here.  Declaring the switch locally is what
  makes such a move a visible test failure instead of a quiet contract change;
* **the probe shape** -- ``(self)`` and nothing else, so the parameterised
  ``constraint_type`` signatures the draft carried cannot come back.  A probe
  answers one question; per-kind narrowing belongs to a formatter.
"""

import inspect

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.ddl_column import DDLColumnMixin
from rhosocial.activerecord.backend.dialect.mixins.ddl_table import ConstraintMixin
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.statements import (
    ColumnCheckConstraint,
    ColumnConstraint,
    ColumnDefaultConstraint,
    ColumnForeignKeyConstraint,
    ColumnNotNullConstraint,
    ColumnNullableConstraint,
    ColumnPrimaryKeyConstraint,
    ColumnUniqueConstraint,
    TableCheckConstraint,
    TableConstraint,
    TableForeignKeyConstraint,
    TablePrimaryKeyConstraint,
    TableUniqueConstraint,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import (
    SnowflakeConstraintMixin,
)

#: The version the render assertions use.  8.0.0 is the dialect's own default.
DIALECT_VERSION = (8, 0, 0)

#: Every constraint switch core's renderers or the protocol consult, with
#: Snowflake's declared answer.  This mapping is the contract; the locality and
#: probe-shape tests below walk it, so a switch cannot leave the backend --
#: or grow a parameter -- without failing first.
CONSTRAINT_SWITCHES = {
    # Constraint kinds.
    "supports_primary_key_constraint": True,
    "supports_unique_constraint": True,
    "supports_not_null_constraint": True,
    "supports_check_constraint": True,
    "supports_foreign_key_constraint": True,
    "supports_exclude_constraint": False,
    # Referential actions and MATCH.
    "supports_fk_on_delete": True,
    "supports_fk_on_update": True,
    "supports_fk_match": True,
    "supports_foreign_key_on_delete": True,
    "supports_foreign_key_on_update": True,
    # Named constraints (SQL-92), consulted by both render paths.
    "supports_constraint_naming": True,
    # Clause attributes -- the render decision, deliberately False without a
    # live server.  See the module docstring of the mixin.
    "supports_deferrable_constraint": False,
    "supports_constraint_enforced": False,
    "supports_alter_constraint_enforced": False,
    "supports_constraint_novalidate": False,
    # ALTER TABLE lifecycle.
    "supports_add_constraint": True,
    "supports_drop_constraint": True,
    "supports_drop_constraint_if_exists": False,
    "supports_validate_constraint": False,
    # The two that live on other Snowflake mixins but answer constraint
    # questions, so they are pinned here too.
    "supports_column_comment": True,
}

#: Probes that core does not declare at all.  They are declared here so the
#: grammar answer is written down in one place, and they are kept apart from the
#: flat switches above because no formatter reads them: the flat probe is the
#: render decision, and these are its per-level / per-kind elaboration.
BACKEND_ONLY_SWITCHES = (
    "supports_column_primary_key_constraint",
    "supports_column_unique_constraint",
    "supports_column_check_constraint",
    "supports_column_foreign_key_constraint",
    "supports_table_primary_key_constraint",
    "supports_table_unique_constraint",
    "supports_table_check_constraint",
    "supports_table_foreign_key_constraint",
    "supports_column_naming_primary_key_constraint",
    "supports_column_naming_unique_constraint",
    "supports_column_naming_check_constraint",
    "supports_column_naming_foreign_key_constraint",
    "supports_table_naming_primary_key_constraint",
    "supports_table_naming_unique_constraint",
    "supports_table_naming_check_constraint",
    "supports_table_naming_foreign_key_constraint",
    "supports_column_enforced_primary_key_constraint",
    "supports_column_enforced_unique_constraint",
    "supports_column_enforced_foreign_key_constraint",
    "supports_column_enforced_check_constraint",
    "supports_table_enforced_primary_key_constraint",
    "supports_table_enforced_unique_constraint",
    "supports_table_enforced_foreign_key_constraint",
    "supports_table_enforced_check_constraint",
    "supports_column_deferrable_primary_key_constraint",
    "supports_column_deferrable_unique_constraint",
    "supports_column_deferrable_foreign_key_constraint",
    "supports_column_deferrable_check_constraint",
    "supports_table_deferrable_primary_key_constraint",
    "supports_table_deferrable_unique_constraint",
    "supports_table_deferrable_foreign_key_constraint",
    "supports_table_deferrable_check_constraint",
    "supports_column_constraint_enable_disable",
    "supports_table_constraint_enable_disable",
    "supports_column_constraint_novalidate",
    "supports_table_constraint_novalidate",
    "supports_column_constraint_rely",
    "supports_table_constraint_rely",
    "supports_column_fk_match",
    "supports_table_fk_match",
    "supports_column_on_update_action",
    "supports_table_on_update_action",
    "supports_table_constraint_comment",
    "supports_add_constraint_if_not_exists",
    "supports_table_add_primary_key_constraint",
    "supports_table_add_unique_constraint",
    "supports_table_add_check_constraint",
    "supports_table_add_foreign_key_constraint",
    "supports_drop_constraint_by_kind",
    "supports_table_rename_constraint",
    "supports_table_alter_constraint",
)

#: The substring every switch docstring must carry: this backend cannot
#: measure, and a docstring that stops saying so reads as a measurement.
EVIDENCE_MARKER = "not server-verified"

#: The two reference pages every production was transcribed from.  Every
#: docstring names at least one grammar fragment, and the two constants are
#: asserted so the pages themselves cannot drift.
GRAMMAR_URL_FRAGMENTS = ("create-table-constraint", "alter-table")


def _dialect():
    return SnowflakeDialect(version=DIALECT_VERSION)


class TestConstraintSwitchValues:
    """What the declaration answers."""

    @pytest.mark.parametrize(
        "switch, expected",
        CONSTRAINT_SWITCHES.items(),
        ids=sorted(CONSTRAINT_SWITCHES),
    )
    def test_switch_answers_the_declared_value(self, switch, expected):
        assert getattr(_dialect(), switch)() is expected

    def test_the_two_enforcement_probes_and_deferral_are_false(self):
        """The render decision, taken deliberately without a server.

        The grammar has ``[ [ NOT ] ENFORCED ]`` and ``[ [ NOT ] DEFERRABLE ]``
        for the key kinds, so a ``True`` would be defensible as a *grammar*
        reading.  It is refused instead because the reference states the
        non-default ``ENABLE`` / ``VALIDATE`` spelling means the constraint is
        *not created*, silently -- emitting it would be worse than a syntax
        error.  Pinned so a later change has to argue with the reason.
        """
        d = _dialect()
        assert d.supports_constraint_enforced() is False
        assert d.supports_alter_constraint_enforced() is False
        assert d.supports_deferrable_constraint() is False

    def test_the_grammar_record_still_says_the_tokens_are_there(self):
        """The per-kind record is the other half, and it is not reconciled away.

        ``supports_{column,table}_enforced_{primary_key,unique,foreign_key}_constraint``
        and the matching deferral probes answer ``True`` because the grammar
        contains the clauses; only CHECK is ``False``, at both levels.  The flat
        probes answer the render question.  Collapsing the two would lose the
        record an eventual live run would be checked against.
        """
        d = _dialect()
        for kind in ("primary_key", "unique", "foreign_key"):
            for level in ("column", "table"):
                assert getattr(d, f"supports_{level}_enforced_{kind}_constraint")() is True
                assert getattr(d, f"supports_{level}_deferrable_{kind}_constraint")() is True
        for level in ("column", "table"):
            assert getattr(d, f"supports_{level}_enforced_check_constraint")() is False
            assert getattr(d, f"supports_{level}_deferrable_check_constraint")() is False


class TestConstraintSwitchSignature:
    """Every probe is ``(self)``, with no exceptions."""

    @pytest.mark.parametrize(
        "switch", sorted(CONSTRAINT_SWITCHES), ids=sorted(CONSTRAINT_SWITCHES)
    )
    def test_probe_takes_no_argument(self, switch):
        """Checked on the bound method, so a defaulted parameter cannot slip in.

        ``(self, constraint_type=None)`` is still callable with no argument, and
        that is exactly how the draft's two probes passed for a while.  The
        signature is read off the function, not off a call.
        """
        d = _dialect()
        bound = getattr(d, switch)
        signature = inspect.signature(bound)
        assert list(signature.parameters) == [], (
            f"{switch} takes {list(signature.parameters)}; every constraint probe "
            f"answers one question with no arguments"
        )


class TestConstraintSwitchesAreDeclaredLocally:
    """The verdict must be this backend's, not an inherited default."""

    @pytest.mark.parametrize(
        "switch", sorted(CONSTRAINT_SWITCHES), ids=sorted(CONSTRAINT_SWITCHES)
    )
    def test_switch_is_declared_by_a_snowflake_mixin(self, switch):
        owners = [
            cls
            for cls in SnowflakeDialect.__mro__
            if switch in getattr(cls, "__dict__", {})
        ]
        assert owners, f"{switch} is declared by no class in the MRO"
        assert any(
            cls.__module__.startswith(
                "rhosocial.activerecord.backend.impl.snowflake"
            )
            for cls in owners
        ), (
            f"{switch} is declared only outside this package ({owners}); it would "
            f"fall through to a core default this repository cannot pin"
        )

    @pytest.mark.parametrize(
        "switch", sorted(CONSTRAINT_SWITCHES), ids=sorted(CONSTRAINT_SWITCHES)
    )
    def test_resolved_switch_is_owned_by_this_backend(self, switch):
        owner = getattr(_dialect(), switch).__qualname__
        module = inspect.getmodule(getattr(_dialect(), switch)).__name__
        assert module.startswith(
            "rhosocial.activerecord.backend.impl.snowflake"
        ), f"{switch} resolves to {owner} in {module}, not this backend"

    def test_backend_mixin_precedes_the_core_constraint_mixins(self):
        """MRO order is what makes the local declarations win at all."""
        mro = SnowflakeDialect.__mro__
        local = mro.index(SnowflakeConstraintMixin)
        assert local < mro.index(ConstraintMixin), (
            "SnowflakeConstraintMixin must precede core's ConstraintMixin"
        )
        assert local < mro.index(DDLColumnMixin), (
            "SnowflakeConstraintMixin must precede DDLColumnMixin"
        )


class TestEveryDeclaredProbeIsPinned:
    """The tables above are exact, in both directions."""

    def test_no_switch_in_the_mixin_is_missing_from_the_tables(self):
        declared = {
            name
            for name in vars(SnowflakeConstraintMixin)
            if name.startswith("supports_")
        }
        pinned = set(CONSTRAINT_SWITCHES) | set(BACKEND_ONLY_SWITCHES)
        # The two constraint surfaces that belong to other mixins and are
        # pinned above because they answer constraint questions.
        elsewhere = {"supports_column_comment", "supports_drop_constraint_if_exists"}
        missing = declared - pinned
        assert not missing, (
            f"{sorted(missing)} are declared on the mixin but pinned nowhere; "
            f"add each to CONSTRAINT_SWITCHES or BACKEND_ONLY_SWITCHES"
        )
        stale = (pinned - elsewhere) - declared
        assert not stale, (
            f"{sorted(stale)} are pinned but no longer declared on the mixin"
        )

    def test_the_general_kind_switch_lives_on_the_capability_mixin(self):
        """``supports_constraints`` is a general switch, not a per-kind one."""
        d = _dialect()
        assert d.supports_constraints() is True


class TestSwitchDocstringsCarryTheirEvidenceLevel:
    """A verdict that cannot be traced is a guess with a name."""

    @pytest.mark.parametrize(
        "switch",
        sorted(set(CONSTRAINT_SWITCHES) | set(BACKEND_ONLY_SWITCHES)),
        ids=sorted(set(CONSTRAINT_SWITCHES) | set(BACKEND_ONLY_SWITCHES)),
    )
    def test_docstring_says_it_is_not_server_verified(self, switch):
        # Scoped to this module: ``supports_column_comment`` and
        # ``supports_drop_constraint_if_exists`` are declared by another
        # Snowflake mixin and carry their own evidence, which is not this
        # wave's to rewrite.  They are still pinned for value and locality
        # above, where the question is the same.
        if switch not in vars(SnowflakeConstraintMixin):
            pytest.skip(f"{switch} is declared by another Snowflake mixin")
        doc = getattr(SnowflakeConstraintMixin, switch).__doc__
        assert doc, f"{switch} has no docstring: the evidence has nowhere to live"
        assert EVIDENCE_MARKER in doc, (
            f"{switch} does not say {EVIDENCE_MARKER!r}; a switch that stops "
            f"admitting it was not measured reads as a measurement"
        )

    def test_module_docstring_states_the_evidence_level_and_the_policy(self):
        """The header is where the level and the modifier policy are argued."""
        doc = SnowflakeConstraintMixin.__doc__ or ""
        module_doc = inspect.getmodule(SnowflakeConstraintMixin).__doc__ or ""
        combined = doc + module_doc
        assert "Nothing here was measured" in combined
        assert EVIDENCE_MARKER in combined
        assert "Modifier policy" in combined, (
            "the module docstring must argue why the enforcement and deferral "
            "probes are False while the grammar has the tokens"
        )
        for fragment in GRAMMAR_URL_FRAGMENTS:
            assert fragment in combined, f"the reference page {fragment!r} is not cited"


class TestConstraintRendering:
    """What this dialect does with each kind.  A render, not a measurement."""

    @pytest.fixture
    def dialect(self):
        return _dialect()

    def _table(self, dialect):
        return Table(dialect, "other")

    def test_column_kinds_render_their_standard_spellings(self, dialect):
        for branch, expected in (
            (ColumnPrimaryKeyConstraint(dialect), ' CONSTRAINT "c" PRIMARY KEY'),
            (ColumnUniqueConstraint(dialect), ' CONSTRAINT "c" UNIQUE'),
            (ColumnNotNullConstraint(dialect), ' CONSTRAINT "c" NOT NULL'),
            (ColumnNullableConstraint(dialect), ' CONSTRAINT "c" NULL'),
            (ColumnDefaultConstraint(dialect, "x"), " CONSTRAINT \"c\" DEFAULT 'x'"),
            (
                ColumnCheckConstraint(
                    dialect,
                    ComparisonPredicate(
                        dialect, "=", Column(dialect, "a"), Column(dialect, "b")
                    ),
                ),
                ' CONSTRAINT "c" CHECK ("a" = "b")',
            ),
        ):
            sql, params = ColumnConstraint(dialect, branch=branch, name="c").to_sql()
            assert sql == expected, (type(branch).__name__, sql)
            assert params == ()

    def test_column_foreign_key_renders_references_and_actions(self, dialect):
        branch = ColumnForeignKeyConstraint(
            dialect, (self._table(dialect), ["id"]), on_delete="CASCADE"
        )
        sql, params = ColumnConstraint(dialect, branch=branch).to_sql()
        assert "REFERENCES" in sql
        assert "ON DELETE CASCADE" in sql
        assert params == ()

    def test_match_is_rendered_because_the_probe_says_so(self, dialect):
        """``MATCH`` is the one inherited answer that was refusing real grammar.

        Core's ``DDLColumnMixin`` declares ``supports_fk_match`` False and
        precedes ``ConstraintMixin`` (True) in a dialect that declares nothing,
        so the inherited answer refused a clause Snowflake's reference lists.
        This is the render that confirms the local ``True`` reaches the path.
        """
        branch = ColumnForeignKeyConstraint(
            dialect, (self._table(dialect), ["id"]), match_type="FULL"
        )
        sql, _ = ColumnConstraint(dialect, branch=branch).to_sql()
        assert "MATCH FULL" in sql

    def test_table_kinds_render_their_standard_spellings(self, dialect):
        cases = (
            (TablePrimaryKeyConstraint(dialect, ["a", "b"]), 'PRIMARY KEY ("a", "b")'),
            (TableUniqueConstraint(dialect, ["a"]), 'UNIQUE ("a")'),
            (
                TableCheckConstraint(
                    dialect,
                    ComparisonPredicate(
                        dialect, "=", Column(dialect, "a"), Column(dialect, "b")
                    ),
                ),
                'CHECK (',
            ),
        )
        for branch, expected in cases:
            sql, params = TableConstraint(
                dialect, branch=branch, name="c"
            ).to_sql()
            assert sql.startswith('CONSTRAINT "c" '), sql
            assert expected in sql, sql
            assert params == ()

    def test_table_foreign_key_renders_its_references(self, dialect):
        branch = TableForeignKeyConstraint(
            dialect, ["a"], (self._table(dialect), ["id"])
        )
        sql, params = TableConstraint(dialect, branch=branch, name="fk").to_sql()
        assert sql.startswith('CONSTRAINT "fk" FOREIGN KEY ("a") REFERENCES'), sql
        assert params == ()

    def test_exclude_is_refused_by_name(self, dialect):
        """Snowflake has no EXCLUDE production; the branch refuses rather than renders."""
        from rhosocial.activerecord.backend.expression.statements import (
            TableExcludeConstraint,
        )

        with pytest.raises(UnsupportedFeatureError) as exc_info:
            TableConstraint(
                dialect, branch=TableExcludeConstraint(dialect, ["a"])
            ).to_sql()
        assert "EXCLUDE" in str(exc_info.value)

    def test_naming_prefix_is_gated_on_the_naming_probe(self, dialect):
        """The prefix renders because the probe is True, and the probe is consulted.

        A column constraint with a name renders ``CONSTRAINT <n>``; the same
        clause without a name does not.  That alone would pass even if the probe
        were never read, so the gate is also flipped: a dialect that answers
        ``False`` must refuse the named clause instead of dropping the name.
        """
        named, _ = ColumnConstraint(
            dialect, branch=ColumnNotNullConstraint(dialect), name="c"
        ).to_sql()
        unnamed, _ = ColumnConstraint(
            dialect, branch=ColumnNotNullConstraint(dialect)
        ).to_sql()
        assert named == ' CONSTRAINT "c" NOT NULL'
        assert unnamed == " NOT NULL"

        class _NoNames(SnowflakeDialect):
            def supports_constraint_naming(self) -> bool:
                return False

        refusing = _NoNames(version=DIALECT_VERSION)
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            ColumnConstraint(
                refusing, branch=ColumnNotNullConstraint(refusing), name="c"
            ).to_sql()
        assert "CONSTRAINT name" in str(exc_info.value)
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            TableConstraint(
                refusing,
                branch=TablePrimaryKeyConstraint(refusing, ["a"]),
                name="c",
            ).to_sql()
        assert "CONSTRAINT name" in str(exc_info.value)


class TestModifierSpellingsAreRefusedByName:
    """The fail-closed half of the modifier policy, asserted as refusals."""

    @pytest.fixture
    def dialect(self):
        return _dialect()

    def _fk(self, dialect):
        return ColumnForeignKeyConstraint(dialect, (Table(dialect, "t"), ["id"]))

    @pytest.mark.parametrize("flag", ("enforced", "not_enforced"))
    def test_column_enforcement_is_refused(self, dialect, flag):
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            ColumnConstraint(
                dialect, branch=self._fk(dialect), **{flag: True}
            ).to_sql()
        assert "ENFORCED" in str(exc_info.value)

    @pytest.mark.parametrize("flag", ("enforced", "not_enforced"))
    def test_table_enforcement_is_refused(self, dialect, flag):
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            TableConstraint(
                dialect,
                branch=TablePrimaryKeyConstraint(dialect, ["a"]),
                **{flag: True},
            ).to_sql()
        assert "ENFORCED" in str(exc_info.value)

    def test_deferral_is_refused(self, dialect):
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            ColumnConstraint(
                dialect, branch=self._fk(dialect), deferrable=True
            ).to_sql()
        assert "DEFERRABLE" in str(exc_info.value)

    def test_deferral_on_a_check_is_refused_at_construction_first(self, dialect):
        """The kind gate fires before the probe, and that is the node's job.

        A CHECK branch cannot carry deferral at all, so the refusal is core's
        ``ValueError`` from ``validate_branch_traits`` -- earlier, and for a
        different reason, than the dialect's ``UnsupportedFeatureError``.
        """
        with pytest.raises(ValueError):
            ColumnConstraint(
                dialect,
                branch=ColumnCheckConstraint(
                    dialect,
                    ComparisonPredicate(
                        dialect, "=", Column(dialect, "a"), Column(dialect, "b")
                    ),
                ),
                deferrable=True,
            )

    def test_not_valid_spelling_is_refused(self, dialect):
        """``NOT VALID`` is not Snowflake syntax, and the probe keeps it out."""
        from rhosocial.activerecord.backend.expression.statements import (
            AddTableConstraint,
            ConstraintValidation,
        )

        action = AddTableConstraint(
            dialect,
            TableConstraint(
                dialect,
                branch=TableCheckConstraint(
                    dialect,
                    ComparisonPredicate(
                        dialect, "=", Column(dialect, "a"), Column(dialect, "b")
                    ),
                ),
                name="ck",
                validation=ConstraintValidation.NOVALIDATE,
            ),
        )
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            action.to_sql()
        assert "NOT VALID" in str(exc_info.value)

    def test_alter_constraint_enforcement_is_refused_by_name(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import (
            AlterConstraint,
        )

        for flag in ("enforced", "not_enforced"):
            with pytest.raises(UnsupportedFeatureError) as exc_info:
                AlterConstraint(
                    dialect,
                    constraint_name="ck",
                    constraint_kind=TableCheckConstraint,
                    **{flag: True},
                ).to_sql()
            assert "ALTER CONSTRAINT" in str(exc_info.value)

    def test_validate_constraint_has_no_standalone_statement(self, dialect):
        from rhosocial.activerecord.backend.expression.statements import (
            ValidateConstraint,
        )

        with pytest.raises(UnsupportedFeatureError) as exc_info:
            ValidateConstraint(dialect, constraint_name="ck").to_sql()
        assert "VALIDATE CONSTRAINT" in str(exc_info.value)

    def test_add_column_if_not_exists_restriction_is_kind_based(self, dialect):
        """The IF NOT EXISTS guard reads the branch class, not a deleted enum.

        Snowflake refuses ``ADD COLUMN IF NOT EXISTS`` on a column that also
        carries DEFAULT / IDENTITY / PK / FK / UNIQUE.  Every branch that trips
        it is asserted, so the migration off ``ColumnConstraintType`` cannot have
        silently emptied the set.
        """
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnDefinition,
        )
        from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
            AddColumn,
        )
        from rhosocial.activerecord.backend.expression.types import IntegerType

        forbidden = (
            ColumnDefaultConstraint(dialect, 1),
            ColumnPrimaryKeyConstraint(dialect),
            ColumnForeignKeyConstraint(dialect, (Table(dialect, "t"), ["id"])),
            ColumnUniqueConstraint(dialect),
        )
        for branch in forbidden:
            column = ColumnDefinition(
                dialect,
                "c",
                IntegerType(dialect),
                constraints=[ColumnConstraint(dialect, branch=branch)],
            )
            with pytest.raises(UnsupportedFeatureError):
                AddColumn(dialect, column, if_not_exists=True).to_sql()

        allowed = ColumnDefinition(
            dialect,
            "c",
            IntegerType(dialect),
            constraints=[ColumnConstraint(dialect, branch=ColumnNotNullConstraint(dialect))],
        )
        sql, _ = AddColumn(dialect, allowed, if_not_exists=True).to_sql()
        assert sql == 'ADD COLUMN IF NOT EXISTS "c" INTEGER NOT NULL'
