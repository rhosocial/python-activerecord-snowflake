# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_create_table_expression_diff.py
"""Snowflake CreateTableExpression diff tests (Phase 3).

Mirrors the cross-backend diff test template (class/method names align with
the core library's `test_create_table_expression_diff.py`).

Snowflake capability summary (drives each test's expected path):
- column type change : in place via ``MODIFY COLUMN`` (Snowflake redefines
                      the column wholesale; DEFAULT/NOT NULL ride along)
- column properties  : NO standalone ``ALTER COLUMN SET/DROP DEFAULT`` ->
                      property-only changes route to a rebuild
- indexes            : NO traditional indexes (only SEARCH INDEX, separate
                      statement) -> rebuild
- primary key change : RebuildPlan
- partition change    : RebuildPlan
"""

import pytest

from rhosocial.activerecord.backend.dialect.protocols import CreateTableExpressionDiffSupport
from rhosocial.activerecord.backend.expression import DiffPlan, RebuildPlan
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumn,
    DropColumn,
    ModifyColumn,
    RenameTable,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    CreateTableExpression,
    IndexDefinition,
    TableConstraint,
    TableConstraintType,
    TableOptions,
)
from rhosocial.activerecord.backend.expression.types import (
    IntegerType,
    TextType,
    VarCharType,
)
from rhosocial.activerecord.backend.impl.dummy.dialect import DummyDialect
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


def _col(name, dtype, *constraints):
    return ColumnDefinition(name=name, data_type=dtype, constraints=list(constraints))


def _pk():
    return ColumnConstraint(constraint_type=ColumnConstraintType.PRIMARY_KEY)


def _not_null():
    return ColumnConstraint(constraint_type=ColumnConstraintType.NOT_NULL)


def _expr(dialect, columns, indexes=None, constraints=None, **kwargs):
    return CreateTableExpression(
        dialect=dialect,
        table=kwargs.pop("table", "items"),
        columns=columns,
        indexes=indexes,
        table_constraints=constraints,
        **kwargs,
    )


D = SnowflakeDialect


class TestProtocolConformance:

    def test_snowflake_dialect_satisfies_protocol(self):
        assert isinstance(D(), CreateTableExpressionDiffSupport)


class TestValidation:

    def test_cross_dialect_raises(self):
        old = _expr(D(), [_col("id", IntegerType(), _pk())])
        new = _expr(DummyDialect(), [_col("id", IntegerType(), _pk())])
        with pytest.raises(ValueError, match="different dialects"):
            old.diff(new)

    def test_cross_table_raises(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())])
        new = _expr(d, [_col("id", IntegerType(), _pk())], table="other")
        with pytest.raises(ValueError, match="different tables"):
            old.diff(new)


class TestNoChange:

    def test_identical_definitions_empty_plan(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk()), _col("name", TextType())])
        new = _expr(d, [_col("id", IntegerType(), _pk()), _col("name", TextType())])
        plan = old.diff(new)
        assert not plan.has_changes
        assert plan.rebuild is None
        assert plan.alters == []


class TestColumnChanges:

    def test_added_column_yields_add_action(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())])
        new = _expr(d, [_col("id", IntegerType(), _pk()), _col("bio", TextType())])
        plan = old.diff(new)
        assert plan.rebuild is None and plan.has_changes
        (alter,) = plan.alters
        action = alter.actions[0]
        assert isinstance(action, AddColumn)
        assert action.column.name == "bio"

    def test_removed_column_yields_drop_action(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk()), _col("bio", TextType())])
        new = _expr(d, [_col("id", IntegerType(), _pk())])
        plan = old.diff(new)
        (action,) = plan.alters[0].actions
        assert isinstance(action, DropColumn)
        assert action.column_name == "bio"


