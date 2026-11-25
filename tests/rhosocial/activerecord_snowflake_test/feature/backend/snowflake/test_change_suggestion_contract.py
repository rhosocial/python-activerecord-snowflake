# tests/rhosocial/activerecord_snowflake_test/feature/backend/snowflake/test_change_suggestion_contract.py
"""Snowflake's four multi-step change suggestions answer explicit "unsupported".

The decision points are frozen, dialect-neutral projections of an old -> new
declaration. Snowflake can express none of them with the expression nodes this
backend actually owns:

* column reorder -- no column-position clause in ``ALTER TABLE``;
* constraint change -- the enriched declarations can build ``ADD CONSTRAINT``,
  but there is no two-anchor IF EXISTS / IF NOT EXISTS gate, no drop-by-kind
  node, and CHECK must be named;
* index change -- plain index DDL is hybrid-table-only and unmodelled;
* partition scheme change -- partitioning is AUTOMATIC (micro-partitions),
  and ``CLUSTER BY`` is clustering, not partition DDL.

Each answer is therefore the tri-state ``False`` (unaddressable), never ``None``
(absent) and never a guessed chain. The tests pin the value, the protocol
registration, the MRO ownership of each method, and the evidence behind the
refusal; no SQL is fabricated for any of the four. Core's enriched declaration
fields are checked explicitly: for the constraint point they remove the old
"no node can be built" objection, so the remaining reason must be capability.
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

#: label, method, value class, protocol, owning mixin
CASES = [
    (
        "column_reorder",
        "suggest_column_reorder",
        ColumnReorderSuggestion,
        ColumnReorderSuggestionSupport,
        SnowflakeColumnReorderSuggestionMixin,
    ),
    (
        "table_constraint_change",
        "suggest_table_constraint_change",
        TableConstraintChangeSuggestion,
        TableConstraintChangeSuggestionSupport,
        SnowflakeTableConstraintChangeSuggestionMixin,
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


@pytest.mark.parametrize("label,method,value_class,protocol,mixin", CASES, ids=IDS)
def test_protocol_is_registered(dialect, label, method, value_class, protocol, mixin):
    assert isinstance(dialect, protocol)


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


def test_column_reorder_evidence(dialect):
    """ALTER TABLE has no column-position clause and core has no reorder node."""
    assert dialect.supports_multi_action_alter_table() is False
    from rhosocial.activerecord.backend.expression.statements import ddl_alter

    assert not any("reorder" in name.lower() for name in dir(ddl_alter))
    doc = _module_doc(SnowflakeColumnReorderSuggestionMixin)
    assert "sql/alter-table" in doc
    assert "column-position" in doc
    assert "FIRST" in doc and "AFTER" in doc


def test_constraint_change_evidence(dialect):
    """ADD is renderable from live declarations; the blockers are capability."""
    assert dialect.supports_add_constraint() is True
    assert dialect.supports_drop_constraint() is True
    assert dialect.supports_drop_constraint_if_exists() is False
    assert dialect.supports_add_constraint_if_not_exists() is False
    assert dialect.supports_drop_constraint_by_kind() is True

    # The two existing nodes are by-value constraint / by-name drop. The first
    # is fed by the enriched declarations; the second has no kind/columns field
    # for the Snowflake-only drop-by-kind grammar.
    assert "constraint" in AddTableConstraintAction.__name__.lower()
    assert "constraint" in DropTableConstraintAction.__name__.lower()
    params = inspect.signature(DropTableConstraintAction.__init__).parameters
    assert "constraint_name" in params
    assert not {"kind", "branch", "columns"} & set(params)
    by_kind_doc = inspect.getdoc(dialect.supports_drop_constraint_by_kind)
    assert "CHECK" in by_kind_doc and "constraint_name is required" in by_kind_doc

    doc = _module_doc(SnowflakeTableConstraintChangeSuggestionMixin)
    assert "sql/alter-table" in doc
    assert "create-table-constraint" in doc
    assert "IF EXISTS" in doc
    assert "old_constraint_declarations" in doc
    assert "new_constraint_declarations" in doc
    assert "DropTableConstraintAction" in doc
    assert "projection" not in doc.lower()


def test_enriched_constraint_declarations_change_the_reason_not_the_answer(dialect):
    """Live branches are present and ADD-able; the answer stays False on capability."""
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

    # The enriched node is enough for a real ADD chain: no kind is lost any more.
    statement = AlterTableStatement(
        dialect,
        Table(dialect, point.table_name),
        [AddTableConstraintAction(dialect, new[0])],
    )
    assert statement.to_sql()[0] == (
        'ALTER TABLE "db.public.t" ADD CONSTRAINT "uq_email" UNIQUE ("email")'
    )
    assert isinstance(statement.actions[0].constraint.branch, TableUniqueConstraint)

    answer = dialect.suggest_table_constraint_change(point)
    assert answer.operations is False
    assert answer.state == "unaddressable"
    assert answer.old_constraint_declarations == old
    assert answer.new_constraint_declarations == new
    # Capability, not the shape of the point, is the remaining blocker.
    assert dialect.supports_add_constraint() is True
    assert dialect.supports_drop_constraint_if_exists() is False
    assert dialect.supports_add_constraint_if_not_exists() is False


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
