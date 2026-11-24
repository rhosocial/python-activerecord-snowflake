# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_alter_table_multi_action.py
"""Snowflake ALTER TABLE accepts only one action per statement.

The shared ALTER TABLE formatter comma-joins actions when the dialect's
``supports_multi_action_alter_table()`` probe is True. Snowflake's grammar has
no such comma-separated action list, so the dialect answers False and core
emits one statement per action instead.
"""

import pytest

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
    def test_probe_is_false(self, dialect):
        assert dialect.supports_multi_action_alter_table() is False

    def test_two_actions_are_not_comma_joined(self, dialect):
        sql, params = _two_action_statement(dialect).to_sql()

        assert (
            sql
            == 'ALTER TABLE "t" ADD COLUMN "c1" INTEGER; ALTER TABLE "t" DROP COLUMN "c2"'
        )
        assert sql.count("ALTER TABLE") == 2
        assert ", DROP COLUMN" not in sql
        assert params == ()
