# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_alter_table_if_exists.py
"""Tests for Snowflake ALTER TABLE IF [NOT] EXISTS handling.

Snowflake supports ``ADD COLUMN IF NOT EXISTS`` and ``DROP COLUMN
IF EXISTS``, but **not** ``DROP CONSTRAINT IF EXISTS``. ``ADD COLUMN
IF NOT EXISTS`` cannot be combined with DEFAULT/IDENTITY/UNIQUE/PK/FK.

``DROP CONSTRAINT`` itself has two addresses: by name and by kind plus the
local column list (``PRIMARY KEY`` alone, ``UNIQUE`` / ``FOREIGN KEY`` with
columns). A CHECK has no kind branch and must be named.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    Column,
    ComparisonPredicate,
    Literal,
    TableCheckConstraint,
    TableConstraint,
    TableForeignKeyConstraint,
    TablePrimaryKeyConstraint,
    TableUniqueConstraint,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    AutoIncrementClause,
    ColumnConstraint,
    ColumnDefaultConstraint,
    ColumnDefinition,
    ColumnNotNullConstraint,
    IdentityClause,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumnAction,
    AlterTableStatement,
    DropColumnAction,
    DropTableConstraintAction,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, TextType, VarCharType
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
        action = AddColumnAction(
            dialect,
            ColumnDefinition(dialect, "content", TextType(dialect)),
            if_not_exists=True,
        )
        sql, params = action.to_sql()
        assert 'ADD COLUMN IF NOT EXISTS "content" VARCHAR(16777216)' == sql
        assert params == ()

    def test_if_not_exists_with_not_null_allowed(self, dialect):
        action = AddColumnAction(
            dialect,
            ColumnDefinition(
                dialect,
                "content",
                TextType(dialect),
                constraints=[
                    ColumnConstraint(
                        dialect, branch=ColumnNotNullConstraint(dialect)
                    )
                ],
            ),
            if_not_exists=True,
        )
        sql, params = action.to_sql()
        assert 'ADD COLUMN IF NOT EXISTS "content" VARCHAR(16777216) NOT NULL' == sql
        assert params == ()

    def test_if_not_exists_with_default_raises(self, dialect):
        action = AddColumnAction(
            dialect,
            ColumnDefinition(
                dialect,
                "content",
                VarCharType(dialect, length=50),
                constraints=[
                    ColumnConstraint(
                        dialect, branch=ColumnDefaultConstraint(dialect, "x")
                    )
                ],
            ),
            if_not_exists=True,
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_if_not_exists_with_identity_raises(self, dialect):
        """The reference also forbids IDENTITY/AUTOINCREMENT with the clause."""
        action = AddColumnAction(
            dialect,
            ColumnDefinition(
                dialect,
                "id",
                IntegerType(dialect),
                attributes=[IdentityClause(dialect, start=1, increment=1)],
            ),
            if_not_exists=True,
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_if_not_exists_with_autoincrement_raises(self, dialect):
        action = AddColumnAction(
            dialect,
            ColumnDefinition(
                dialect,
                "id",
                IntegerType(dialect),
                attributes=[AutoIncrementClause(dialect)],
            ),
            if_not_exists=True,
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_identity_without_if_not_exists_renders(self, dialect):
        """The restriction belongs to the qualifier, not to IDENTITY itself."""
        action = AddColumnAction(
            dialect,
            ColumnDefinition(
                dialect,
                "id",
                IntegerType(dialect),
                attributes=[IdentityClause(dialect, start=1, increment=1)],
            ),
        )
        sql, _ = action.to_sql()
        assert sql == 'ADD COLUMN "id" INTEGER IDENTITY(1, 1)'

    def test_none_renders_plain_form(self, dialect):
        action = AddColumnAction(dialect, ColumnDefinition(dialect, "content", TextType(dialect)))
        sql, params = action.to_sql()
        assert 'ADD COLUMN "content" VARCHAR(16777216)' == sql
        assert "IF NOT EXISTS" not in sql
        assert params == ()


class TestSnowflakeDropColumnIfExists:
    def test_if_exists_renders_qualifier(self, dialect):
        action = DropColumnAction(dialect, column_name="x", if_exists=True)
        sql, params = action.to_sql()
        assert 'DROP COLUMN IF EXISTS "x"' == sql
        assert params == ()

    def test_none_renders_plain_form(self, dialect):
        action = DropColumnAction(dialect, column_name="x")
        sql, params = action.to_sql()
        assert 'DROP COLUMN "x"' == sql
        assert "IF EXISTS" not in sql
        assert params == ()


class TestSnowflakeDropConstraint:
    def test_if_exists_raises(self, dialect):
        action = DropTableConstraintAction(
            dialect, constraint_name="fk", if_exists=True
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_none_renders_plain_form(self, dialect):
        action = DropTableConstraintAction(dialect, constraint_name="fk")
        sql, params = action.to_sql()
        assert 'DROP CONSTRAINT "fk"' == sql
        assert "IF EXISTS" not in sql
        assert params == ()

    def test_name_wins_when_both_addresses_are_given(self, dialect):
        declaration = TableConstraint(
            dialect, branch=TableUniqueConstraint(dialect, ["a", "b"]), name="uq_ab"
        )
        action = DropTableConstraintAction(
            dialect, constraint_name="uq_ab", constraint=declaration
        )
        assert action.to_sql() == ('DROP CONSTRAINT "uq_ab"', ())


class TestSnowflakeDropConstraintByKind:
    """The grammar's second address: ``DROP <kind> (<cols>)``.

    Snowflake's ``constraintAction`` production spells ``PRIMARY KEY`` alone,
    and ``UNIQUE`` / ``FOREIGN KEY`` with the local column list.  The branch of
    the declaration is what decides which kind is rendered.
    """

    def test_declaration_only_primary_key(self, dialect):
        declaration = TableConstraint(
            dialect, branch=TablePrimaryKeyConstraint(dialect, ["id"])
        )
        action = DropTableConstraintAction(dialect, constraint=declaration)
        assert action.to_sql() == ("DROP PRIMARY KEY", ())

    def test_declaration_only_unique_renders_its_columns(self, dialect):
        declaration = TableConstraint(
            dialect, branch=TableUniqueConstraint(dialect, ["a", "b"])
        )
        action = DropTableConstraintAction(dialect, constraint=declaration)
        assert action.to_sql() == ('DROP UNIQUE ("a", "b")', ())

    def test_declaration_only_foreign_key_renders_local_columns(self, dialect):
        declaration = TableConstraint(
            dialect,
            branch=TableForeignKeyConstraint(
                dialect, ["a"], (Table(dialect, "parent"), ["id"])
            ),
        )
        action = DropTableConstraintAction(dialect, constraint=declaration)
        assert action.to_sql() == ('DROP FOREIGN KEY ("a")', ())

    def test_declaration_only_check_is_refused_by_name(self, dialect):
        condition = ComparisonPredicate(
            dialect, "=", Column(dialect, "age"), Literal(dialect, 0, inline=True)
        )
        declaration = TableConstraint(
            dialect, branch=TableCheckConstraint(dialect, condition)
        )
        action = DropTableConstraintAction(dialect, constraint=declaration)
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            action.to_sql()
        assert "DROP CONSTRAINT by kind for CHECK" in excinfo.value.feature_name
        assert "constraint_name" in str(excinfo.value)

    def test_check_with_a_name_renders_by_name(self, dialect):
        condition = ComparisonPredicate(
            dialect, "=", Column(dialect, "age"), Literal(dialect, 0, inline=True)
        )
        declaration = TableConstraint(
            dialect, branch=TableCheckConstraint(dialect, condition), name="ck_age"
        )
        action = DropTableConstraintAction(dialect, constraint_name="ck_age")
        assert action.to_sql() == ('DROP CONSTRAINT "ck_age"', ())
        assert declaration.name == "ck_age"

    def test_two_addresses_is_a_malformed_action(self, dialect):
        action = DropTableConstraintAction(dialect)
        with pytest.raises(ValueError, match="requires constraint_name or constraint"):
            action.to_sql()

    def test_cascade_survives_the_by_kind_branch(self, dialect):
        declaration = TableConstraint(
            dialect, branch=TablePrimaryKeyConstraint(dialect, ["id"])
        )
        action = DropTableConstraintAction(
            dialect, constraint=declaration, cascade=True
        )
        assert action.to_sql() == ("DROP PRIMARY KEY CASCADE", ())

    def test_the_action_builds_a_full_alter_table_statement(self, dialect):
        declaration = TableConstraint(
            dialect, branch=TableUniqueConstraint(dialect, ["a", "b"])
        )
        statement = AlterTableStatement(
            dialect,
            Table(dialect, "t"),
            [DropTableConstraintAction(dialect, constraint=declaration)],
        )
        assert statement.to_sql() == (
            'ALTER TABLE "t" DROP UNIQUE ("a", "b")',
            (),
        )

    def test_unique_without_columns_is_not_spellable_by_kind(self, dialect):
        declaration = TableConstraint(
            dialect, branch=TableUniqueConstraint(dialect, [])
        )
        action = DropTableConstraintAction(dialect, constraint=declaration)
        with pytest.raises(ValueError, match="requires at least one column"):
            action.to_sql()

    def test_a_branch_is_not_a_declaration(self, dialect):
        branch = TablePrimaryKeyConstraint(dialect, ["id"])
        action = DropTableConstraintAction(dialect, constraint=branch)
        with pytest.raises(TypeError, match="must be a TableConstraint"):
            action.to_sql()