# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_alter_table_if_exists.py
"""Tests for Snowflake ALTER TABLE IF [NOT] EXISTS handling.

Snowflake supports ``ADD COLUMN IF NOT EXISTS`` and ``DROP COLUMN
IF EXISTS``, but **not** ``DROP CONSTRAINT IF EXISTS``. ``ADD COLUMN
IF NOT EXISTS`` cannot be combined with DEFAULT/IDENTITY/UNIQUE/PK/FK.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import (
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumn,
    DropColumn,
    DropTableConstraint,
)
from rhosocial.activerecord.backend.expression.types import TextType, VarCharType
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeAlterTableModifierCapabilities:
    def test_supports_switches(self, dialect):
        assert dialect.supports_add_column_if_not_exists() is True
        assert dialect.supports_drop_column_if_exists() is True
        assert dialect.supports_drop_constraint_if_exists() is False


class TestSnowflakeAddColumnIfNotExists:
    def test_if_not_exists_renders_qualifier(self, dialect):
        action = AddColumn(
            dialect,
            ColumnDefinition("content", TextType()),
            if_not_exists=True,
        )
        sql, params = action.to_sql()
        assert 'ADD COLUMN IF NOT EXISTS "content" TEXT' == sql
        assert params == ()

    def test_if_not_exists_with_not_null_allowed(self, dialect):
        action = AddColumn(
            dialect,
            ColumnDefinition(
                "content",
                TextType(),
                constraints=[ColumnConstraint(ColumnConstraintType.NOT_NULL)],
            ),
            if_not_exists=True,
        )
        sql, params = action.to_sql()
        assert 'ADD COLUMN IF NOT EXISTS "content" TEXT NOT NULL' == sql
        assert params == ()

    def test_if_not_exists_with_default_raises(self, dialect):
        action = AddColumn(
            dialect,
            ColumnDefinition(
                "content",
                VarCharType(50),
                constraints=[
                    ColumnConstraint(ColumnConstraintType.DEFAULT, default_value="x")
                ],
            ),
            if_not_exists=True,
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_none_renders_plain_form(self, dialect):
        action = AddColumn(dialect, ColumnDefinition("content", TextType()))
        sql, params = action.to_sql()
        assert 'ADD COLUMN "content" TEXT' == sql
        assert "IF NOT EXISTS" not in sql
        assert params == ()


class TestSnowflakeDropColumnIfExists:
    def test_if_exists_renders_qualifier(self, dialect):
        action = DropColumn(dialect, column_name="x", if_exists=True)
        sql, params = action.to_sql()
        assert 'DROP COLUMN IF EXISTS "x"' == sql
        assert params == ()

    def test_none_renders_plain_form(self, dialect):
        action = DropColumn(dialect, column_name="x")
        sql, params = action.to_sql()
        assert 'DROP COLUMN "x"' == sql
        assert "IF EXISTS" not in sql
        assert params == ()


class TestSnowflakeDropConstraint:
    def test_if_exists_raises(self, dialect):
        action = DropTableConstraint(
            dialect, constraint_name="fk", if_exists=True
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_none_renders_plain_form(self, dialect):
        action = DropTableConstraint(dialect, constraint_name="fk")
        sql, params = action.to_sql()
        assert 'DROP CONSTRAINT "fk"' == sql
        assert "IF EXISTS" not in sql
        assert params == ()