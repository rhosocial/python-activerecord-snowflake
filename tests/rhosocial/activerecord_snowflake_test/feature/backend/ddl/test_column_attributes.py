# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_column_attributes.py
"""Snowflake rendering of the dialect-free column-attribute channel."""

from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    IdentityClause,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.base import CollationAttribute
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


def _column(dialect, attrs):
    col = ColumnDefinition(dialect, "id", IntegerType(dialect))
    col.attributes = attrs
    return col


def _identity(dialect, **options):
    """Build the expression-layer clause a hand-built column must carry.

    AR-layer ``IdentityAttribute`` objects are translated by the deriver
    (``base.derivation``) before they reach ``ColumnDefinition.attributes``;
    the dialect renderer only accepts expression-layer clauses.
    """
    return IdentityClause(dialect, **options)


def test_identity_uses_identity_start_step():
    dialect = SnowflakeDialect((8, 0, 0))
    col = _column(dialect, [_identity(dialect, generation="BY DEFAULT", start=5, increment=2)])
    assert col.to_sql()[0] == '"id" INTEGER IDENTITY(5, 2)'


def test_identity_defaults_to_start_step_one():
    dialect = SnowflakeDialect((8, 0, 0))
    col = _column(dialect, [_identity(dialect)])
    assert col.to_sql()[0] == '"id" INTEGER IDENTITY(1, 1)'


def test_collation_is_quoted():
    dialect = SnowflakeDialect((8, 0, 0))
    col = _column(dialect, [CollationAttribute(name="en-ci")])
    assert col.to_sql()[0] == '"id" INTEGER COLLATE \'en-ci\''
