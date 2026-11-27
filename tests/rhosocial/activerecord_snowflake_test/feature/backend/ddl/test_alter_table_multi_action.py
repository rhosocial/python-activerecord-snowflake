# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_alter_table_multi_action.py
"""One expression renders one action, on every dialect.

Snowflake's grammar takes one ``tableAction`` per ``ALTER TABLE``, and the
framework reaches the same shape everywhere: a statement carrying two actions
fails fast with ``UnsupportedFeatureError`` rather than comma-joining them.
Comma-joining would hide the second action from the caller's plan -- its own
phase, permission and destructive check. A single-action statement renders
normally.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    AlterTableStatement,
    ColumnDefinition,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumnAction,
    DropColumnAction,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


def _single_action_statement(dialect):
    return AlterTableStatement(
        dialect,
        Table(dialect, "t"),
        [AddColumnAction(dialect, ColumnDefinition(dialect, "c1", IntegerType(dialect)))],
    )


def _two_action_statement(dialect):
    return AlterTableStatement(
        dialect,
        Table(dialect, "t"),
        [
            AddColumnAction(dialect, ColumnDefinition(dialect, "c1", IntegerType(dialect))),
            DropColumnAction(dialect, "c2"),
        ],
    )


class TestSnowflakeMultiActionAlterTable:
    def test_two_actions_are_refused(self, dialect):
        with pytest.raises(UnsupportedFeatureError, match="multiple actions"):
            _two_action_statement(dialect).to_sql()

    def test_single_action_renders_normally(self, dialect):
        sql, params = _single_action_statement(dialect).to_sql()

        assert sql == 'ALTER TABLE "t" ADD COLUMN "c1" INTEGER'
        assert sql.count("ALTER TABLE") == 1
        assert params == ()
