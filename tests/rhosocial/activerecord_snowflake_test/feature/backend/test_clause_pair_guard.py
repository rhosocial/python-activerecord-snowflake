# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_clause_pair_guard.py
"""Guard: every clause-parameter pair this dialect consumes is answerable.

The round's rule (core commit 438b7aa): each spellable alternative of a
two-spelling clause has its own parameter; "unspecified" is the state where
neither is set; setting both raises ``ValueError`` at construction. A formatter
that reads such a pair must answer *every* state: render the requested spelling
when the dialect can express it, refuse by name when it cannot. A state that
collapses into "unspecified" is a silent drop and fails here.

This file is the Snowflake counterpart of core's
``test_clause_pair_guard.py``. Core's guard renders through ``DummyDialect``,
which declares every capability ``True``, so it proves the *formatters* answer
each spelling. This one renders through ``SnowflakeDialect``, whose probes
answer ``False`` for several options, so it proves the *dialect* answers each
spelling too -- rendered where Snowflake's grammar has the words, refused by
name where it does not. Both halves are needed: a dialect probe that says
``False`` while its formatter silently ignores the request would pass core's
guard and still hand the caller a statement that lost a clause.

How the four states are compared
================================

Each case declares the expected outcome of each state as an *outcome
signature*: ``("rendered", sql)``, ``("refused", feature_name)``, or
``("value-error", message)``. The guard asserts:

* neither parameter -> the declared "neither" outcome (for a rendered
  outcome, neither spelling appears in the SQL);
* parameter A -> A's outcome; when rendered, A's spelling appears and B's
  does not (and vice versa), matched as regexes so ``ORDER`` is not read out
  of ``NOORDER``;
* both parameters -> ``ValueError`` with the exact mutual-exclusion message;
* the four signatures are pairwise distinct, except for the one declared
  shape where they cannot be: a pair whose *both* spellings the dialect
  cannot express is answered with the same refusal for A and B
  (``same_refusal_ok``). That is the dialect's one answer for the whole
  clause, not a collision between two answers; the guard still requires the
  refusal to differ from "neither".

Mandatory pairs (``AlterConstraint.enforced`` / ``not_enforced``) have no
"neither" state at all: the action *is* the keyword. They are guarded by
:class:`MandatoryPairCase`, which requires "neither" and "both" to raise
``ValueError`` and each requested spelling to be answered (rendered or refused
by name) rather than dropped.

Not server-verified
===================

There is no Snowflake instance on this machine and CI has none. Every
expectation here is render-only: the SQL strings and feature names are
compared with the Snowflake reference pages cited in the sibling test files
(``test_sequence_ddl.py``, ``test_identity_column.py``, ``test_pivot_unpivot.py``,
``test_routine.py``, ``test_undrop_clone_materialized_view.py``), not with a
server's answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.objects import (
    MaterializedView,
    Schema,
    Sequence,
    Table,
    View,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AlterConstraint,
)
from rhosocial.activerecord.backend.expression.statements.ddl_schema import (
    DropSchemaExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_sequence import (
    AlterSequenceExpression,
    CreateSequenceExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    DropTableExpression,
    IdentityClause,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_truncate import (
    TruncateExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_view import (
    CreateMaterializedViewExpression,
    DropMaterializedViewExpression,
    DropViewExpression,
)
from rhosocial.activerecord.backend.expression.statements.dql import QueryExpression
from rhosocial.activerecord.backend.expression.transaction import (
    BeginTransactionExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.routine import (
    SnowflakeCreateFunctionExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.pivot import (
    SnowflakeUnpivotExpression,
)

DIALECT_VERSION = (8, 0, 0)

#: ``("rendered", sql)`` / ``("refused", feature_name)`` / ``("value-error", fragment)``
Outcome = Tuple[str, str]


def _dialect() -> SnowflakeDialect:
    return SnowflakeDialect(version=DIALECT_VERSION)


def _table(d, name="t"):
    return Table(d, name)


def _query(d):
    return QueryExpression(d, select=[Column(d, "id")], from_=_table(d))


def _render(build: Callable[[], object]) -> Outcome:
    """Render one state; a refusal is an outcome, a construction error is too."""
    try:
        expr = build()
    except ValueError as exc:
        return ("value-error", str(exc))
    try:
        sql, _params = expr.to_sql()
    except UnsupportedFeatureError as exc:
        return ("refused", exc.feature_name)
    return ("rendered", sql)


@dataclass(frozen=True)
class PairCase:
    """One optional two-spelling clause, with the four states' expectations."""

    case_id: str
    build: Callable[..., object]
    a: str
    b: str
    neither: Outcome
    a_outcome: Outcome
    b_outcome: Outcome
    a_pattern: Optional[str] = None
    b_pattern: Optional[str] = None
    a_value: object = True
    b_value: object = True
    same_refusal_ok: bool = False
    note: str = ""

    def render(self, d, **kw) -> Outcome:
        return _render(lambda: self.build(d, **kw))

    def _check_spelling(self, sql: str, mine: Optional[str], other: Optional[str], label: str) -> None:
        if mine is not None:
            assert re.search(mine, sql), (
                f"{self.case_id}: {label} was rendered but its spelling {mine!r} "
                f"does not appear: {sql!r}"
            )
        if other is not None:
            assert not re.search(other, sql), (
                f"{self.case_id}: {label} was rendered but the other spelling "
                f"{other!r} also appears: {sql!r}"
            )


