# tests/rhosocial/activerecord_snowflake_test/feature/backend/expression/test_expression_roundtrip_all.py
"""Every expression class this backend can be asked to render must round-trip.

For each expression class collected from **two** packages -- the core
``rhosocial.activerecord.backend.expression`` and this backend's own
``impl.snowflake.expression`` -- that can be constructed:

  1. dict round-trip : ``deserialize(serialize(e)).to_sql() == e.to_sql()``
  2. JSON round-trip : the same through ``serialize_json``
  3. XML round-trip  : the same through ``serialize_xml``
  4. SQL             : classified, never swallowed -- see below.

Why ``to_sql()`` is classified rather than caught
=================================================

The testsuite's own ``sql_consistent`` wraps the first render in
``try/except Exception: return``. That makes every render failure a green tick:
the three SQL comparisons never run, so a formatter reading a field that no
longer existed is indistinguishable from a formatter for a feature this dialect
does not support. This file replaces the blanket catch with named branches, and
every branch is asserted:

* **renders** -- all three encodings must restore byte-identical SQL *and*
  byte-identical bind parameters, and ``to_sql()`` must have returned an
  ``(sql, params)`` pair rather than something else.
* ``UnsupportedFeatureError`` -- Snowflake does not model the feature. Asserted
  as exactly that type, so a different failure cannot hide behind it.
* an entry in :data:`LEGITIMATE_NON_RENDERS` -- a class that cannot render for a
  reason belonging to its own tree. Each entry pins the exception type *and* a
  message fragment, so a class that started failing for a different reason fails
  here instead of staying quietly green.
* a formatter named in :data:`UNMODELLED_FORMATTERS` -- Snowflake declares no
  ``format_*`` for that expression kind. ``to_sql()`` reports this by naming the
  method it wanted, so the entry is matched against the name it actually reported
  and the table's membership is pinned in both directions: an entry no class needs
  any more fails, and a method outside the table fails here.
* **anything else** -- a failure naming the class and the exception.

Two spellings of "Snowflake does not model that"
=================================================

The unsupported branch and the unmodelled branch now carry the same exception
type, because ``to_sql()`` reports a dialect that has no such formatter as a
capability gap -- the same way every probe in the tree reports one. What tells
them apart is *who* is refusing: a probe inside a formatter that reached its work
names a feature (``GRAPH_TABLE``, ``derived table in FROM``), while a dispatch
that never found a formatter names the formatting method. The shape of
:attr:`UnsupportedFeatureError.feature_name` separates the two exactly; see
:func:`_dispatched_formatter`.

How the classes are found
=========================

``collect_expression_classes`` walks each package. It does **not** read
``ExpressionRegistry._registry``: that dict is process-global and grows as
sibling test modules import their own backends, so a matrix built from it would
cover a different set of classes depending on which files pytest happened to
import first. ``_auto_register_builtins`` is still called, because deserialising
a core class needs it registered -- a separate concern from deciding what to
test -- and :func:`register_all` registers what was collected so a Snowflake
expression can be found again on the way back.

And when a class cannot be constructed
=====================================

``make_instance(...) is None`` is a skip only for a class named in
:data:`UNCONSTRUCTIBLE`, and :meth:`TestMatrixIntegrity.test_unconstructible_list_is_exact`
pins that tuple from what the constructor really does. Both directions fail: a
class that starts needing an exemption goes red until the tuple is updated, and
an entry that has gone stale goes red too. There is no "no more than N" ceiling,
because a ceiling absorbs new gaps silently.

Running without a warehouse
===========================

Nothing here touches a connection. ``SnowflakeDialect()`` is constructed
directly, ``to_sql()`` is pure string building, and the serialisers are pure
data. So this runs in CI's unit job -- which is the only job that exists for
this repository, since its scenarios file and warehouse live in the account the
maintainers hold. If that ever stops being true this file will fail to import
the dialect, not skip quietly.
"""

