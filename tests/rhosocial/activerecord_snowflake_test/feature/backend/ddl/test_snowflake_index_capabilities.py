# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_snowflake_index_capabilities.py
"""Snowflake index capability probes and by-name refusals.

Snowflake has no plain ``CREATE INDEX`` / ``DROP INDEX`` for ordinary tables.
Its only index DDL is the hybrid-table secondary index family:

* ``CREATE [ OR REPLACE ] INDEX [ IF NOT EXISTS ] <index_name>
  ON <table_name> ( <col_name> [ , ... ] ) [ INCLUDE ( ... ) ]``
* ``DROP INDEX [ IF EXISTS ] <table_name>.<index_name>``

Both target a hybrid table, which this backend does not model, and the drop
form is table-qualified rather than ``DROP INDEX <name> ON <table>``.  These
tests pin every index probe the dialect exposes, and assert that the
plain-index formatters and the ALTER TABLE index actions refuse by name
instead of emitting SQL the service would reject.

Evidence (fetched 2026-11-25):
https://docs.snowflake.com/en/sql-reference/sql/create-index
https://docs.snowflake.com/en/sql-reference/sql/drop-index
https://docs.snowflake.com/en/sql-reference/sql/create-hybrid-table
"""

import inspect

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Index, Table
from rhosocial.activerecord.backend.expression.statements import (
    AlterTableStatement,
    ColumnDefinition,
    CreateTableStatement,
    IndexDefinition,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddIndexAction,
    DropIndexAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_index import (
    CreateFulltextIndexStatement,
    CreateIndexStatement,
    DropFulltextIndexStatement,
    DropIndexStatement,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import SnowflakeIndexMixin


#: name, expected answer, and the reason the answer is what it is.
INDEX_PROBES = (
    # -- flipped by this change: core's defaults claimed plain index DDL ----
    (
        "supports_create_index",
        False,
        "CREATE INDEX exists only for hybrid tables, which this backend does not model",
    ),
    (
        "supports_unique_index",
        False,
        "Snowflake's CREATE INDEX grammar has no UNIQUE qualifier",
    ),
    (
        "supports_drop_index",
        False,
        "DROP INDEX is hybrid-table only and table-qualified",
    ),
    (
        "supports_drop_index_on_table",
        False,
        "the grammar is <table_name>.<index_name>, with no ON suffix",
    ),
    (
        "supports_indexes",
        False,
        "ordinary tables have no indexes; clustering keys are not indexes",
    ),
    # -- already False, pinned locally so a core default cannot move them ----
    (
        "supports_index_if_not_exists",
        False,
        "IF NOT EXISTS exists only in the unmodelled hybrid-table statement",
    ),
    (
        "supports_index_if_exists",
        False,
        "IF EXISTS exists only in the unmodelled hybrid-table statement",
    ),
    ("supports_index_type", False, "no USING clause in the index grammar"),
    ("supports_partial_index", False, "no WHERE clause in the index grammar"),
    ("supports_functional_index", False, "columns only; no expression position"),
    (
        "supports_index_include",
        False,
        "INCLUDE exists only in the unmodelled hybrid-table statement",
    ),
    ("supports_index_tablespace", False, "Snowflake has no tablespaces"),
    ("supports_concurrent_index", False, "no CONCURRENTLY keyword in Snowflake SQL"),
    ("supports_fulltext_index", False, "search optimization is not a FULLTEXT clause"),
    ("supports_inline_index", False, "standard CREATE TABLE has no index branch"),
    (
        "supports_alter_table_index_actions",
        False,
        "the ALTER TABLE action list has no ADD/DROP INDEX",
    ),
)

#: Adjacent introspection answers.  Not plain-index DDL, but pinned here so the
#: index scope's shape is recorded in one place.
INDEX_INTROSPECTION_PROBES = (
    (
        "supports_index_introspection",
        True,
        "the INDEX scope is answered from constraint metadata, not an index catalogue",
    ),
    ("supports_index_stats", False, "no index usage statistics family"),
    ("supports_unused_indexes_detection", False, "no unused-index statistics family"),
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


@pytest.mark.parametrize(
    "switch_name,expected,reason",
    INDEX_PROBES + INDEX_INTROSPECTION_PROBES,
    ids=[name for name, _, _ in INDEX_PROBES + INDEX_INTROSPECTION_PROBES],
)
def test_every_index_probe_is_honest(switch_name, expected, reason, dialect):
    """Each probe answers what the reference supports, not a core default."""
    assert getattr(dialect, switch_name)() is expected, reason


@pytest.mark.parametrize(
    "switch_name,expected,reason",
    INDEX_PROBES,
    ids=[name for name, _, _ in INDEX_PROBES],
)
def test_each_ddl_index_probe_is_declared_in_this_package(
    switch_name, expected, reason, dialect
):
    """The DDL answers are owned here, not inherited from core."""
    declaring = next(
        cls for cls in type(dialect).__mro__ if switch_name in cls.__dict__
    )
    assert declaring.__module__.startswith(
        "rhosocial.activerecord.backend.impl.snowflake"
    ), f"{switch_name} is declared by {declaring.__module__}"
    assert getattr(dialect, switch_name)() is expected, reason


def test_create_index_refuses_by_name(dialect):
    expression = CreateIndexStatement(
        dialect, Index(dialect, "i"), Table(dialect, "t"), ["a"]
    )
    with pytest.raises(UnsupportedFeatureError) as caught:
        expression.to_sql()
    assert caught.value.feature_name == "CREATE INDEX"
    assert "hybrid table" in str(caught.value)


def test_unique_create_index_refuses_by_name(dialect):
    """``UNIQUE`` is not an index qualifier, so it must not change the answer."""
    expression = CreateIndexStatement(
        dialect, Index(dialect, "i"), Table(dialect, "t"), ["a"], unique=True
    )
    with pytest.raises(UnsupportedFeatureError) as caught:
        expression.to_sql()
    assert caught.value.feature_name == "CREATE INDEX"
    assert "hybrid table" in str(caught.value)


def test_create_index_with_include_refuses_by_name(dialect):
    """``INCLUDE`` belongs to the unmodelled hybrid-table statement too."""
    expression = CreateIndexStatement(
        dialect, Index(dialect, "i"), Table(dialect, "t"), ["a"], include=["b"]
    )
    with pytest.raises(UnsupportedFeatureError) as caught:
        expression.to_sql()
    assert caught.value.feature_name == "CREATE INDEX"
    assert "hybrid table" in str(caught.value)


def test_drop_index_refuses_by_name(dialect):
    expression = DropIndexStatement(
        dialect, Index(dialect, "i"), Table(dialect, "t"), if_exists=True
    )
    with pytest.raises(UnsupportedFeatureError) as caught:
        expression.to_sql()
    assert caught.value.feature_name == "DROP INDEX"
    assert "<table_name>.<index_name>" in str(caught.value)
    assert "hybrid table" in str(caught.value)


def test_alter_table_add_index_refuses_by_name(dialect):
    expression = AlterTableStatement(
        dialect,
        table=Table(dialect, "t"),
        actions=[AddIndexAction(dialect, IndexDefinition(dialect, "i", ["a"]))],
    )
    with pytest.raises(UnsupportedFeatureError) as caught:
        expression.to_sql()
    assert caught.value.feature_name == "ALTER TABLE ADD INDEX"
    assert "ADD INDEX" in str(caught.value)


def test_alter_table_drop_index_refuses_by_name(dialect):
    expression = AlterTableStatement(
        dialect,
        table=Table(dialect, "t"),
        actions=[DropIndexAction(dialect, Index(dialect, "i"))],
    )
    with pytest.raises(UnsupportedFeatureError) as caught:
        expression.to_sql()
    assert caught.value.feature_name == "ALTER TABLE DROP INDEX"
    assert "DROP INDEX" in str(caught.value)


def test_inline_create_table_index_is_refused(dialect):
    column = ColumnDefinition(dialect, "id", IntegerType(dialect))
    expression = CreateTableStatement(
        dialect,
        Table(dialect, "t"),
        [column],
        indexes=[IndexDefinition(dialect, "i", ["id"])],
    )
    with pytest.raises(UnsupportedFeatureError) as caught:
        expression.to_sql()
    assert "inline index" in str(caught.value)


def test_fulltext_index_statements_are_refused(dialect):
    create = CreateFulltextIndexStatement(
        dialect, Index(dialect, "i"), Table(dialect, "t"), ["a"]
    )
    drop = DropFulltextIndexStatement(dialect, Index(dialect, "i"), Table(dialect, "t"))
    for expression in (create, drop):
        with pytest.raises(UnsupportedFeatureError) as caught:
            expression.to_sql()
        assert caught.value.feature_name == "FULLTEXT INDEX"


def test_hybrid_table_index_family_is_recorded_as_unmodelled(dialect):
    """No hybrid-table node or formatter is invented on this dialect."""
    for method in (
        "format_create_hybrid_table_statement",
        "format_create_hybrid_index_statement",
        "format_drop_hybrid_index_statement",
    ):
        assert not hasattr(dialect, method), f"{method} must not exist"
    doc = inspect.getdoc(inspect.getmodule(SnowflakeIndexMixin)) or ""
    for phrase in ("CREATE HYBRID TABLE", "CREATE INDEX", "DROP INDEX"):
        assert phrase in doc, f"the module docstring must record {phrase!r}"