PAIR_CASES: Tuple[PairCase, ...] = (
    # ---------------------------------------------------------- sequences --
    PairCase(
        "CreateSequenceExpression.cycle",
        lambda d, **kw: CreateSequenceExpression(d, Sequence(d, "s"), **kw),
        "cycle",
        "no_cycle",
        ("rendered", 'CREATE SEQUENCE "s"'),
        ("refused", "SEQUENCE CYCLE"),
        ("refused", "SEQUENCE CYCLE"),
        same_refusal_ok=True,
        note="Snowflake has neither CYCLE nor NO CYCLE; both requests are refused by name.",
    ),
    PairCase(
        "CreateSequenceExpression.order",
        lambda d, **kw: CreateSequenceExpression(d, Sequence(d, "s"), **kw),
        "order",
        "no_order",
        ("rendered", 'CREATE SEQUENCE "s"'),
        ("rendered", 'CREATE SEQUENCE "s" ORDER'),
        ("rendered", 'CREATE SEQUENCE "s" NOORDER'),
        a_pattern=r"(?<!NO)ORDER\b",
        b_pattern=r"NOORDER\b",
        note="CREATE SEQUENCE [ { ORDER | NOORDER } ].",
    ),
    PairCase(
        "CreateSequenceExpression.cache",
        lambda d, **kw: CreateSequenceExpression(d, Sequence(d, "s"), **kw),
        "cache",
        "no_cache",
        ("rendered", 'CREATE SEQUENCE "s"'),
        ("refused", "SEQUENCE CACHE"),
        ("refused", "SEQUENCE CACHE"),
        a_value=10,
        same_refusal_ok=True,
        note="Snowflake has no CACHE clause on sequences.",
    ),
    PairCase(
        "AlterSequenceExpression.cycle",
        lambda d, **kw: AlterSequenceExpression(d, Sequence(d, "s"), **kw),
        "cycle",
        "no_cycle",
        ("rendered", 'ALTER SEQUENCE "s"'),
        ("refused", "ALTER SEQUENCE CYCLE"),
        ("refused", "ALTER SEQUENCE CYCLE"),
        same_refusal_ok=True,
    ),
    PairCase(
        "AlterSequenceExpression.order",
        lambda d, **kw: AlterSequenceExpression(d, Sequence(d, "s"), **kw),
        "order",
        "no_order",
        ("rendered", 'ALTER SEQUENCE "s"'),
        ("rendered", 'ALTER SEQUENCE "s" ORDER'),
        ("rendered", 'ALTER SEQUENCE "s" NOORDER'),
        a_pattern=r"(?<!NO)ORDER\b",
        b_pattern=r"NOORDER\b",
        note="ALTER SEQUENCE ... SET [ { ORDER | NOORDER } ].",
    ),
    PairCase(
        "AlterSequenceExpression.cache",
        lambda d, **kw: AlterSequenceExpression(d, Sequence(d, "s"), **kw),
        "cache",
        "no_cache",
        ("rendered", 'ALTER SEQUENCE "s"'),
        ("refused", "ALTER SEQUENCE CACHE"),
        ("refused", "ALTER SEQUENCE CACHE"),
        a_value=10,
        same_refusal_ok=True,
    ),
    # ----------------------------------------------------------- identity --
    PairCase(
        "IdentityClause.cycle",
        lambda d, **kw: IdentityClause(d, **kw),
        "cycle",
        "no_cycle",
        ("rendered", " IDENTITY(1, 1)"),
        ("refused", "IDENTITY CYCLE"),
        ("refused", "IDENTITY CYCLE"),
        same_refusal_ok=True,
    ),
    PairCase(
        "IdentityClause.order",
        lambda d, **kw: IdentityClause(d, **kw),
        "order",
        "no_order",
        ("rendered", " IDENTITY(1, 1)"),
        ("rendered", " IDENTITY(1, 1) ORDER"),
        ("rendered", " IDENTITY(1, 1) NOORDER"),
        a_pattern=r"(?<!NO)ORDER\b",
        b_pattern=r"NOORDER\b",
        note="IDENTITY [ ( start , step ) ] [ ORDER | NOORDER ].",
    ),
    PairCase(
        "IdentityClause.cache",
        lambda d, **kw: IdentityClause(d, **kw),
        "cache",
        "no_cache",
        ("rendered", " IDENTITY(1, 1)"),
        ("refused", "IDENTITY CACHE"),
        ("refused", "IDENTITY CACHE"),
        a_value=10,
        same_refusal_ok=True,
    ),
    # ------------------------------------------------------- drop family --
    PairCase(
        "DropSchemaExpression.cascade",
        lambda d, **kw: DropSchemaExpression(d, Schema(d, "s"), **kw),
        "cascade",
        "restrict",
        ("rendered", 'DROP SCHEMA "s"'),
        ("rendered", 'DROP SCHEMA "s" CASCADE'),
        ("rendered", 'DROP SCHEMA "s" RESTRICT'),
        a_pattern=r"\bCASCADE\b",
        b_pattern=r"\bRESTRICT\b",
        note="DROP SCHEMA [ CASCADE | RESTRICT ]; Snowflake accepts both.",
    ),
    PairCase(
        "DropTableExpression.cascade",
        lambda d, **kw: DropTableExpression(d, _table(d), **kw),
        "cascade",
        "restrict",
        ("rendered", 'DROP TABLE "t"'),
        ("refused", "DROP TABLE ... CASCADE"),
        ("rendered", 'DROP TABLE "t" RESTRICT'),
        b_pattern=r"\bRESTRICT\b",
        note=(
            "The dialect declares supports_drop_table_cascade() False, so CASCADE "
            "is refused by name; RESTRICT renders. The refusal is pinned so a "
            "future change to that pre-existing probe is visible here."
        ),
    ),
    PairCase(
        "DropViewExpression.cascade",
        lambda d, **kw: DropViewExpression(d, View(d, "v"), **kw),
        "cascade",
        "restrict",
        ("rendered", 'DROP VIEW "v"'),
        ("refused", "DROP VIEW CASCADE"),
        ("refused", "DROP VIEW RESTRICT"),
        note="The DROP VIEW reference has neither keyword; both are refused by name.",
    ),
    PairCase(
        "DropMaterializedViewExpression.cascade",
        lambda d, **kw: DropMaterializedViewExpression(d, MaterializedView(d, "mv"), **kw),
        "cascade",
        "restrict",
        ("rendered", 'DROP MATERIALIZED VIEW "mv"'),
        ("rendered", 'DROP MATERIALIZED VIEW "mv" CASCADE'),
        ("refused", "DROP MATERIALIZED VIEW RESTRICT"),
        a_pattern=r"\bCASCADE\b",
        note=(
            "CASCADE is rendered by core's shared formatter, which has no cascade "
            "probe; RESTRICT is gated by the dialect's new "
            "supports_materialized_view_restrict() (False). The reference page has "
            "neither keyword -- reported, not fixed here."
        ),
    ),
    # ----------------------------------------------------------- truncate --
    PairCase(
        "TruncateExpression.cascade",
        lambda d, **kw: TruncateExpression(d, _table(d), **kw),
        "cascade",
        "restrict",
        ("rendered", 'TRUNCATE TABLE "t"'),
        ("refused", "TRUNCATE ... CASCADE"),
        ("refused", "TRUNCATE ... RESTRICT"),
        note="The TRUNCATE reference has neither keyword; both are refused by name.",
    ),
    PairCase(
        "TruncateExpression.restart_identity",
        lambda d, **kw: TruncateExpression(d, _table(d), **kw),
        "restart_identity",
        "continue_identity",
        ("rendered", 'TRUNCATE TABLE "t"'),
        ("refused", "TRUNCATE ... RESTART IDENTITY"),
        ("refused", "TRUNCATE ... CONTINUE IDENTITY"),
        note="The TRUNCATE reference has no identity clause; both are refused by name.",
    ),
    # ---------------------------------------------- dialect-owned clauses --
    PairCase(
        "SnowflakeUnpivotExpression.include_nulls",
        lambda d, **kw: SnowflakeUnpivotExpression(
            d, value_column="v", pivot_column="k", columns=["a", "b"], **kw
        ),
        "include_nulls",
        "exclude_nulls",
        ("rendered", 'UNPIVOT ("v" FOR "k" IN ("a", "b"))'),
        ("rendered", 'UNPIVOT INCLUDE NULLS ("v" FOR "k" IN ("a", "b"))'),
        ("rendered", 'UNPIVOT EXCLUDE NULLS ("v" FOR "k" IN ("a", "b"))'),
        a_pattern=r"\bINCLUDE NULLS\b",
        b_pattern=r"\bEXCLUDE NULLS\b",
        note="UNPIVOT [ { INCLUDE | EXCLUDE } NULLS ]; omitting it is legal (default EXCLUDE).",
    ),
    PairCase(
        "SnowflakeCreateFunctionExpression.immutable",
        lambda d, **kw: SnowflakeCreateFunctionExpression(
            d, "f", returns="NUMBER", body="SELECT 1", **kw
        ),
        "immutable",
        "volatile",
        ("rendered", 'CREATE FUNCTION "f" () RETURNS NUMBER LANGUAGE SQL AS $$ SELECT 1 $$'),
        (
            "rendered",
            'CREATE FUNCTION "f" () RETURNS NUMBER LANGUAGE SQL IMMUTABLE AS $$ SELECT 1 $$',
        ),
        (
            "rendered",
            'CREATE FUNCTION "f" () RETURNS NUMBER LANGUAGE SQL VOLATILE AS $$ SELECT 1 $$',
        ),
        a_pattern=r"\bIMMUTABLE\b",
        b_pattern=r"\bVOLATILE\b",
        note="CREATE FUNCTION ... [ { VOLATILE | IMMUTABLE } ]; default VOLATILE.",
    ),
    PairCase(
        "CreateMaterializedViewExpression.with_data",
        lambda d, **kw: CreateMaterializedViewExpression(
            d, MaterializedView(d, "mv"), _query(d), **kw
        ),
        "with_data",
        "no_data",
        ("rendered", 'CREATE MATERIALIZED VIEW "mv" AS SELECT "id" FROM "t"'),
        ("refused", "MATERIALIZED VIEW WITH [NO] DATA"),
        ("refused", "MATERIALIZED VIEW WITH [NO] DATA"),
        same_refusal_ok=True,
        note=(
            "Snowflake has no WITH [NO] DATA: the view is created empty and filled "
            "in the background. Both spellings are refused by name instead of "
            "silently dropped."
        ),
    ),
    PairCase(
        "BeginTransactionExpression.deferrable",
        lambda d, **kw: BeginTransactionExpression(d, **kw),
        "deferrable",
        "not_deferrable",
        ("rendered", "BEGIN"),
        ("refused", "BEGIN TRANSACTION DEFERRABLE"),
        ("refused", "BEGIN TRANSACTION NOT DEFERRABLE"),
        note="Snowflake declares supports_deferrable_transaction() False; both spellings refuse.",
    ),
)

