# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_column_attributes.py
"""Snowflake rendering of the dialect-free column-attribute channel."""

from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.base.ddl.attributes import CollationAttribute, IdentityAttribute
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


def _column(dialect, attrs):
    col = ColumnDefinition(dialect, "id", IntegerType(dialect))
    col.attributes = dialect.select_column_attributes(attrs)
    return col


def test_identity_uses_identity_start_step():
    dialect = SnowflakeDialect((8, 0, 0))
    col = _column(dialect, [IdentityAttribute(generation="BY DEFAULT", start=5, increment=2)])
    assert col.to_sql()[0] == '"id" INTEGER IDENTITY(5, 2)'


def test_identity_defaults_to_start_step_one():
    dialect = SnowflakeDialect((8, 0, 0))
    col = _column(dialect, [IdentityAttribute(generation="ALWAYS")])
    assert col.to_sql()[0] == '"id" INTEGER IDENTITY(1, 1)'


def test_collation_is_quoted():
    dialect = SnowflakeDialect((8, 0, 0))
    col = _column(dialect, [CollationAttribute(name="en-ci")])
    assert col.to_sql()[0] == '"id" INTEGER COLLATE \'en-ci\''
