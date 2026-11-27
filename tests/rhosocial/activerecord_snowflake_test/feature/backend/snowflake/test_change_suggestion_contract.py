# tests/rhosocial/activerecord_snowflake_test/feature/backend/snowflake/test_change_suggestion_contract.py
"""Snowflake's multi-step change suggestions: three unsupported, one real.

The decision points are frozen, dialect-neutral projections of an old -> new
declaration.  Snowflake can express none of these with the expression nodes
this backend owns:

* column reorder -- no column-position clause in ``ALTER TABLE``;
* index change -- plain index DDL is hybrid-table-only and unmodelled;
* partition scheme change -- partitioning is AUTOMATIC (micro-partitions),
  and ``CLUSTER BY`` is clustering, not partition DDL.

Each of those answers is the tri-state ``False`` (unaddressable), never ``None``
(absent) and never a guessed chain.

The table-constraint point is different: core's enriched declarations carry the
live ``TableConstraint`` nodes, and core now lets ``DropTableConstraintAction``
carry a declaration.  Snowflake's own ``DROP PRIMARY KEY | UNIQUE | FOREIGN KEY
(cols)`` grammar therefore becomes reachable, so removals and redefinitions of
the key kinds produce real single-action ``AlterTableStatement`` chains.  The
remaining refusals are grammar/capability gaps: an unnamed CHECK has no drop
address, a CHECK cannot be added by ``ALTER TABLE`` without ``ENABLE
NOVALIDATE``, and the enforcement/deferral/validation traits are declined by
this dialect's probes.
"""

import inspect
import sys
from types import MappingProxyType

import pytest