PAIR_IDS = [case.case_id for case in PAIR_CASES]


class TestFourStatesArePairwiseDistinguishable:
    """Every pair the dialect consumes answers all four states distinctly."""

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_neither_set_renders_neither_spelling(self, case):
        outcome = case.render(_dialect())
        assert outcome == case.neither, (
            f"{case.case_id}: neither parameter set -> {outcome!r}, "
            f"expected {case.neither!r}"
        )
        if outcome[0] == "rendered":
            sql = outcome[1]
            for pattern, label in ((case.a_pattern, case.a), (case.b_pattern, case.b)):
                if pattern is not None:
                    assert not re.search(pattern, sql), (
                        f"{case.case_id}: with neither parameter set the SQL still "
                        f"spells {label!r}: {sql!r}"
                    )

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_a_set_answers_a_only(self, case):
        outcome = case.render(_dialect(), **{case.a: case.a_value})
        assert outcome == case.a_outcome, (
            f"{case.case_id}: {case.a!r} -> {outcome!r}, expected {case.a_outcome!r}"
        )
        if outcome[0] == "rendered":
            case._check_spelling(outcome[1], case.a_pattern, case.b_pattern, repr(case.a))

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_b_set_answers_b_only(self, case):
        outcome = case.render(_dialect(), **{case.b: case.b_value})
        assert outcome == case.b_outcome, (
            f"{case.case_id}: {case.b!r} -> {outcome!r}, expected {case.b_outcome!r}"
        )
        if outcome[0] == "rendered":
            case._check_spelling(outcome[1], case.b_pattern, case.a_pattern, repr(case.b))

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_both_set_is_refused_at_construction(self, case):
        outcome = case.render(_dialect(), **{case.a: case.a_value, case.b: case.b_value})
        assert outcome[0] == "value-error", (
            f"{case.case_id}: setting both {case.a!r} and {case.b!r} -> {outcome!r}; "
            f"expected a construction-time ValueError"
        )
        assert f"{case.a} and {case.b} are mutually exclusive options" in outcome[1], (
            f"{case.case_id}: both-set message did not name the pair: {outcome[1]!r}"
        )

    @pytest.mark.parametrize("case", PAIR_CASES, ids=PAIR_IDS)
    def test_the_four_states_are_pairwise_distinguishable(self, case):
        d = _dialect()
        outcomes = [
            case.render(d),
            case.render(d, **{case.a: case.a_value}),
            case.render(d, **{case.b: case.b_value}),
            case.render(d, **{case.a: case.a_value, case.b: case.b_value}),
        ]
        signatures = set(outcomes)
        expected = 3 if case.same_refusal_ok else 4
        assert len(signatures) == expected, (
            f"{case.case_id}: the four states produced {len(signatures)} distinct "
            f"outcomes, expected {expected}: {outcomes!r}"
        )
        if case.same_refusal_ok:
            a_outcome, b_outcome = outcomes[1], outcomes[2]
            assert a_outcome == b_outcome == case.a_outcome, (
                f"{case.case_id}: same_refusal_ok is declared, but A and B do not "
                f"share the declared refusal: {a_outcome!r} / {b_outcome!r}"
            )
        else:
            assert outcomes[1] != outcomes[2], (
                f"{case.case_id}: A and B collapsed to the same outcome: "
                f"{outcomes[1]!r}"
            )