class TestColumnPropertyChanges:
    """Snowflake: property-only changes (no type change) -> rebuild."""

    def test_set_default_rebuilds(self):
        d = D()
        old = _expr(d, [_col("status", TextType())])
        new = _expr(d, [_col(
            "status", TextType(),
            ColumnConstraint(constraint_type=ColumnConstraintType.DEFAULT, default_value="ok"),
        )])
        plan = old.diff(new)
        assert plan.alters == []
        assert plan.rebuild is not None

    def test_set_not_null_rebuilds(self):
        d = D()
        old = _expr(d, [_col("name", TextType())])
        new = _expr(d, [_col("name", TextType(), _not_null())])
        plan = old.diff(new)
        assert plan.rebuild is not None


class TestTypeChangeRebuild:
    """Snowflake: type change is in place via ``MODIFY COLUMN``."""

    def test_type_change_yields_modify_column_action(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())])
        new = _expr(d, [_col("id", IntegerType(), _pk()), _col("code", TextType())])
        plan = old.diff(new)
        assert plan.rebuild is None
        (alter,) = plan.alters
        action = alter.actions[0]
        assert isinstance(action, ModifyColumn)
        assert action.column.name == "code"

    def test_type_change_renders_modify_column_sql(self):
        d = D()
        old = _expr(d, [_col("code", VarCharType(length=50))])
        new = _expr(d, [_col("code", VarCharType(length=100))])
        plan = old.diff(new)
        sql, _ = plan.alters[0].to_sql()
        upper = sql.upper()
        assert "MODIFY COLUMN" in upper
        assert "VARCHAR" in upper


class TestIndexChanges:
    """Snowflake has no traditional indexes -> rebuild."""

    def test_added_index_rebuilds(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())])
        new = _expr(d, [_col("id", IntegerType(), _pk())],
                    indexes=[IndexDefinition(name="idx_id", columns=["id"])])
        plan = old.diff(new)
        assert plan.alters == []
        assert plan.rebuild is not None
        assert "index change" in plan.rebuild.reason

    def test_removed_index_rebuilds(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())],
                    indexes=[IndexDefinition(name="idx_id", columns=["id"])])
        new = _expr(d, [_col("id", IntegerType(), _pk())])
        plan = old.diff(new)
        assert plan.rebuild is not None


class TestTableConstraintChanges:

    def test_pk_change_rebuilds(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType()), _col("code", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["id"])])
        new = _expr(d, [_col("id", IntegerType()), _col("code", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["code"])])
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "primary key" in plan.rebuild.reason


class TestStructuralChanges:

    def test_table_options_change_rebuilds(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())])
        new = _expr(d, [_col("id", IntegerType(), _pk())],
                    table_options=TableOptions(comment="x"))
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "structural" in plan.rebuild.reason

    def test_rebuild_plan_shape(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())])
        new = _expr(d, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())],
                    indexes=[IndexDefinition(name="idx_code", columns=["code"])])
        rp = old.diff(new).rebuild
        assert rp.create.table_name == "items__rebuild__"
        assert rp.drop_old.table.name == "items"
        assert isinstance(rp.rename.actions[0], RenameTable)
        assert rp.rename.actions[0].new_name == "items"
        assert rp.copy_columns == ["id", "code"]


class TestDiffPlanInvariants:

    def test_alters_and_rebuild_mutually_exclusive(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())])
        new = _expr(d, [_col("id", IntegerType(), _pk()), _col("x", TextType())])
        plan = old.diff(new)
        assert plan.rebuild is None and plan.alters


class TestDefectRegressions:

    def test_fk_table_constraint_signature_branch(self):
        """Regression: _constraint_signature accessed ColumnConstraint-only
        ``foreign_key_reference``; a TableConstraint carrying
        ``foreign_key_table`` raised AttributeError in the unnamed path.
        """
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            ForeignKeyConstraint,
        )
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk()), _col("uid", IntegerType())])
        new = _expr(
            d, [_col("id", IntegerType(), _pk()), _col("uid", IntegerType())],
            constraints=[ForeignKeyConstraint(
                columns=["uid"], foreign_key_table="users", foreign_key_columns=["id"],
            )],
        )
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "unnamed" in plan.rebuild.reason