from rhosocial.activerecord.backend.dialect.partition_capability import (
    PartitionCapability,
)
from rhosocial.activerecord.backend.expression import (
    Column,
    ComparisonPredicate,
    IndexDefinition,
    Literal,
    TableCheckConstraint,
    TableConstraint,
    TableForeignKeyConstraint,
    TablePrimaryKeyConstraint,
    TableUniqueConstraint,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddTableConstraintAction,
    AlterTableStatement,
    DropTableConstraintAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_partition import (
    PartitionClause,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnDefinition,
)
from rhosocial.activerecord.backend.expression.types import DataType
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import (
    SnowflakeColumnReorderSuggestionMixin,
    SnowflakePartitionSchemeChangeSuggestionMixin,
    SnowflakeTableConstraintChangeSuggestionMixin,
    SnowflakeTableIndexChangeSuggestionMixin,
)
from rhosocial.activerecord.backend.suggestion.definitions import (
    ColumnReorderSuggestion,
    PartitionSchemeChangeSuggestion,
    TableConstraintChangeSuggestion,
    TableIndexChangeSuggestion,
)
from rhosocial.activerecord.backend.suggestion.protocols import (
    ColumnReorderSuggestionSupport,
    PartitionSchemeChangeSuggestionSupport,
    TableConstraintChangeSuggestionSupport,
    TableIndexChangeSuggestionSupport,
)
from rhosocial.activerecord.migration import resolve_point

#: label, method, value class, protocol, owning mixin -- for the three points
#: whose answer is still the explicit unsupported state.
CASES = [
    (
        "column_reorder",
        "suggest_column_reorder",
        ColumnReorderSuggestion,
        ColumnReorderSuggestionSupport,
        SnowflakeColumnReorderSuggestionMixin,
    ),
    (
        "table_index_change",
        "suggest_table_index_change",
        TableIndexChangeSuggestion,
        TableIndexChangeSuggestionSupport,
        SnowflakeTableIndexChangeSuggestionMixin,
    ),
    (
        "partition_scheme_change",
        "suggest_partition_scheme_change",
        PartitionSchemeChangeSuggestion,
        PartitionSchemeChangeSuggestionSupport,
        SnowflakePartitionSchemeChangeSuggestionMixin,
    ),
]
IDS = [case[0] for case in CASES]

CONSTRAINT_CASE = (
    "table_constraint_change",
    "suggest_table_constraint_change",
    TableConstraintChangeSuggestion,
    TableConstraintChangeSuggestionSupport,
    SnowflakeTableConstraintChangeSuggestionMixin,
)

#: Realistic frozen projections, in the shape core's ``_freeze`` produces.
POINTS = {
    ColumnReorderSuggestion: {
        "old_order": ("id", "name"),
        "new_order": ("name", "id"),
        "reordered_columns": ("name",),
    },
    TableConstraintChangeSuggestion: {
        "old_constraints": (("params", {"name": "uq_name", "kind": "UNIQUE"}),),
        "new_constraints": (),
    },
    TableIndexChangeSuggestion: {
        "old_indexes": (("params", {"name": "ix_name", "columns": ("name",)}),),
        "new_indexes": (),
    },
    PartitionSchemeChangeSuggestion: {
        "old_partition": None,
        "new_partition": ("params", {"columns": ("created_at",)}),
    },
}


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


def _point(value_class):
    return value_class(table_name="db.public.t", **POINTS[value_class])


def _module_doc(mixin):
    return inspect.getdoc(sys.modules[mixin.__module__]) or ""


def _check(dialect, name=None):
    return TableConstraint(
        dialect,
        branch=TableCheckConstraint(
            dialect,
            ComparisonPredicate(
                dialect, "=", Column(dialect, "age"), Literal(dialect, 0, inline=True)
            ),
        ),
        name=name,
    )


def _primary_key(dialect, columns, name=None):
    return TableConstraint(
        dialect, branch=TablePrimaryKeyConstraint(dialect, columns), name=name
    )


def _unique(dialect, columns, name=None):
    return TableConstraint(
        dialect, branch=TableUniqueConstraint(dialect, columns), name=name
    )


def _foreign_key(dialect, columns, name=None):
    return TableConstraint(
        dialect,
        branch=TableForeignKeyConstraint(
            dialect, columns, (Table(dialect, "parent"), ["id"])
        ),
        name=name,
    )


def _constraint_answer(dialect, old=(), new=(), table="t"):
    point = TableConstraintChangeSuggestion(
        table_name=table,
        old_constraint_declarations=tuple(old),
        new_constraint_declarations=tuple(new),
    )
    return dialect.suggest_table_constraint_change(point)


def _sql(answer):
    return [statement.to_sql()[0] for statement in answer.operations]


@pytest.mark.parametrize("label,method,value_class,protocol,mixin", CASES, ids=IDS)
def test_protocol_is_registered(dialect, label, method, value_class, protocol, mixin):
    assert isinstance(dialect, protocol)


def test_constraint_protocol_is_registered(dialect):
    assert isinstance(dialect, TableConstraintChangeSuggestionSupport)


@pytest.mark.parametrize("label,method,value_class,protocol,mixin", CASES, ids=IDS)
def test_answer_is_the_explicit_unsupported_tri_state(
    dialect, label, method, value_class, protocol, mixin
):
    answer = getattr(dialect, method)(_point(value_class))
    assert isinstance(answer, value_class)
    assert answer.operations is False
    assert answer.state == "unaddressable"
    # False is a distinct state: not a chain (tuple) and not silence (None).
    assert answer.operations is not None
    assert not isinstance(answer.operations, tuple)


@pytest.mark.parametrize("label,method,value_class,protocol,mixin", CASES, ids=IDS)
def test_answer_keeps_the_point_context(dialect, label, method, value_class, protocol, mixin):
    point = _point(value_class)
    answer = getattr(dialect, method)(point)
    assert answer is not point
    assert answer.label == label
    assert answer.table_name == point.table_name
    for field_name, original in POINTS[value_class].items():
        assert getattr(answer, field_name) == original


@pytest.mark.parametrize("label,method,value_class,protocol,mixin", CASES, ids=IDS)
def test_method_is_owned_by_the_backend_mixin_not_the_protocol_stub(
    dialect, label, method, value_class, protocol, mixin
):
    """A protocol stub returning None must never shadow the real answer."""
    declaring = next(cls for cls in type(dialect).__mro__ if method in cls.__dict__)
    assert declaring is mixin, f"{method} is resolved on {declaring!r}"


def test_constraint_method_is_owned_by_the_backend_mixin(dialect):
    method = CONSTRAINT_CASE[1]
    declaring = next(cls for cls in type(dialect).__mro__ if method in cls.__dict__)
    assert declaring is SnowflakeTableConstraintChangeSuggestionMixin


@pytest.mark.parametrize("label,method,value_class,protocol,mixin", CASES, ids=IDS)
def test_no_supported_chain_and_no_sql_is_fabricated(
    dialect, label, method, value_class, protocol, mixin
):
    """There is no supported chain, so there is nothing to render to SQL.

    A tuple of expression nodes would be the only actionable state; this
    dialect never manufactures one and never puts SQL text in an answer.
    """
    answer = getattr(dialect, method)(_point(value_class))
    assert answer.operations is False
    assert not isinstance(answer.operations, (tuple, str))
    # No field of the answer carries an expression node (the only objects
    # that could later be rendered into SQL). Labels and names are strings.
    assert not any(hasattr(value, "to_sql") for value in vars(answer).values())


def test_constraint_point_without_declarations_is_unaddressable(dialect):
    """The frozen projections alone cannot rebuild an action."""
    point = _point(TableConstraintChangeSuggestion)
    answer = dialect.suggest_table_constraint_change(point)
    assert answer.operations is False
    assert answer.state == "unaddressable"


# ---------------------------------------------------------------------------
# The supported half: real chains from the live declarations
# ---------------------------------------------------------------------------


def test_unnamed_primary_key_removal_is_a_real_drop_by_kind(dialect):
    primary_key = _primary_key(dialect, ["id"])
    answer = _constraint_answer(dialect, old=(primary_key,))

    assert answer.state == "actions"
    assert _sql(answer) == ['ALTER TABLE "t" DROP PRIMARY KEY']
    statement = answer.operations[0]
    assert isinstance(statement, AlterTableStatement)
    action = statement.action
    assert isinstance(action, DropTableConstraintAction)
    assert action.constraint is primary_key
    assert action.constraint_name is None


def test_unnamed_unique_removal_renders_its_columns(dialect):
    unique = _unique(dialect, ["a", "b"])
    answer = _constraint_answer(dialect, old=(unique,))

    assert _sql(answer) == ['ALTER TABLE "t" DROP UNIQUE ("a", "b")']
    assert answer.operations[0].action.constraint is unique


def test_unnamed_foreign_key_removal_renders_its_local_columns(dialect):
    foreign_key = _foreign_key(dialect, ["a"])
    answer = _constraint_answer(dialect, old=(foreign_key,))

    assert _sql(answer) == ['ALTER TABLE "t" DROP FOREIGN KEY ("a")']
    assert answer.operations[0].action.constraint is foreign_key


def test_named_check_removal_uses_the_name_form(dialect):
    check = _check(dialect, name="ck_age")
    answer = _constraint_answer(dialect, old=(check,))

    assert _sql(answer) == ['ALTER TABLE "t" DROP CONSTRAINT "ck_age"']
    action = answer.operations[0].action
    assert action.constraint_name == "ck_age"
    assert action.constraint is None


def test_unnamed_check_removal_is_refused_because_check_needs_a_name(dialect):
    answer = _constraint_answer(dialect, old=(_check(dialect),))
    assert answer.operations is False
    assert answer.state == "unaddressable"


def test_adding_a_check_is_refused_for_the_missing_enable_novalidate(dialect):
    answer = _constraint_answer(dialect, new=(_check(dialect, name="ck_age"),))
    assert answer.operations is False
    assert answer.state == "unaddressable"


def test_same_name_primary_key_redefinition_drops_then_adds(dialect):
    old = _primary_key(dialect, ["a"], name="pk_t")
    new = _primary_key(dialect, ["a", "b"], name="pk_t")
    answer = _constraint_answer(dialect, old=(old,), new=(new,))

    assert answer.state == "actions"
    assert _sql(answer) == [
        'ALTER TABLE "t" DROP PRIMARY KEY',
        'ALTER TABLE "t" ADD CONSTRAINT "pk_t" PRIMARY KEY ("a", "b")',
    ]
    drop_action, add_action = (
        answer.operations[0].action,
        answer.operations[1].action,
    )
    assert isinstance(drop_action, DropTableConstraintAction)
    assert drop_action.constraint is old
    assert isinstance(add_action, AddTableConstraintAction)
    assert add_action.constraint is new


def test_adding_a_key_is_a_real_add_statement(dialect):
    unique = _unique(dialect, ["email"], name="uq_email")
    answer = _constraint_answer(dialect, new=(unique,))

    assert _sql(answer) == [
        'ALTER TABLE "t" ADD CONSTRAINT "uq_email" UNIQUE ("email")'
    ]
    assert answer.operations[0].action.constraint is unique


def test_unchanged_declarations_need_no_action(dialect):
    unique = _unique(dialect, ["a"])
    answer = _constraint_answer(
        dialect, old=(unique,), new=(_unique(dialect, ["a"]),)
    )

    assert answer.operations is None
    assert answer.state == "absent"


def test_the_chain_passes_the_consumers_single_action_guard(dialect):
    """One expression -> one statement, and nothing table- or schema-level."""
    old = (
        _primary_key(dialect, ["id"]),
        _check(dialect, name="ck_age"),
    )
    new = (_unique(dialect, ["email"], name="uq_email"),)
    answer = _constraint_answer(dialect, old=old, new=new)

    entry = resolve_point(
        TableConstraintChangeSuggestion(
            table_name="t",
            old_constraint_declarations=old,
            new_constraint_declarations=new,
            operations=answer.operations,
        ),
        dialect,
    )
    assert entry.state == "actions"
    for statement in entry.operations:
        assert isinstance(statement, AlterTableStatement)
        assert statement.action is not None
        sql, params = statement.to_sql()
        assert sql.startswith("ALTER TABLE ")
        assert "DROP TABLE" not in sql
        assert "DROP SCHEMA" not in sql
        assert params == ()


def test_constraint_change_evidence(dialect):
    """ADD and the by-kind DROP are renderable; the remaining gaps are grammar."""
    assert dialect.supports_add_constraint() is True
    assert dialect.supports_drop_constraint() is True
    assert dialect.supports_drop_constraint_if_exists() is False
    assert dialect.supports_add_constraint_if_not_exists() is False
    assert dialect.supports_drop_constraint_by_kind() is True

    # The declaration-carrying drop node is what the by-kind form needs.
    assert "constraint" in DropTableConstraintAction.__name__.lower()
    params = inspect.signature(DropTableConstraintAction.__init__).parameters
    assert "constraint_name" in params
    assert "constraint" in params
    assert "if_exists" in params
    assert "cascade" in params

    by_kind_doc = inspect.getdoc(dialect.supports_drop_constraint_by_kind)
    assert "CHECK" in by_kind_doc and "constraint_name is required" in by_kind_doc
    assert "Now renderable" in by_kind_doc

    doc = _module_doc(SnowflakeTableConstraintChangeSuggestionMixin)
    assert "sql/alter-table" in doc
    assert "create-table-constraint" in doc
    assert "IF EXISTS" in doc
    assert "old_constraint_declarations" in doc
    assert "new_constraint_declarations" in doc
    assert "DropTableConstraintAction" in doc
    assert "ENABLE NOVALIDATE" in doc
    assert "projection" not in doc.lower()


def test_enriched_declarations_yield_a_complete_constraint_chain(dialect):
    """The old capability objection is gone: the live branches build the chain."""
    check = ComparisonPredicate(dialect, "=", Column(dialect, "age"), Literal(dialect, 0))
    old = (
        TableConstraint(dialect, branch=TablePrimaryKeyConstraint(dialect, ["id"]), name="pk_t"),
        TableConstraint(dialect, branch=TableCheckConstraint(dialect, check), name="ck_age"),
    )
    new = (
        TableConstraint(dialect, branch=TableUniqueConstraint(dialect, ["email"]), name="uq_email"),
    )
    point = TableConstraintChangeSuggestion(
        table_name="db.public.t",
        old_constraints=(("params", {"name": "pk_t"}), ("params", {"name": "ck_age"})),
        new_constraints=(("params", {"name": "uq_email"}),),
        old_constraint_declarations=old,
        new_constraint_declarations=new,
    )

    assert point.old_constraint_declarations == old
    assert point.new_constraint_declarations == new
    assert isinstance(old[0].branch, TablePrimaryKeyConstraint)
    assert isinstance(old[1].branch, TableCheckConstraint)
    assert isinstance(new[0].branch, TableUniqueConstraint)

    answer = dialect.suggest_table_constraint_change(point)
    assert answer.state == "actions"
    assert [statement.to_sql()[0] for statement in answer.operations] == [
        'ALTER TABLE "db.public.t" DROP PRIMARY KEY',
        'ALTER TABLE "db.public.t" DROP CONSTRAINT "ck_age"',
        'ALTER TABLE "db.public.t" ADD CONSTRAINT "uq_email" UNIQUE ("email")',
    ]
    assert answer.old_constraint_declarations == old
    assert answer.new_constraint_declarations == new


def test_enriched_fields_leave_the_other_three_answers_unchanged(dialect):
    """The new declaration fields are carried through, never turned into actions."""
    column = ColumnDefinition(dialect, "name", DataType.as_type(dialect, "VARCHAR(64)"))
    fields = MappingProxyType({"name": column})
    index = IndexDefinition(dialect, "ix_name", ["name"])
    partition = PartitionClause(dialect, "HASH", [Column(dialect, "name")])
    cases = (
        (
            ColumnReorderSuggestion,
            "suggest_column_reorder",
            {
                "old_fields": fields,
                "new_fields": fields,
            },
        ),
        (
            TableIndexChangeSuggestion,
            "suggest_table_index_change",
            {
                "old_index_declarations": (index,),
                "new_index_declarations": (),
            },
        ),
        (
            PartitionSchemeChangeSuggestion,
            "suggest_partition_scheme_change",
            {
                "old_partition_declaration": None,
                "new_partition_declaration": partition,
            },
        ),
    )
    for value_class, method, enriched in cases:
        point = value_class(table_name="db.public.t", **POINTS[value_class], **enriched)
        answer = getattr(dialect, method)(point)
        assert answer.operations is False, method
        for field_name, value in enriched.items():
            assert getattr(answer, field_name) is value


def test_index_change_evidence(dialect):
    """Every plain-index probe is False and the hybrid family is unmodelled."""
    for probe in (
        "supports_create_index",
        "supports_drop_index",
        "supports_indexes",
        "supports_inline_index",
        "supports_alter_table_index_actions",
        "supports_index_if_exists",
        "supports_index_if_not_exists",
    ):
        assert getattr(dialect, probe)() is False, probe
    assert not hasattr(dialect, "format_create_hybrid_index_statement")
    assert not hasattr(dialect, "format_drop_hybrid_index_statement")
    doc = _module_doc(SnowflakeTableIndexChangeSuggestionMixin)
    assert "sql/create-index" in doc
    assert "sql/drop-index" in doc
    assert "hybrid" in doc.lower()


def test_automatic_partitioning_does_not_fabricate_a_chain(dialect):
    """AUTOMATIC capability and CLUSTER BY are not partition DDL."""
    point = _point(PartitionSchemeChangeSuggestion)
    answer = dialect.suggest_partition_scheme_change(point)
    assert dialect.partition_capability() is PartitionCapability.AUTOMATIC
    assert dialect.supports_table_partitioning() is False
    assert dialect.supports_cluster_by() is True
    # Clustering exists, yet it must not become a partition action chain.
    assert answer.operations is False
    assert not isinstance(answer.operations, tuple)
    doc = _module_doc(SnowflakePartitionSchemeChangeSuggestionMixin)
    assert "micro-partitions" in doc
    assert "CLUSTER BY" in doc
    assert "tables-clustering-micropartitions" in doc