@dataclass(frozen=True)
class MandatoryPairCase:
    """A pair with no "neither" state: the clause *is* one of the two spellings."""

    case_id: str
    build: Callable[..., object]
    a: str
    b: str
    neither_fragment: str
    a_outcome: Outcome
    b_outcome: Outcome
    note: str = ""


MANDATORY_CASES: Tuple[MandatoryPairCase, ...] = (
    MandatoryPairCase(
        "AlterConstraint.enforced",
        lambda d, **kw: AlterConstraint(
            d, "c", constraint_type=TableConstraintType.CHECK, **kw
        ),
        "enforced",
        "not_enforced",
        "AlterConstraint requires exactly one of",
        ("refused", "ALTER CONSTRAINT ENFORCED/NOT ENFORCED"),
        ("refused", "ALTER CONSTRAINT ENFORCED/NOT ENFORCED"),
        note=(
            "Snowflake declares supports_alter_constraint_enforced() False; both "
            "spellings are refused by name, neither is dropped."
        ),
    ),
)

MANDATORY_IDS = [case.case_id for case in MANDATORY_CASES]


class TestMandatoryPairs:
    """A mandatory pair: neither and both raise; each spelling is answered."""

    @pytest.mark.parametrize("case", MANDATORY_CASES, ids=MANDATORY_IDS)
    def test_neither_set_is_refused(self, case):
        outcome = _render(lambda: case.build(_dialect()))
        assert outcome[0] == "value-error", f"{case.case_id}: {outcome!r}"
        assert case.neither_fragment in outcome[1], f"{case.case_id}: {outcome[1]!r}"

    @pytest.mark.parametrize("case", MANDATORY_CASES, ids=MANDATORY_IDS)
    def test_each_spelling_is_answered(self, case):
        for param, expected in ((case.a, case.a_outcome), (case.b, case.b_outcome)):
            outcome = _render(lambda p=param: case.build(_dialect(), **{p: True}))
            assert outcome == expected, (
                f"{case.case_id}: {param!r} -> {outcome!r}, expected {expected!r}"
            )

    @pytest.mark.parametrize("case", MANDATORY_CASES, ids=MANDATORY_IDS)
    def test_both_set_is_refused_at_construction(self, case):
        outcome = _render(lambda: case.build(_dialect(), **{case.a: True, case.b: True}))
        assert outcome[0] == "value-error", f"{case.case_id}: {outcome!r}"
        assert f"{case.a} and {case.b} are mutually exclusive options" in outcome[1], (
            f"{case.case_id}: {outcome[1]!r}"
        )


