# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_introspection_table_types.py
"""Snowflake's ``TABLE_TYPE`` vocabulary, read and written.

Two defects share one vocabulary:

* the parser folded every spelling it did not know into ``BASE_TABLE`` with
  no trace, so a managed, event, Iceberg, hybrid or dynamic table became
  indistinguishable from a plain one;
* the listing's ``include_views=False`` and ``table_type`` filters spoke only
  the catalogue's spelling -- and the first of them required exactly
  ``BASE TABLE``, hiding every other table kind along with the views.

These tests pin both ends against the same table of spellings.
"""
import pytest

from rhosocial.activerecord.backend.expression.introspection import (
    TableListQueryStatement,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.introspection import (
    SnowflakeIntrospectorMixin,
)
from rhosocial.activerecord.backend.introspection.types import TableType


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


@pytest.fixture
def parser():
    return SnowflakeIntrospectorMixin()


def table_list(dialect, **kwargs):
    return TableListQueryStatement(dialect, schema="MY_SCHEMA", **kwargs).to_sql()


# ------------------------------------------------------------------ #
# Parsing: the catalogue's word survives beside the core member
# ------------------------------------------------------------------ #

@pytest.mark.parametrize(
    "spelling, member",
    [
        ("BASE TABLE", TableType.BASE_TABLE),
        ("MANAGED TABLE", TableType.BASE_TABLE),
        ("EVENT TABLE", TableType.BASE_TABLE),
        ("HYBRID TABLE", TableType.BASE_TABLE),
        ("ICEBERG TABLE", TableType.BASE_TABLE),
        ("DYNAMIC TABLE", TableType.BASE_TABLE),
        ("VIEW", TableType.VIEW),
        ("MATERIALIZED VIEW", TableType.MATERIALIZED_VIEW),
        ("SYSTEM TABLE", TableType.SYSTEM_TABLE),
        ("TEMPORARY TABLE", TableType.TEMPORARY),
        ("EXTERNAL TABLE", TableType.EXTERNAL),
    ],
)
def test_every_known_spelling_keeps_the_catalogue_word(parser, spelling, member):
    tables = parser.parse_tables(
        [{"TABLE_NAME": "ORDERS", "TABLE_TYPE": spelling}], "PUBLIC"
    )
    assert tables[0].table_type is member
    assert tables[0].extra["snowflake_table_type"] == spelling


def test_an_unknown_spelling_is_base_table_with_the_word_kept(parser):
    tables = parser.parse_tables(
        [{"TABLE_NAME": "ORDERS", "TABLE_TYPE": "SOMETHING NEW"}], "PUBLIC"
    )
    assert tables[0].table_type is TableType.BASE_TABLE
    assert tables[0].extra["snowflake_table_type"] == "SOMETHING NEW"


def test_the_catalogue_word_is_always_present(parser):
    tables = parser.parse_tables([{"TABLE_NAME": "ORDERS"}], "PUBLIC")
    assert tables[0].extra["snowflake_table_type"] == "BASE TABLE"


def test_a_lower_case_fixture_still_matches_the_vocabulary(parser):
    tables = parser.parse_tables(
        [{"TABLE_NAME": "ORDERS", "TABLE_TYPE": "materialized view"}], "PUBLIC"
    )
    assert tables[0].table_type is TableType.MATERIALIZED_VIEW
    assert tables[0].extra["snowflake_table_type"] == "MATERIALIZED VIEW"


# ------------------------------------------------------------------ #
# include_views=False removes views, not every non-base kind
# ------------------------------------------------------------------ #

def test_no_views_removes_only_the_view_spellings(dialect):
    sql, params = table_list(dialect, include_views=False)
    assert "NOT (TABLE_TYPE IN ('VIEW', 'MATERIALIZED VIEW'))" in sql
    assert "TABLE_TYPE = 'BASE TABLE'" not in sql
    assert params == ("MY_SCHEMA",)


# ------------------------------------------------------------------ #
# table_type accepts both vocabularies
# ------------------------------------------------------------------ #

def test_a_core_materialized_view_expands_to_the_catalogue_spelling(dialect):
    sql, params = table_list(dialect, table_type="MATERIALIZED_VIEW")
    assert "TABLE_TYPE IN (%s)" in sql
    assert params == ("MY_SCHEMA", "MATERIALIZED VIEW")


def test_a_core_external_kind_expands_to_the_catalogue_spelling(dialect):
    _sql, params = table_list(dialect, table_type="EXTERNAL")
    assert params == ("MY_SCHEMA", "EXTERNAL TABLE")


def test_a_core_base_table_covers_every_table_spelling(dialect):
    _sql, params = table_list(dialect, table_type="BASE_TABLE")
    assert params == (
        "MY_SCHEMA",
        "BASE TABLE",
        "MANAGED TABLE",
        "EVENT TABLE",
        "HYBRID TABLE",
        "ICEBERG TABLE",
        "DYNAMIC TABLE",
    )


def test_a_core_member_object_is_read_as_its_name(dialect):
    _sql, params = table_list(dialect, table_type=TableType.VIEW)
    assert params == ("MY_SCHEMA", "VIEW")


def test_a_raw_catalogue_spelling_filters_exactly_that_spelling(dialect):
    _sql, params = table_list(dialect, table_type="ICEBERG TABLE")
    assert params == ("MY_SCHEMA", "ICEBERG TABLE")


def test_a_kind_the_catalogue_never_names_matches_nothing(dialect):
    sql, params = table_list(dialect, table_type="FOREIGN_TABLE")
    assert "1 = 2" in sql
    assert params == ("MY_SCHEMA",)