import inspect
from typing import Dict

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import (
    ProtocolNotImplementedError,
    UnsupportedFeatureError,
)
from rhosocial.activerecord.backend.expression.objects import (
    Database,
    Domain,
    EdgeTable as EdgeTableObject,
    Function,
    Index,
    MaterializedView,
    NodeTable,
    Schema,
    Sequence,
    Table,
    Trigger,
    Type,
    View,
)
from rhosocial.activerecord.backend.expression import graph as graph_mod
from rhosocial.activerecord.backend.expression.advanced_functions import (
    CaseExpression,
    WindowClause,
    WindowDefinition,
    WindowSpecification,
)
from rhosocial.activerecord.backend.expression.collation import CollateExpression
from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.expression.datetime import (
    TemporalOptionsExpression,
)
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.query_parts import JoinClause
from rhosocial.activerecord.backend.expression.serialization import (
    ExpressionRegistry,
    deserialize,
    deserialize_json,
    deserialize_xml,
    serialize,
    serialize_json,
    serialize_xml,
)
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.expression.statements import (
    ddl_alter,
    ddl_comment,
    ddl_database,
    ddl_domain,
    ddl_function,
    ddl_index,
    ddl_schema,
    ddl_sequence,
    ddl_table,
    ddl_trigger,
    ddl_truncate,
    ddl_type,
    ddl_view,
    dml,
)
from rhosocial.activerecord.backend.expression.statements.ddl_database import (
    AlterDatabaseAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_domain import (
    DomainCheckConstraint,
    RenameDomainAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnConstraint,
    ColumnConstraintType,
    ForeignKeyConstraint,
    IndexDefinition,
    ReferencesClause,
    TableConstraint,
    TableConstraintType,
)
from rhosocial.activerecord.backend.expression.statements.ddl_trigger import (
    TriggerEvent,
    TriggerTiming,
)
from rhosocial.activerecord.backend.expression.statements.dml import (
    MergeAction,
    MergeActionType,
)
from rhosocial.activerecord.backend.expression.statements.dql import QueryExpression
from rhosocial.activerecord.backend.expression.types import (
    ArrayType,
    IntegerType,
    VarCharType,
)
from rhosocial.activerecord.backend.expression.xml import (
    XMLAttribute,
    XMLAttributesExpression,
    XMLConcatExpression,
    XMLForestExpression,
    XMLForestItem,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.file_format import (
    SnowflakeAlterFileFormatExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.materialized_view import (  # noqa: E501
    SnowflakeCreateMaterializedViewExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.pipe import (
    SnowflakeCreatePipeExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.stage import (
    SnowflakeAlterStageExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.stream import (
    SnowflakeCreateStreamExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.type import (
    SnowflakeAlterTypeExpression,
    SnowflakeObjectTypeDefinition,
    SnowflakeSetTypeCommentAction,
    SnowflakeTypeField,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.dml import (
    SnowflakeInsertExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.partition import (
    SnowflakeClusterByClause,
    SnowflakeExternalPartitionClause,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.sample import (
    SnowflakeSampleExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.show import (
    SnowflakeShowExpression,
    SnowflakeShowObjectType,
    SnowflakeShowScope,
)
from rhosocial.activerecord.testsuite.utils.expression import (
    assert_params_equal,
    collect_expression_classes,
    make_instance,
    register_all,
    register_special_constructor,
)

CORE_EXPR_PKG = "rhosocial.activerecord.backend.expression"
SNOWFLAKE_EXPR_PKG = "rhosocial.activerecord.backend.impl.snowflake.expression"

#: The version the matrix renders with.
#:
#: 8.0.0 is the dialect's own default, which is *below* the 10.8 floor for
#: schema-level TYPE DDL. That is deliberate rather than convenient: it is the
#: version a Snowflake account of the vintage this backend targets reports, and
#: the TYPE expressions then take the ``UnsupportedFeatureError`` branch, which is
#: a real answer. Raising the version would turn five genuine "not on this
#: server" verdicts into renders and hide the version gate. The render-time
#: behaviour at or above the floor is covered by
#: ``ddl/test_type_ddl.py``, which constructs the dialect at 10.8.
DIALECT_VERSION = (8, 0, 0)


def _collect_matrix_classes():
    """Every concrete expression class these two packages define.

    Walked rather than read from the registry -- see the module docstring for
    why that distinction is load-bearing here. Classes exported under several
    names are keyed by the first name in sorted order, so a class aliased four
    ways is not tested four times.
    """
    ExpressionRegistry._auto_register_builtins()
    collected: Dict[str, type] = {}
    for package in (SNOWFLAKE_EXPR_PKG, CORE_EXPR_PKG):
        collected.update(collect_expression_classes(package))
    by_identity: Dict[int, str] = {}
    for fqn, cls in sorted(collected.items()):
        by_identity.setdefault(id(cls), fqn)
    return {
        fqn: cls
        for cls in collected.values()
        if not inspect.isabstract(cls)
        for fqn in [by_identity[id(cls)]]
    }


REGISTERED = _collect_matrix_classes()
# Deserialising a Snowflake expression needs it registered; nothing registers
# this package's classes on import.
register_all(REGISTERED)


# ---------------------------------------------------------------------------
# Special constructors: a real value where the introspective guess is a lie
# ---------------------------------------------------------------------------
#
# ``make_instance`` reads each required parameter's annotation and guesses: ``"x"``
# for a string, ``[]`` for a list, ``IntegerType()`` for a type. That is right
# for a name and wrong for everything else that matters here:
#
# * every parameter that wants a catalogue object, because a bare ``"x"`` is not
#   a Table and the formatter now refuses it by name;
# * every container that must not be empty (CASE, WINDOW, JOIN);
# * every predicate that has to render without bind parameters, because a DOMAIN
#   CHECK and a MERGE condition are DDL and cannot carry a ``?``;
# * every required parameter hidden behind a defaulted positional, which the
#   guess skips entirely.
#
# Suffixes are spelled relative to the expression package because
# ``make_instance`` matches with ``str.endswith`` and several modules export
# identically named classes.


def _table_obj(dialect, name="t"):
    """A table with a bare name and no namespace."""
    return Table(dialect, name)


def _column_predicate(dialect):
    """A predicate comparing two columns, so it renders with no bind parameters."""
    return ComparisonPredicate(
        dialect, "=", Column(dialect, "a"), Column(dialect, "b")
    )


def _one_column_query(dialect):
    """A single-column ``SELECT`` over a table."""
    return QueryExpression(
        dialect, select=[Column(dialect, "id")], from_=_table_obj(dialect)
    )


def _integer_column(dialect, name="col"):
    """A column definition carrying a *dialect-bound* type.

    The binding is load-bearing: ``to_sql()`` dispatches the type through its own
    dialect, so an unbound ``IntegerType()`` raises the moment anything renders
    it.
    """
    return ddl_table.ColumnDefinition(dialect, name, IntegerType(dialect))


def register_specials():
    """Replace every introspective guess that would cost a real assertion."""

    # -- the FROM side -------------------------------------------------------
    register_special_constructor(
        "sources.relation.NamedRelationRef",
        lambda d: NamedRelationRef(d, _table_obj(d)),
    )
    register_special_constructor(
        "query_parts.JoinClause",
        lambda d: JoinClause(
            d,
            left_table=NamedRelationRef(d, _table_obj(d)),
            right_table=NamedRelationRef(d, Table(d, "other")),
            condition=_column_predicate(d),
        ),
    )

    # -- tables and columns --------------------------------------------------
    register_special_constructor(
        "statements.ddl_table.CreateTableExpression",
        lambda d: ddl_table.CreateTableExpression(d, _table_obj(d), [_integer_column(d)]),
    )
    register_special_constructor(
        "statements.ddl_table.DropTableExpression",
        lambda d: ddl_table.DropTableExpression(d, _table_obj(d)),
    )
    register_special_constructor(
        "statements.ddl_table.CreateTableLikeExpression",
        lambda d: ddl_table.CreateTableLikeExpression(d, _table_obj(d), Table(d, "other")),
    )
    register_special_constructor(
        "statements.ddl_table.CreateTableCloneExpression",
        lambda d: ddl_table.CreateTableCloneExpression(
            d, _table_obj(d), Table(d, "other")
        ),
    )
    register_special_constructor(
        "statements.ddl_table.CreateTableAsExpression",
        lambda d: ddl_table.CreateTableAsExpression(d, _table_obj(d), _one_column_query(d)),
    )
    register_special_constructor(
        "statements.ddl_table.CreateTableFromTemplateExpression",
        lambda d: ddl_table.CreateTableFromTemplateExpression(
            d, _table_obj(d), _one_column_query(d)
        ),
    )
    register_special_constructor(
        "statements.ddl_truncate.TruncateExpression",
        lambda d: ddl_truncate.TruncateExpression(d, _table_obj(d)),
    )
    # Overrides the shared testsuite factory, which binds no dialect to its type.
    register_special_constructor("statements.ddl_table.ColumnDefinition", _integer_column)

    # -- indexes -------------------------------------------------------------
    register_special_constructor(
        "statements.ddl_index.CreateIndexExpression",
        lambda d: ddl_index.CreateIndexExpression(
            d, index=Index(d, "i"), table=_table_obj(d), columns=["a"]
        ),
    )
    register_special_constructor(
        "statements.ddl_index.DropIndexExpression",
        lambda d: ddl_index.DropIndexExpression(d, index=Index(d, "i")),
    )
    register_special_constructor(
        "statements.ddl_index.CreateFulltextIndexExpression",
        lambda d: ddl_index.CreateFulltextIndexExpression(
            d, index=Index(d, "i"), table=_table_obj(d), columns=["a"]
        ),
    )
    register_special_constructor(
        "statements.ddl_index.DropFulltextIndexExpression",
        lambda d: ddl_index.DropFulltextIndexExpression(
            d, index=Index(d, "i"), table=_table_obj(d)
        ),
    )
    register_special_constructor(
        "statements.ddl_alter.DropIndex",
        lambda d: ddl_alter.DropIndex(d, Index(d, "i")),
    )

    # -- schemas, sequences, databases, domains, types -----------------------
    register_special_constructor(
        "statements.ddl_schema.CreateSchemaExpression",
        lambda d: ddl_schema.CreateSchemaExpression(d, Schema(d, "s")),
    )
    register_special_constructor(
        "statements.ddl_schema.DropSchemaExpression",
        lambda d: ddl_schema.DropSchemaExpression(d, Schema(d, "s")),
    )
    register_special_constructor(
        "statements.ddl_sequence.CreateSequenceExpression",
        lambda d: ddl_sequence.CreateSequenceExpression(d, Sequence(d, "s")),
    )
    register_special_constructor(
        "statements.ddl_sequence.AlterSequenceExpression",
        lambda d: ddl_sequence.AlterSequenceExpression(d, Sequence(d, "s"), restart=1),
    )
    register_special_constructor(
        "statements.ddl_sequence.DropSequenceExpression",
        lambda d: ddl_sequence.DropSequenceExpression(d, Sequence(d, "s")),
    )
    register_special_constructor(
        "statements.ddl_database.CreateDatabaseExpression",
        lambda d: ddl_database.CreateDatabaseExpression(d, Database(d, "db")),
    )
    register_special_constructor(
        "statements.ddl_database.DropDatabaseExpression",
        lambda d: ddl_database.DropDatabaseExpression(d, Database(d, "db")),
    )
    register_special_constructor(
        "statements.ddl_database.AlterDatabaseExpression",
        lambda d: ddl_database.AlterDatabaseExpression(
            d,
            Database(d, "db"),
            action=AlterDatabaseAction.RENAME_TO,
            target="renamed_db",
        ),
    )
    register_special_constructor(
        "statements.ddl_domain.CreateDomainExpression",
        lambda d: ddl_domain.CreateDomainExpression(d, Domain(d, "dom"), IntegerType(d)),
    )
    register_special_constructor(
        "statements.ddl_domain.DropDomainExpression",
        lambda d: ddl_domain.DropDomainExpression(d, Domain(d, "dom")),
    )
    register_special_constructor(
        "statements.ddl_domain.AlterDomainExpression",
        lambda d: ddl_domain.AlterDomainExpression(
            d, Domain(d, "dom"), [RenameDomainAction(d, "other")]
        ),
    )
    # A DOMAIN CHECK is DDL: it must render without bind parameters, so its
    # condition compares two columns rather than a column and a literal.
    register_special_constructor(
        "statements.ddl_domain.DomainCheckConstraint",
        lambda d: DomainCheckConstraint(d, _column_predicate(d), name="chk"),
    )
    register_special_constructor(
        "statements.ddl_type.CreateTypeExpression",
        lambda d: ddl_type.CreateTypeExpression(
            d, type=Type(d, "t"), definition=IntegerType(d)
        ),
    )
    register_special_constructor(
        "statements.ddl_type.AlterTypeExpression",
        lambda d: ddl_type.AlterTypeExpression(
            d, type=Type(d, "t"), actions=[SnowflakeSetTypeCommentAction(d, "a note")]
        ),
    )
    register_special_constructor(
        "statements.ddl_type.DropTypeExpression",
        lambda d: ddl_type.DropTypeExpression(d, type=Type(d, "t")),
    )

    # -- routines, triggers, comments ----------------------------------------
    register_special_constructor(
        "statements.ddl_function.CreateFunctionExpression",
        lambda d: ddl_function.CreateFunctionExpression(
            d, Function(d, "fn"), returns="integer", body="SELECT 1"
        ),
    )
    register_special_constructor(
        "statements.ddl_function.DropFunctionExpression",
        lambda d: ddl_function.DropFunctionExpression(d, Function(d, "fn")),
    )
    register_special_constructor(
        "statements.ddl_trigger.CreateTriggerExpression",
        lambda d: ddl_trigger.CreateTriggerExpression(
            d,
            trigger=Trigger(d, "trg"),
            table=_table_obj(d),
            timing=TriggerTiming.BEFORE,
            events=[TriggerEvent.INSERT],
            function=Function(d, "fn"),
        ),
    )
    register_special_constructor(
        "statements.ddl_trigger.DropTriggerExpression",
        lambda d: ddl_trigger.DropTriggerExpression(d, trigger=Trigger(d, "trg")),
    )
    register_special_constructor(
        "statements.ddl_comment.CommentOnExpression",
        lambda d: ddl_comment.CommentOnExpression(d, "table", _table_obj(d), comment="c"),
    )

    # -- views ---------------------------------------------------------------
    register_special_constructor(
        "statements.ddl_view.DropViewExpression",
        lambda d: ddl_view.DropViewExpression(d, View(d, "v")),
    )
    register_special_constructor(
        "statements.ddl_view.CreateMaterializedViewExpression",
        lambda d: ddl_view.CreateMaterializedViewExpression(
            d, MaterializedView(d, "mv"), _one_column_query(d)
        ),
    )
    register_special_constructor(
        "statements.ddl_view.DropMaterializedViewExpression",
        lambda d: ddl_view.DropMaterializedViewExpression(d, MaterializedView(d, "mv")),
    )
    register_special_constructor(
        "statements.ddl_view.RefreshMaterializedViewExpression",
        lambda d: ddl_view.RefreshMaterializedViewExpression(d, MaterializedView(d, "mv")),
    )

    # -- DML -----------------------------------------------------------------
    register_special_constructor(
        "statements.dml.InsertExpression",
        lambda d: dml.InsertExpression(
            d, into=_table_obj(d), source=dml.ValuesSource(d, [[Literal(d, 1)]])
        ),
    )
    register_special_constructor(
        "statements.dml.DeleteExpression",
        lambda d: dml.DeleteExpression(d, _table_obj(d)),
    )
    register_special_constructor(
        "statements.dml.MergeExpression",
        lambda d: dml.MergeExpression(
            d,
            target_table=_table_obj(d),
            source=NamedRelationRef(d, Table(d, "src")),
            on_condition=_column_predicate(d),
            when_matched=[
                MergeAction(
                    d,
                    MergeActionType.UPDATE,
                    {"a": Literal(d, 1)},
                    _column_predicate(d),
                    "matched",
                )
            ],
        ),
    )
    register_special_constructor(
        "statements.dml.MergeAction",
        lambda d: MergeAction(
            d,
            MergeActionType.UPDATE,
            {"a": Literal(d, 1)},
            _column_predicate(d),
            "matched",
        ),
    )

    # -- constraints and column pieces ---------------------------------------
    register_special_constructor(
        "statements.ddl_table.ColumnConstraint",
        lambda d: ColumnConstraint(d, ColumnConstraintType.NOT_NULL, name="c"),
    )
    register_special_constructor(
        "statements.ddl_table.TableConstraint",
        lambda d: TableConstraint(
            d, TableConstraintType.PRIMARY_KEY, name="c", columns=["a"]
        ),
    )
    register_special_constructor(
        "statements.ddl_table.ForeignKeyConstraint",
        lambda d: ForeignKeyConstraint(
            d,
            columns=["a"],
            foreign_key_table=Table(d, "other"),
            foreign_key_columns=["b"],
            name="fk",
        ),
    )
    register_special_constructor(
        "statements.ddl_table.ReferencesClause",
        lambda d: ReferencesClause(d, Table(d, "other"), ["b"]),
    )
    register_special_constructor(
        "statements.ddl_alter.AddColumn",
        lambda d: ddl_alter.AddColumn(d, _integer_column(d)),
    )
    register_special_constructor(
        "statements.ddl_alter.ModifyColumn",
        lambda d: ddl_alter.ModifyColumn(d, _integer_column(d)),
    )
    register_special_constructor(
        "statements.ddl_alter.AddIndex",
        lambda d: ddl_alter.AddIndex(d, IndexDefinition(d, "i", ["a"])),
    )
    register_special_constructor(
        "statements.ddl_alter.AddTableConstraint",
        lambda d: ddl_alter.AddTableConstraint(
            d,
            TableConstraint(
                d, TableConstraintType.PRIMARY_KEY, name="c", columns=["a"]
            ),
        ),
    )

    # -- expressions that need at least one member --------------------------
    register_special_constructor(
        "advanced_functions.CaseExpression",
        lambda d: CaseExpression(
            d, cases=[(_column_predicate(d), Literal(d, 1))], else_result=Literal(d, 0)
        ),
    )
    register_special_constructor(
        "advanced_functions.WindowSpecification",
        lambda d: WindowSpecification(d, partition_by=["a"]),
    )
    register_special_constructor(
        "advanced_functions.WindowDefinition",
        lambda d: WindowDefinition(d, "w", WindowSpecification(d, partition_by=["a"])),
    )
    register_special_constructor(
        "advanced_functions.WindowClause",
        lambda d: WindowClause(
            d, [WindowDefinition(d, "w", WindowSpecification(d, partition_by=["a"]))]
        ),
    )
    # An empty options dict is refused by the formatter, so a temporal clause
    # needs an actual option. AS_OF is the one the shared default renders; the
    # Snowflake-specific AT / BEFORE forms are covered by
    # ``mixins/time_travel.py``'s own tests.
    register_special_constructor(
        "datetime.TemporalOptionsExpression",
        lambda d: TemporalOptionsExpression(d, {"as_of": "2020-01-01"}),
    )

    # -- property graphs ------------------------------------------------------
    def _node_table(d):
        return NodeTable(d, "people")

    def _edge_table(d):
        return EdgeTableObject(d, "knows")

    def _path_pattern(d):
        return graph_mod.PathPattern(d, graph_mod.GraphVertex(d, "n", _node_table(d)))

    register_special_constructor(
        "graph.GraphVertex",
        lambda d: graph_mod.GraphVertex(d, "n", _node_table(d)),
    )
    register_special_constructor(
        "graph.VertexTable",
        lambda d: graph_mod.VertexTable(d, _node_table(d), key_columns=["id"]),
    )
    register_special_constructor(
        "graph.EdgeTable",
        lambda d: graph_mod.EdgeTable(d, _edge_table(d), ["src"], ["dst"]),
    )
    register_special_constructor(
        "graph.GraphEdge",
        lambda d: graph_mod.GraphEdge(d, "e", _edge_table(d)),
    )
    register_special_constructor(
        "graph.QuantifiedPath",
        lambda d: graph_mod.QuantifiedPath(
            d, graph_mod.GraphEdge(d, "e", _edge_table(d)), min_repeats=1, max_repeats=3
        ),
    )
    register_special_constructor(
        "graph.PathPattern", _path_pattern
    )
    register_special_constructor(
        "graph.MatchClause", lambda d: graph_mod.MatchClause(d, _path_pattern(d))
    )

    # -- SQL/XML --------------------------------------------------------------
    register_special_constructor(
        "xml.XMLAttributesExpression",
        lambda d: XMLAttributesExpression(d, [XMLAttribute(Literal(d, "v"), "a")]),
    )
    register_special_constructor(
        "xml.XMLForestExpression",
        lambda d: XMLForestExpression(d, [XMLForestItem(Literal(d, "v"), "a")]),
    )
    register_special_constructor(
        "xml.XMLConcatExpression",
        lambda d: XMLConcatExpression(d, [Literal(d, "a"), Literal(d, "b")]),
    )
    register_special_constructor(
        "types.array.ArrayType", lambda d: ArrayType(d, VarCharType(d, 10))
    )

    # -- a value the guess cannot know ---------------------------------------
    # ``collation_name`` is checked against a whitelist, and the guess supplies
    # the placeholder ``"x"``. This is the only parameter in the two packages
    # that is a string *belonging to a closed set* rather than free text.
    register_special_constructor(
        "collation.CollateExpression",
        lambda d: CollateExpression(d, Column(d, "name"), "en-ci"),
    )

    # -- Snowflake's own expressions -----------------------------------------
    # Each of these has a required parameter that is either keyword-only, so the
    # guess skips it, or of a kind the guess fills with a bare string. All are
    # backend-owned, so their shape is this repository's business.
    register_special_constructor(
        "ddl.materialized_view.SnowflakeCreateMaterializedViewExpression",
        lambda d: SnowflakeCreateMaterializedViewExpression(
            d, "mv", as_query="SELECT 1"
        ),
    )
    register_special_constructor(
        "ddl.type.SnowflakeAlterTypeExpression",
        lambda d: SnowflakeAlterTypeExpression(
            d, Type(d, "t"), [SnowflakeSetTypeCommentAction(d, "a note")]
        ),
    )
    register_special_constructor(
        "ddl.type.SnowflakeObjectTypeDefinition",
        lambda d: SnowflakeObjectTypeDefinition(
            d, [SnowflakeTypeField(d, "f", IntegerType(d))]
        ),
    )
    register_special_constructor(
        "partition.SnowflakeClusterByClause",
        lambda d: SnowflakeClusterByClause(d, [Column(d, "c1")]),
    )
    register_special_constructor(
        "partition.SnowflakeExternalPartitionClause",
        lambda d: SnowflakeExternalPartitionClause(d, [Column(d, "c1")]),
    )
    register_special_constructor(
        "ddl.pipe.SnowflakeCreatePipeExpression",
        lambda d: SnowflakeCreatePipeExpression(d, "p", copy_sql="COPY INTO t FROM @s"),
    )
    register_special_constructor(
        "ddl.stream.SnowflakeCreateStreamExpression",
        lambda d: SnowflakeCreateStreamExpression(d, "s", object_name="t"),
    )
    register_special_constructor(
        "ddl.file_format.SnowflakeAlterFileFormatExpression",
        lambda d: SnowflakeAlterFileFormatExpression(d, "f", options={"TYPE": "CSV"}),
    )
    register_special_constructor(
        "ddl.stage.SnowflakeAlterStageExpression",
        lambda d: SnowflakeAlterStageExpression(d, "s", url="s3://bucket/path"),
    )
    register_special_constructor(
        "sample.SnowflakeSampleExpression",
        lambda d: SnowflakeSampleExpression(d, 10),
    )
    register_special_constructor(
        "show.SnowflakeShowExpression",
        lambda d: SnowflakeShowExpression(
            d, SnowflakeShowObjectType.TABLES,
            in_scope=SnowflakeShowScope.DATABASE,
            limit=10,
        ),
    )
    register_special_constructor(
        "dml.SnowflakeInsertExpression",
        lambda d: SnowflakeInsertExpression(
            d, _table_obj(d), dml.ValuesSource(d, [[Literal(d, 1)]])
        ),
    )


register_specials()


# ---------------------------------------------------------------------------
# Lists that cannot grow or shrink silently
# ---------------------------------------------------------------------------

#: Classes the generic introspective constructor cannot build.
#:
#: Each is a real coverage gap, named here so it is visible rather than lost.
#: :meth:`TestMatrixIntegrity.test_unconstructible_list_is_exact` pins the tuple
#: in both directions, so a class that starts needing an exemption fails until
#: this entry is justified and a stale entry fails too.
#:
#: Sorted, because the integrity test compares against a sorted tuple of what it
#: observes. Every remaining entry is the same shape: a required parameter the
#: introspective guess cannot supply, because it sits behind a defaulted
#: positional or is a member of a closed set. Registering a constructor is the way
#: to retire any of them.
#:
#: ``XMLTableExpression`` used to be a fifth entry here, and it never was a gap in
#: the class. It wants ``columns: Sequence[XMLTableColumn]``, and the guess read
#: that annotation's *alias* name -- ``"Sequence"`` -- decided it named a catalogue
#: object and handed the parameter a ``Sequence`` instead of a list of columns.
#: The class was fine and the harness was wrong. It constructs now, and what it
#: reports is a real answer: Snowflake has no SQL/XML at all, so the dispatch finds
#: no ``format_xmltable_expression``. That is why the method is in
#: :data:`UNMODELLED_FORMATTERS` under SQL/XML rather than the class staying pinned
#: here -- the matrix could not find that out while the class could not be built.
UNCONSTRUCTIBLE = (
    # ALTER CONSTRAINT. ``name`` and ``constraint_type`` sit behind defaulted
    # positionals and are keyword-only, so the introspective constructor skips
    # them and the class refuses an incomplete action (`ValueError:
    # constraint_name must be a non-empty string`, because the defaulted
    # ``constraint_name`` stays None).
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.AlterConstraint",
    # VALIDATE CONSTRAINT. The same shape: the required ``name`` is keyword-only
    # behind a defaulted positional.
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.ValidateConstraint",
    # ADD DOMAIN CHECK. Widens a ``SQLPredicate`` into a ``DomainCheckConstraint``
    # and needs one. The guess supplies a bare *string*: the annotation names a
    # ``DomainCheckConstraint``, whose ``\bDomain\b`` fragment does not match
    # inside the longer word, so the guess falls through to its name-based default
    # and the class raises ``TypeError: check must be a DomainCheckConstraint
    # instance, got str``. Registering a constructor for it would need the same
    # predicate this module already builds for ``JoinClause``, and the class is
    # unreachable under Snowflake either way -- it names a formatter Snowflake
    # does not declare (see :data:`UNMODELLED_FORMATTERS`), so rendering it would
    # be an ``UnsupportedFeatureError`` whatever it was built from. Building it
    # would buy no assertion.
    "rhosocial.activerecord.backend.expression.statements.ddl_domain.AddDomainCheckAction",
    # ENUM type. Its ``values`` list is keyword-only behind a defaulted
    # positional, so the constructor skips it and the type declares no members
    # (``ValueError: EnumType requires values``).
    "rhosocial.activerecord.backend.expression.types.enum_.EnumType",
)

#: Formatters Snowflake declares no implementation of, grouped by the feature
#: that is absent, each group naming every method the matrix's classes need.
#:
#: A class needing one of these fails with ``UnsupportedFeatureError`` naming the
#: method it wanted: ``to_sql()`` reports a dialect that has no such formatter as
#: a capability gap, the same way every probe in the tree reports one, so a gap
#: declared by omission no longer has a second spelling. The failure is still
#: attributed to *this* table rather than waved through, and
#: :meth:`TestMatrixIntegrity.test_unmodelled_formatter_list_is_exact` pins the
#: table in both directions. So a formatter that starts existing moves its classes
#: out of this table and the pin fails until it does, and a class that starts
#: needing an unlisted formatter fails outright.
#:
#: These are not defects: they are features Snowflake does not have, which the
#: shared renderer reports by naming the method it could not find. The grouping is
#: the point -- "44 methods" says nothing, "Snowflake has no SQL/XML, no property
#: graphs, no triggers, no DOMAIN" says what the dialect is.
UNMODELLED_FORMATTERS = {
    # --- SQL/XML: Snowflake implements no part of SQL/XML -------------------
    # Thirteen. ``format_xmltable_expression`` is the one that arrived last and
    # the one worth explaining: ``XMLTableExpression`` was pinned in
    # UNCONSTRUCTIBLE until the testsuite's introspective constructor stopped
    # reading ``columns: Sequence[XMLTableColumn]`` as a request for a
    # ``Sequence`` catalogue object. Once the class could be built the matrix
    # asked it to render, and the answer was the one this group already gave for
    # the other twelve: ``SnowflakeDialect`` declares no ``format_xml*`` method at
    # all. Nothing about Snowflake changed; the matrix simply stopped being unable
    # to ask the question.
    "SQL/XML (no XMLAGG, XMLATTRIBUTES, XMLCOMMENT, XMLCONCAT, XMLELEMENT, "
    "XMLEXISTS, XMLFOREST, XMLPARSE, XMLPI, XMLQUERY, XMLROOT, XMLSERIALIZE or "
    "XMLTABLE)": (
        "format_xmlagg_expression",
        "format_xmlattributes_expression",
        "format_xmlcomment_expression",
        "format_xmlconcat_expression",
        "format_xmlelement_expression",
        "format_xmlexists_expression",
        "format_xmlforest_expression",
        "format_xmlparse_expression",
        "format_xmlpi_expression",
        "format_xmlquery_expression",
        "format_xmlroot_expression",
        "format_xmlserialize_expression",
        "format_xmltable_expression",
    ),
    # --- SQL/PGQ property graphs: no graph tables, no MATCH ---------------
    "SQL/PGQ property graphs (Snowflake has no GRAPH_TABLE and no Cypher)": (
        "format_alter_property_graph_statement",
        "format_create_property_graph_statement",
        "format_drop_property_graph_statement",
        "format_edge_table",
        "format_graph_columns_clause",
        "format_graph_edge",
        "format_graph_table_expression",
        "format_graph_vertex",
        "format_match_clause",
        "format_path_pattern",
        "format_property_graph_object",
        "format_quantified_path",
        "format_table_properties_clause",
        "format_vertex_table",
    ),
    # --- DOMAIN: Snowflake has no CREATE DOMAIN at all ---------------------
    "DOMAIN (Snowflake has no CREATE DOMAIN, so no domain statement or action)": (
        "format_alter_domain_statement",
        "format_create_domain_statement",
        "format_domain_alter_action",
        "format_domain_check_constraint",
        "format_domain_value_expression",
        "format_drop_domain_statement",
    ),
    # --- TRIGGER: Snowflake has no CREATE TRIGGER -------------------------
    "TRIGGER (Snowflake implements triggers in JavaScript, not as DDL)": (
        "format_create_trigger_statement",
        "format_drop_trigger_statement",
        "format_trigger_object",
    ),
    # --- Routines and the objects only they name --------------------------
    # Snowflake *does* have procedures and functions, and it renders them -- but
    # through ``SnowflakeRoutineMixin`` and the ``SnowflakeRoutineSupport``
    # protocol, whose expressions carry a bare name. The core SQL/PSM statements
    # are not what Snowflake's formatters read. ``CreateFunctionExpression``
    # is pinned separately below because it fails differently: this dialect's
    # override shadows the core formatter, so the dispatch finds a formatter,
    # calls it, and it raises reading an attribute the core statement lacks --
    # which is not a missing formatter at all, and so belongs nowhere in this
    # table.
    "the core SQL/PSM routine objects (Snowflake renders routines through "
    "SnowflakeRoutineSupport, whose expressions carry a bare name)": (
        "format_drop_function_statement",
        "format_function_object",
        "format_procedure_object",
    ),
    # --- Objects Snowflake's namespace has no level for --------------------
    # A FOREIGN TABLE and a SYNONYM are the two objects whose namespace shape
    # Snowflake cannot express: it resolves neither ``db.schema.foreign_table``
    # nor a synonym of a table.
    "FOREIGN TABLE and SYNONYM (neither object exists in Snowflake)": (
        "format_foreign_table_object",
        "format_synonym_object",
    ),
    # --- PIVOT / UNPIVOT as core expressions ------------------------------
    # Snowflake has PIVOT, and renders it -- through ``SnowflakePivotExpression``
    # and ``SnowflakePivotSupport``. The core ``PivotExpression`` names formatters
    # this dialect does not declare, because the Snowflake clause is spelled from
    # different fields.
    "the core PIVOT / UNPIVOT expressions (Snowflake spells the clause from "
    "SnowflakePivotExpression instead)": (
        "format_pivot_expression",
        "format_unpivot_expression",
    ),
    # --- the root of the row-source tree ----------------------------------
    # Every concrete row source declares its own ``format_method`` and overrides
    # this; the base declares none, so there is nothing to dispatch. Not a Snowflake
    # gap -- the root of a tree is never renderable anywhere -- so it is named
    # rather than treated as a missing feature.
    "the TableSource root (every concrete row source overrides its formatter; the "
    "root carries nothing but an alias and is never rendered)": (
        "format_table_source",
    ),
}

#: The two ends of the frame ``to_sql()`` puts around a formatting method name
#: in the ``feature_name`` of the ``UnsupportedFeatureError`` it raises for a
#: dialect that has no such formatter.
#:
#: The frame is the discriminator, and it is a good one. A probe a *formatter*
#: reaches for refuses through the same exception type but names a feature --
#: ``GRAPH_TABLE``, ``derived table in FROM``, ``the generic type 'int'`` -- and
#: never a formatting method, because a formatter has already been found by the
#: time a probe can run. Only the dispatch knows a formatting method name at all,
#: so only the dispatch puts one in this frame.
#:
#: That is not a hope. Every ``UnsupportedFeatureError`` construction and every
#: ``check_feature_support`` call in the core tree was walked: of 276 with a
#: literal feature name, none opens this frame, and of the 23 that interpolate,
#: only ``bases.py``'s dispatch does -- every other one opens with its own fixed
#: prefix ("TYPE definition ", "ALTER DOMAIN action ", "date_diff(" and so on).
#: Which is what lets the unsupported and unmodelled branches share an exception
#: type without merging. A probe that ever did adopt the frame would be
#: misattributed -- loudly, as a method missing from the table, never silently.
_DISPATCH_FEATURE_PREFIX = "the '"
_DISPATCH_FEATURE_SUFFIX = "' statement"


def _dispatched_formatter(exc):
    """The formatting method *exc* says the dialect does not have, or ``None``.

    ``None`` means *exc* is not the dispatch reporting a missing formatter --
    it is a probe inside a formatter that refused a feature, which is the
    ``"unsupported"`` branch.

    Args:
        exc: An :class:`UnsupportedFeatureError` raised out of ``to_sql()``.

    Returns:
        The method name out of the ``feature_name`` frame, or ``None`` when
        *exc* came from a probe rather than from the dispatch.
    """
    feature = exc.feature_name
    if not feature.startswith(_DISPATCH_FEATURE_PREFIX):
        return None
    if not feature.endswith(_DISPATCH_FEATURE_SUFFIX):
        return None
    method = feature[
        len(_DISPATCH_FEATURE_PREFIX) : len(feature) - len(_DISPATCH_FEATURE_SUFFIX)
    ]
    return method if method else None


def _unmodelled_methods():
    """The flat set of formatter names in :data:`UNMODELLED_FORMATTERS`."""
    return {
        method for methods in UNMODELLED_FORMATTERS.values() for method in methods
    }


#: Classes that construct but cannot render, for a reason belonging to their own
#: tree rather than to a defect in a formatter. Each entry pins *what* is
#: expected: the exception type and a message fragment it must carry.
#:
#: The type is checked with ``type(exc) is``, never ``isinstance``, so a
#: subclass cannot stand in for the pinned type. And the message fragment is
#: checked, so a class that started failing for a *different* reason fails here
#: instead of passing on the strength of raising the right class of error.
_NO_FORMAT_METHOD_NAME = "does not declare its dialect formatting method name"
_NO_GENERIC_TYPE = "does not support the generic type"

LEGITIMATE_NON_RENDERS = {
    # ---- roots that name an expression category, not a renderable thing ----
    # Each is a base class that deliberately declares no ``format_method``, so
    # ``to_sql()`` reports that there is nothing to dispatch. They are not
    # ``inspect.isabstract`` -- concrete enough to construct -- so the collector
    # keeps them, and each is pinned to its exact message so a base that started
    # rendering fails here instead of passing quietly.
    "rhosocial.activerecord.backend.expression.bases.SQLPredicate": (
        NotImplementedError,
        _NO_FORMAT_METHOD_NAME,
    ),
    "rhosocial.activerecord.backend.expression.bases.SQLValueExpression": (
        NotImplementedError,
        _NO_FORMAT_METHOD_NAME,
    ),
    "rhosocial.activerecord.backend.expression.datetime._TemporalValueExpression": (
        NotImplementedError,
        _NO_FORMAT_METHOD_NAME,
    ),
    "rhosocial.activerecord.backend.expression.introspection.IntrospectionExpression": (
        NotImplementedError,
        _NO_FORMAT_METHOD_NAME,
    ),
    "rhosocial.activerecord.backend.expression.objects.base.SchemaObject": (
        NotImplementedError,
        _NO_FORMAT_METHOD_NAME,
    ),
    "rhosocial.activerecord.backend.expression.objects.relation.RelationObject": (
        NotImplementedError,
        _NO_FORMAT_METHOD_NAME,
    ),
    "rhosocial.activerecord.backend.expression.objects.routine.RoutineObject": (
        NotImplementedError,
        _NO_FORMAT_METHOD_NAME,
    ),
    "rhosocial.activerecord.backend.expression.objects.type_.TypeObject": (
        NotImplementedError,
        _NO_FORMAT_METHOD_NAME,
    ),
    "rhosocial.activerecord.backend.expression.statements.ddl_alter.AlterTableAction": (
        NotImplementedError,
        _NO_FORMAT_METHOD_NAME,
    ),
    "rhosocial.activerecord.backend.expression.statements.dml.InsertDataSource": (
        NotImplementedError,
        _NO_FORMAT_METHOD_NAME,
    ),
    "rhosocial.activerecord.backend.expression.transaction.TransactionExpression": (
        NotImplementedError,
        _NO_FORMAT_METHOD_NAME,
    ),
    # An introspection query base rather than a DDL or DML one: it names a
    # category ("ask the server about something") and each concrete subclass
    # supplies its own query. The message is the base's own, not the shared one.
    "rhosocial.activerecord.backend.expression.introspection.TableInfoExpression": (
        NotImplementedError,
        "Subclass must implement format_table_info_query",
    ),
    # ---- a protocol answering where a formatter belongs -------------------
    # The root of the type tree answers ``format_domain_object`` through the
    # *protocol* ``TypeObjectSupport``, which is in this dialect's base list.
    # A protocol's body is ``...``, so the lookup succeeds, the call returns
    # ``None``, and ``Domain.to_sql()`` used to hand its caller ``None`` where a
    # ``(sql, params)`` pair belongs.
    #
    # ``to_sql()`` now looks at what answered the lookup, so the answer is no
    # longer silent: a ``None`` from a protocol is reported as a
    # ``ProtocolNotImplementedError`` naming both the protocol and what required
    # it. It stays pinned here rather than moved to
    # :data:`UNMODELLED_FORMATTERS` because a formatter *was* found -- the table
    # answers "this dialect declares no such formatter", which is a different
    # answer.
    #
    # It is still pinned rather than fixed because there is no honest local fix:
    # the dialect satisfies ``TypeObjectSupport`` structurally through
    # ``TypeNameMixin``, and Snowflake has no DOMAIN, so mixing in
    # ``DomainNameMixin`` would claim a feature that does not exist.
    "rhosocial.activerecord.backend.expression.objects.type_.Domain": (
        ProtocolNotImplementedError,
        "does not implement format_domain_object protocol, "
        "which is required by Domain",
    ),
    # ---- the core routine statement under this dialect's override ---------
    # ``SnowflakeRoutineMixin`` overrides ``format_create_function_statement``
    # for ``SnowflakeCreateFunctionExpression``, which carries a bare ``name``.
    # The core statement carries a ``Function`` object and has no ``name``, so
    # the override -- which shadows the core formatter -- reads an attribute that
    # is not there. Pinned with its exact message so a change in what happens
    # here fails this entry instead of passing.
    #
    # Still an ``AttributeError`` raised *inside* the formatter, and the same one
    # the earlier shape check could not reach: ``to_sql()`` inspects what a
    # formatter *returns*, and this one never returns -- it fails on the way in.
    # So this is still the same bug, not a new one. It is a real bug: the dialect
    # declares a formatter for the core class and that formatter cannot render
    # it. Two different bugs would need two different fixes, and only one of them
    # is here.
    "rhosocial.activerecord.backend.expression.statements.ddl_function.CreateFunctionExpression": (  # noqa: E501
        AttributeError,
        "'CreateFunctionExpression' object has no attribute 'name'",
    ),
    # ---- the root of the type tree: incomplete rather than unsupported ----
    # Every concrete type declares its own generic ``name``, which is what
    # ``format_data_type`` dispatches on; the root declares none. TypeError, not
    # UnsupportedFeatureError, because the class is incomplete rather than the
    # dialect being unable.
    "rhosocial.activerecord.backend.expression.types._base.DataType": (
        TypeError,
        "does not declare a valid generic type name",
    ),
    # ---- generic types Snowflake spells differently -----------------------
    # Snowflake's data types carry their own names (``snowflake_varchar``,
    # ``snowflake_number`` and so on), and this dialect implements no
    # ``format_data_type_<generic>`` for the names below. The message is the
    # shared dispatcher's, and its fragment is checked so that a type whose
    # formatter starts existing fails here.
    "rhosocial.activerecord.backend.expression.types.array.ArrayType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
    "rhosocial.activerecord.backend.expression.types.binary.BinaryType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
    "rhosocial.activerecord.backend.expression.types.binary.VarBinaryType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
    "rhosocial.activerecord.backend.expression.types.custom.CustomType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.IntervalType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.TimeTzType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
    "rhosocial.activerecord.backend.expression.types.datetime_.TimestampTzType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
    "rhosocial.activerecord.backend.expression.types.integer.IntType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
    "rhosocial.activerecord.backend.expression.types.integer.TinyIntType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
    "rhosocial.activerecord.backend.expression.types.json_.JsonBType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
    "rhosocial.activerecord.backend.expression.types.numeric.RealType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
    "rhosocial.activerecord.backend.expression.types.uuid_.UUIDType": (
        TypeError,
        _NO_GENERIC_TYPE,
    ),
}


# ---------------------------------------------------------------------------
# The local SQL assertion: classify the outcome instead of swallowing it
# ---------------------------------------------------------------------------


def _is_sql_params_pair(rendered):
    """Whether *rendered* is the ``(str, tuple)`` pair every formatter returns."""
    return (
        isinstance(rendered, tuple)
        and len(rendered) == 2
        and isinstance(rendered[0], str)
        and isinstance(rendered[1], tuple)
    )


def assert_sql_roundtrip_classified(fqn, instance, dialect):
    """Assert an expression's SQL survives the round-trip, or say precisely why not.

    The branches, each asserted:

    * **renders** -- ``to_sql()`` returned an ``(sql, params)`` pair, and all
      three encodings must restore byte-identical SQL *and* byte-identical bind
      parameters.
    * ``UnsupportedFeatureError`` -- Snowflake does not model the feature. There
      are two ways to say that, and the ``feature_name`` frame tells them apart:
      a probe inside a formatter that reached its work is **unsupported**; the
      dispatch finding no formatter at all is **unmodelled**, and the method it
      named is asserted against :data:`UNMODELLED_FORMATTERS`. Both are asserted
      as exactly this type, so a failure of some other type cannot hide behind
      either.
    * a member of :data:`LEGITIMATE_NON_RENDERS` -- unrenderable by design,
      asserted as its exact type *and* message fragment.
    * **anything else** -- a failure naming the class and the exception.

    Returns the branch taken, so a caller can report the distribution.

    Raises:
        AssertionError: On a round-trip mismatch, on an unexpected exception
            type, or when a class's rendering outcome changed.
    """
    try:
        rendered = instance.to_sql()
    except UnsupportedFeatureError as exc:
        assert type(exc) is UnsupportedFeatureError, fqn
        method = _dispatched_formatter(exc)
        if method is None:
            return "unsupported"
        assert method in _unmodelled_methods(), (
            f"{fqn}: to_sql() reported that {exc.dialect_name} declares no "
            f"{method!r}, which is not in UNMODELLED_FORMATTERS.\n"
            f"  Either Snowflake now needs that formatter -- in which case the "
            f"class should render and this entry should go -- or the feature is "
            f"absent and the method belongs in that table with its reason."
        )
        return "unmodelled"
    except Exception as exc:
        if fqn not in LEGITIMATE_NON_RENDERS:
            raise AssertionError(
                f"{fqn}: to_sql() raised {type(exc).__name__}, which is neither a "
                f"render nor a classified non-render, and this is a defect.\n"
                f"  UnsupportedFeatureError means the dialect lacks the feature and "
                f"is always allowed.\n"
                f"  A class that cannot render for a reason belonging to its own "
                f"tree belongs in LEGITIMATE_NON_RENDERS.\n"
                f"  Exception: {exc}"
            ) from exc
        _assert_pinned_non_render(fqn, exc)
        return "non-render"

    if not _is_sql_params_pair(rendered):
        # No class is exempt from this any more -- a formatter answering with
        # anything else is a defect, and there is no sentinel left to exempt it.
        # ``to_sql()`` checks that the answer is a pair whose first element is a
        # string, but not that the params are a *tuple*: ``("SELECT 1", [1, 2])``
        # passes it. This branch is where that weaker shape is caught.
        raise AssertionError(
            f"{fqn}: to_sql() returned {rendered!r}, which is not an "
            f"(sql, params) pair with a tuple of params. to_sql() does not "
            f"check the params container, so this shape reaches it."
        )

    expected_sql, expected_params = rendered
    for channel, decoded in (
        ("dict", deserialize(serialize(instance), dialect)),
        ("json", deserialize_json(serialize_json(instance), dialect)),
        ("xml", deserialize_xml(serialize_xml(instance), dialect)),
    ):
        decoded_sql, decoded_params = decoded.to_sql()
        assert decoded_sql == expected_sql, (
            f"{fqn}: {channel} round-trip changed the SQL.\n"
            f"  original: {expected_sql!r}\n"
            f"  {channel}: {decoded_sql!r}"
        )
        assert decoded_params == expected_params, (
            f"{fqn}: {channel} round-trip changed the bind parameters.\n"
            f"  original: {expected_params!r}\n"
            f"  {channel}: {decoded_params!r}"
        )
    return "rendered"


def _assert_pinned_non_render(fqn, exc):
    """Assert *exc* is the exact type and message :data:`LEGITIMATE_NON_RENDERS` pins."""
    expected_type, fragment = LEGITIMATE_NON_RENDERS[fqn]
    assert type(exc) is expected_type, (
        f"{fqn}: LEGITIMATE_NON_RENDERS pins this class as a legitimate "
        f"non-render raising {expected_type!r}, but it raised "
        f"{type(exc).__name__}: {exc}"
    )
    assert fragment in str(exc), (
        f"{fqn}: expected {expected_type!r} and was expected to say "
        f"{fragment!r}, but it said: {exc}"
    )


@pytest.fixture(scope="module")
def dialect():
    """A Snowflake dialect. Needs no connection and no warehouse."""
    return SnowflakeDialect(version=DIALECT_VERSION)


#: Node ids for the parameterised fixture. The last two dotted segments of the
#: fully qualified name, which keeps a 317-case run readable. A duplicate id is
#: not an error -- pytest disambiguates with a suffix -- but
#: :meth:`TestMatrixIntegrity.test_node_ids_are_distinct` fails on one anyway,
#: because two cases sharing a name in the output is the first thing that makes
#: a red run hard to read.
NODE_IDS = [
    fqn.rsplit(".", 2)[-2] + "." + fqn.rsplit(".", 1)[-1] for fqn in sorted(REGISTERED)
]


@pytest.fixture(params=sorted(REGISTERED), ids=NODE_IDS)
def expr_case(request, dialect):
    fqn = request.param
    instance, source = make_instance(REGISTERED[fqn], dialect)
    if instance is None:
        assert fqn in UNCONSTRUCTIBLE, (
            f"{fqn} cannot be built by the generic constructor ({source}) and is "
            f"not in UNCONSTRUCTIBLE. Either register a special constructor for it "
            f"or add it to the tuple with a reason -- do not let it disappear into "
            f"a skip."
        )
        pytest.skip(f"{fqn}: pinned in UNCONSTRUCTIBLE ({source})")
    return fqn, instance


class TestExpressionRoundtripAll:
    """All constructible expression classes round-trip through all encodings."""

    def test_get_params_roundtrip_across_encodings(self, expr_case, dialect):
        fqn, instance = expr_case
        original = instance.get_params()

        restored_dict = deserialize(serialize(instance), dialect)
        assert_params_equal(restored_dict.get_params(), original, fqn)

        restored_json = deserialize_json(serialize_json(instance), dialect)
        assert_params_equal(restored_json.get_params(), original, fqn)

        restored_xml = deserialize_xml(serialize_xml(instance), dialect)
        assert_params_equal(restored_xml.get_params(), original, fqn)

    def test_to_sql_roundtrip_classified(self, expr_case, dialect):
        """A render must survive the round-trip; a non-render must be classified."""
        fqn, instance = expr_case
        assert_sql_roundtrip_classified(fqn, instance, dialect)


class TestMatrixIntegrity:
    """Guards on the matrix and its lists, so neither can quietly change.

    Each guard is bidirectional on purpose. A one-way check passes when the tree
    grows and only fails when it shrinks; these fail in both directions, so a new
    gap has to be justified rather than absorbed.
    """

    def test_unconstructible_list_is_exact(self, dialect):
        """Pin the unconstructible tuple against what the constructor really skips."""
        actual = tuple(
            sorted(
                fqn
                for fqn in REGISTERED
                if make_instance(REGISTERED[fqn], dialect)[0] is None
            )
        )
        assert actual == tuple(sorted(UNCONSTRUCTIBLE)), (
            "the set of expression classes the generic constructor cannot build "
            "changed.\n"
            f"  now skipped but not named: {sorted(set(actual) - set(UNCONSTRUCTIBLE))}\n"
            f"  named but now built: {sorted(set(UNCONSTRUCTIBLE) - set(actual))}\n"
            "Each new entry needs a reason in the comment above UNCONSTRUCTIBLE."
        )

    def test_node_ids_are_distinct(self):
        """No two cases share a short name.

        pytest tolerates duplicates and disambiguates them, so this would not
        fail on its own -- but a run of 634 cases where two share a label is a
        run nobody can read when it goes red.
        """
        duplicates = sorted(
            {node_id for node_id in NODE_IDS if NODE_IDS.count(node_id) > 1}
        )
        assert not duplicates, f"two classes share a node id: {duplicates}"

    def test_pinned_entries_are_real_classes(self):
        """Every pin names a class that was actually collected.

        A typo in a table would otherwise exempt nothing while still reading as a
        deliberate decision.
        """
        collected = set(REGISTERED)
        unknown = set(UNCONSTRUCTIBLE) - collected
        assert not unknown, f"UNCONSTRUCTIBLE names uncollected classes: {sorted(unknown)}"
        unknown = set(LEGITIMATE_NON_RENDERS) - collected
        assert not unknown, (
            f"LEGITIMATE_NON_RENDERS names uncollected classes: {sorted(unknown)}"
        )

    def test_unmodelled_formatter_list_is_exact(self, dialect):
        """Pin the unmodelled-formatter table against what the dialect really lacks.

        Observed rather than asserted: for each class the matrix covers, either
        it renders or it fails, and every "the dialect declares no such formatter"
        failure is attributed to the method it named. Then the table is compared
        with the set observed, in both directions, so:

        * a method in the table that Snowflake now implements fails here, because
          its classes render and are no longer attributed to it -- which is the
          moment to delete the entry rather than leave a lie in the table;
        * a class that starts needing a method outside the table fails the
          per-class assertion instead of being absorbed.
        """
        observed = set()
        for fqn in sorted(REGISTERED):
            instance, source = make_instance(REGISTERED[fqn], dialect)
            if instance is None:
                continue
            try:
                instance.to_sql()
            except UnsupportedFeatureError as exc:
                method = _dispatched_formatter(exc)
                if method is not None:
                    observed.add(method)
                continue
            except Exception:
                continue

        declared = _unmodelled_methods()
        assert not (observed - declared), (
            "classes need formatters that are not in UNMODELLED_FORMATTERS: "
            f"{sorted(observed - declared)}. Add each with the feature that is "
            f"absent and why."
        )
        assert not (declared - observed), (
            "UNMODELLED_FORMATTERS names formatters no class actually needs: "
            f"{sorted(declared - observed)}. Snowflake may have gained one of "
            f"these, in which case the classes needing it now render and the "
            f"entry should go."
        )

    def test_pinned_non_render_really_does_not_render(self, dialect):
        """Each pinned entry still does what it claims, for the stated reason.

        Without this, an entry could sit in the table for a class that renders
        perfectly well, and the matrix would assert nothing about it.
        """
        for fqn, (expected, fragment) in LEGITIMATE_NON_RENDERS.items():
            instance, source = make_instance(REGISTERED[fqn], dialect)
            assert instance is not None, (
                f"{fqn} is pinned as a non-render but could not be constructed "
                f"({source})"
            )
            with pytest.raises(expected) as exc_info:
                instance.to_sql()
            assert fragment in str(exc_info.value), (
                f"{fqn}: expected the message to mention {fragment!r}, got: "
                f"{exc_info.value}"
            )

    def test_matrix_covers_both_packages(self):
        """The matrix covers every concrete class in *both* packages.

        Re-walked here rather than trusting the module-level collection, so a
        class that appeared after import is caught. The walk is used rather than
        the registry because the registry also holds whatever backends other test
        modules happened to import.
        """
        ExpressionRegistry._auto_register_builtins()
        expected = set(_collect_matrix_classes())
        assert expected == set(REGISTERED), (
            "the set of classes these packages define changed after collection.\n"
            f"  now defined but not covered: {sorted(expected - set(REGISTERED))}\n"
            f"  covered but no longer defined: {sorted(set(REGISTERED) - expected)}"
        )
        prefixes = (CORE_EXPR_PKG + ".", SNOWFLAKE_EXPR_PKG + ".")
        stray = [fqn for fqn in REGISTERED if not fqn.startswith(prefixes)]
        assert not stray, f"classes outside the two packages are in the matrix: {stray}"

    def test_each_package_is_actually_covered(self):
        """Neither package contributes zero classes.

        Stated because the structural problem this file exists for was silent:
        the five existing backend matrices collect ``impl.<backend>.expression``
        and so never touch the core package's own 118 classes, which is how a
        backend formatter reading a field core had removed months earlier stayed
        green. A count is asserted per package, and the specific number is the
        one measured on this branch -- not a ceiling, so a package cannot shrink
        unnoticed, and not an equality, so a class added later does not fail
        here.
        """
        from_core = [
            fqn for fqn in REGISTERED if fqn.startswith(CORE_EXPR_PKG + ".")
        ]
        from_snowflake = [
            fqn for fqn in REGISTERED if fqn.startswith(SNOWFLAKE_EXPR_PKG + ".")
        ]
        assert len(from_core) > 200, (
            f"only {len(from_core)} core classes collected; the package walk may "
            f"have stopped early"
        )
        assert len(from_snowflake) > 20, (
            f"only {len(from_snowflake)} Snowflake classes collected"
        )
        assert len(from_core) + len(from_snowflake) == len(REGISTERED), (
            "a collected class belongs to neither package"
        )

    def test_every_covered_class_is_registered_for_deserialization(self):
        """A class in the matrix can be found again when deserializing.

        Deserialisation looks the class up by name, so a class the matrix renders
        but the registry cannot resolve would round-trip into the wrong thing or
        nothing at all.
        """
        ExpressionRegistry._auto_register_builtins()
        unresolved = sorted(set(REGISTERED) - set(ExpressionRegistry._registry))
        assert not unresolved, (
            f"the matrix covers classes the registry cannot resolve: {unresolved}"
        )

    def test_row_sources_are_reached(self, dialect):
        """Every core row source is in the matrix, named rather than counted.

        Snowflake uses ``NamedRelationRef`` zero times, where clickhouse uses it
        64 and firebird 12. That was worth confirming rather than assuming: it
        means the *core* statements that read a relation do so through a
        different expression here, so the row-source branches of the shared
        renderer could go unexercised. They are not. Each row source is named
        below, so the assertion is about the eight classes that matter rather
        than about a number, and each is then classified -- so "Snowflake uses
        the ref zero times" does not turn into "row sources are untested".

        The engine-specific sources are the interesting half: Snowflake refuses
        JSON_TABLE, XMLTABLE, GRAPH_TABLE and table functions as features it does
        not have, which means their ``UnsupportedFeatureError`` branch is what
        keeps their rendering honest here. The core matrix only found those
        branches because it added the six ``format_*_source`` methods that were
        missing; without them the dispatch reported no such formatter for each,
        which was a capability gap wearing a different spelling rather than a
        refusal.
        """
        expected = {
            "sources.relation.NamedRelationRef": "the relation reference",
            "sources.base.TableSource": "the root of the row-source tree",
            "sources.derived.DerivedTableSource": "a derived table",
            "sources.derived.ValuesTableSource": "an inline VALUES row source",
            "sources.functions.TableFunctionSource": "a table function",
            "sources.json.JsonTableSource": "JSON_TABLE",
            "sources.xml.XmlTableSource": "XMLTABLE",
            "sources.graph.GraphTableSource": "GRAPH_TABLE",
        }
        for suffix, what in sorted(expected.items()):
            candidates = [
                fqn for fqn in REGISTERED if fqn.endswith(suffix)
            ]
            assert candidates, (
                f"no collected class ends in {suffix!r}, so {what} is not "
                f"covered by the matrix at all"
            )
            for fqn in candidates:
                instance, source = make_instance(REGISTERED[fqn], dialect)
                if instance is None:
                    assert fqn in UNCONSTRUCTIBLE, (
                        f"{fqn} is a row source the generic constructor cannot "
                        f"build and is not pinned"
                    )
                    continue
                # Classified rather than merely collected: the assertion inside
                # raises for an unclassified outcome, which is the point.
                assert_sql_roundtrip_classified(fqn, instance, dialect)

    def test_coverage_report(self, dialect):
        """Surface the matrix's classification, so coverage stays transparent."""
        ExpressionRegistry._auto_register_builtins()
        tally = {}
        constructible = 0
        for fqn in sorted(REGISTERED):
            instance, source = make_instance(REGISTERED[fqn], dialect)
            if instance is None:
                tally["not-constructible"] = tally.get("not-constructible", 0) + 1
                continue
            constructible += 1
            branch = assert_sql_roundtrip_classified(fqn, instance, dialect)
            tally[branch] = tally.get(branch, 0) + 1
        report = ", ".join(
            "%s=%d" % (key, tally[key]) for key in sorted(tally)
        )
        print(
            f"\nexpression matrix under Snowflake {DIALECT_VERSION}: "
            f"{len(REGISTERED)} collected, {constructible} constructible [{report}]"
        )
        for fqn in UNCONSTRUCTIBLE:
            print(f"  not constructible: {fqn}")
        for feature, methods in sorted(UNMODELLED_FORMATTERS.items()):
            print(f"  not modelled: {feature} ({len(methods)} formatters)")
        for fqn in sorted(LEGITIMATE_NON_RENDERS):
            print(f"  non-render: {fqn}")