class TestGuardIsNotVacuous:
    """The guard's own lists and channels cannot pass by accident."""

    def test_case_ids_are_distinct(self):
        ids = PAIR_IDS + MANDATORY_IDS
        assert len(ids) == len(set(ids)), f"duplicate case ids: {ids}"

    def test_every_pair_has_two_distinct_parameters(self):
        for case in PAIR_CASES:
            assert case.a != case.b, case.case_id

    def test_every_consumed_pair_is_covered(self):
        """The pairs this backend's formatters and probes consume.

        The set is stated so a pair cannot leave the guard silently. Pairs
        consumed only by core's shared formatters with no Snowflake probe
        override (SetOperation ``all_``/``distinct``, CTE
        ``materialized``/``not_materialized``, CreateTableAs ``with_data``/
        ``no_data``, the constraint classes' deferral/enforcement) are covered
        by core's ``test_clause_pair_guard.py`` and are deliberately not
        duplicated here; the report lists them as inherited.
        """
        expected = {
            "CreateSequenceExpression.cycle",
            "CreateSequenceExpression.order",
            "CreateSequenceExpression.cache",
            "AlterSequenceExpression.cycle",
            "AlterSequenceExpression.order",
            "AlterSequenceExpression.cache",
            "IdentityClause.cycle",
            "IdentityClause.order",
            "IdentityClause.cache",
            "DropSchemaExpression.cascade",
            "DropTableExpression.cascade",
            "DropViewExpression.cascade",
            "DropMaterializedViewExpression.cascade",
            "TruncateExpression.cascade",
            "TruncateExpression.restart_identity",
            "SnowflakeUnpivotExpression.include_nulls",
            "SnowflakeCreateFunctionExpression.immutable",
            "CreateMaterializedViewExpression.with_data",
            "BeginTransactionExpression.deferrable",
        }
        covered = {case.case_id for case in PAIR_CASES}
        assert expected == covered, (
            f"pairs in scope but not guarded: {sorted(expected - covered)}; "
            f"guarded but not in scope: {sorted(covered - expected)}"
        )
        assert {case.case_id for case in MANDATORY_CASES} == {"AlterConstraint.enforced"}


class TestSentinels:
    """Each assertion channel is shown rejecting a deliberately wrong claim.

    A guard that has never been seen to fail is not evidence. These feed the
    channels a wrong claim and require the channel to reject it.
    """

    def test_wrong_expected_sql_is_rejected(self):
        d = _dialect()
        sql = CreateSequenceExpression(d, Sequence(d, "s"), no_order=True).to_sql()[0]
        with pytest.raises(AssertionError):
            assert sql == 'CREATE SEQUENCE "s" ORDER'

    def test_wrong_expected_feature_name_is_rejected(self):
        d = _dialect()
        with pytest.raises(AssertionError):
            with pytest.raises(UnsupportedFeatureError) as exc_info:
                CreateSequenceExpression(d, Sequence(d, "s"), no_cycle=True).to_sql()
            assert exc_info.value.feature_name == "SEQUENCE ORDER"

    def test_wrong_collision_claim_is_rejected(self):
        """The before/after channel: unspecified and no_order must NOT collide."""
        d = _dialect()
        with pytest.raises(AssertionError):
            assert (
                CreateSequenceExpression(d, Sequence(d, "s")).to_sql()[0]
                == CreateSequenceExpression(d, Sequence(d, "s"), no_order=True).to_sql()[0]
            )

    def test_wrong_unpivot_default_claim_is_rejected(self):
        """The measured collision: unspecified must not spell EXCLUDE NULLS."""
        d = _dialect()
        sql = SnowflakeUnpivotExpression(
            d, value_column="v", pivot_column="k", columns=["a", "b"]
        ).to_sql()[0]
        with pytest.raises(AssertionError):
            assert sql == 'UNPIVOT EXCLUDE NULLS ("v" FOR "k" IN ("a", "b"))'
