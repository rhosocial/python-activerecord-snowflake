# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_alter_column_actions.py
"""Snowflake's ``ALTER COLUMN`` default and nullability actions.

The four operations and the spelling the backend renders for each:

=================  ============================================================  ==========
Operation          Snowflake spelling                                            Verdict
=================  ============================================================  ==========
``DROP DEFAULT``   ``ALTER COLUMN <col> DROP DEFAULT``                           rendered
``SET DEFAULT``    ``ALTER COLUMN <col> SET DEFAULT <seq_name>.NEXTVAL``         rendered
``SET NOT NULL``   ``ALTER COLUMN <col> SET NOT NULL``                           rendered
``DROP NOT NULL``  ``ALTER COLUMN <col> DROP NOT NULL``                           rendered
=================  ============================================================  ==========

The one narrow edge is ``SET DEFAULT``: Snowflake accepts it only to change the
sequence a column *already* uses as its default, and only spelled as a
``NEXTVAL`` reference. Adding a default, or replacing a non-sequence default,
is not an ``ALTER COLUMN`` action at all -- it needs the full column
re-specification ``MODIFY COLUMN <col> <type> [ DEFAULT <value> ] ...``, which
carries the column type the core action does not. That request is refused by
name, and the refusal points at the re-specification path.

Source (grammar and the supported/unsupported action table):

https://docs.snowflake.com/en/sql-reference/sql/alter-table-column

**not server-verified** -- no Snowflake account is configured in this
repository, and the bundled emulator (fakesnow over DuckDB) does not execute
Snowflake's ``ALTER COLUMN`` DDL. The spellings below are transcribed from the
reference page and asserted as renderings, never as measurements.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    AlterTableStatement,
    ColumnConstraint,
    ColumnDefaultConstraint,
    ColumnDefinition,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AlterColumnAction,
    ColumnAlterOperation,
    ModifyColumnAction,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression.sequence import (
    SnowflakeNextvalExpression,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


def _render(dialect, action):
    """Render one action as the single-action ALTER TABLE statement it sits in."""
    return AlterTableStatement(dialect, Table(dialect, "t"), [action]).to_sql()


class TestCapabilityAnswers:
    """Both probes are True: the spellings exist, so the refusals must not."""

    def test_default_probe_is_true(self, dialect):
        assert dialect.supports_alter_column_default() is True

    def test_nullability_probe_is_true(self, dialect):
        assert dialect.supports_alter_column_nullability() is True


class TestRenderedOperations:
    """The spellings Snowflake's grammar carries, rendered through the action."""

    @pytest.mark.parametrize(
        "operation, expected",
        [
            (ColumnAlterOperation.DROP_DEFAULT, 'ALTER COLUMN "c" DROP DEFAULT'),
            (ColumnAlterOperation.SET_NOT_NULL, 'ALTER COLUMN "c" SET NOT NULL'),
            (ColumnAlterOperation.DROP_NOT_NULL, 'ALTER COLUMN "c" DROP NOT NULL'),
        ],
    )
    def test_action_renders_the_documented_spelling(self, dialect, operation, expected):
        sql, params = _render(dialect, AlterColumnAction(dialect, "c", operation))

        assert sql == f'ALTER TABLE "t" {expected}'
        assert params == ()

    def test_set_default_accepts_a_sequence_nextval(self, dialect):
        """``SET DEFAULT`` is the documented spellings' one accepted value."""
        action = AlterColumnAction(
            dialect,
            "c",
            ColumnAlterOperation.SET_DEFAULT,
            new_value=SnowflakeNextvalExpression(dialect, "order_id_seq"),
        )

        sql, params = _render(dialect, action)

        assert sql == (
            'ALTER TABLE "t" ALTER COLUMN "c" '
            'SET DEFAULT "order_id_seq".NEXTVAL'
        )
        assert params == ()

    @pytest.mark.parametrize("operation", ["DROP DEFAULT", "DROP NOT NULL"])
    def test_the_raw_spelling_is_accepted_the_same_way(self, dialect, operation):
        """The action accepts the enum or its spelling; the render is one shape."""
        sql, params = _render(dialect, AlterColumnAction(dialect, "c", operation))

        assert sql == f'ALTER TABLE "t" ALTER COLUMN "c" {operation}'
        assert params == ()

    def test_set_data_type_keeps_its_type_rendering(self, dialect):
        """The override delegates the type action; it does not replace it."""
        action = AlterColumnAction(
            dialect,
            "c",
            ColumnAlterOperation.SET_DATA_TYPE,
            new_value=VarCharType(dialect, length=50),
        )

        sql, params = _render(dialect, action)

        assert sql == 'ALTER TABLE "t" ALTER COLUMN "c" SET DATA TYPE VARCHAR(50)'
        assert params == ()


class TestRefusedRequests:
    """Requests this action cannot spell are refused by name."""

    @pytest.mark.parametrize(
        "factory",
        [
            lambda dialect: Literal(dialect, 5, inline=True),
            lambda dialect: "5",
            lambda dialect: None,
            lambda dialect: SnowflakeNextvalExpression(
                dialect, "order_id_seq", alias="next_id"
            ),
        ],
        ids=["literal", "string", "missing", "aliased-nextval"],
    )
    def test_set_default_without_a_bare_nextval_names_the_respecification(
        self, dialect, factory
    ):
        action = AlterColumnAction(
            dialect,
            "c",
            ColumnAlterOperation.SET_DEFAULT,
            new_value=factory(dialect),
        )

        with pytest.raises(UnsupportedFeatureError) as exc_info:
            _render(dialect, action)

        message = str(exc_info.value)
        assert "ALTER COLUMN SET DEFAULT" in message
        assert "MODIFY COLUMN" in message
        assert "does not carry the column type" in message

    def test_an_operation_the_action_does_not_carry_is_refused_by_name(self, dialect):
        action = AlterColumnAction(dialect, "c", "SET MASKING POLICY")

        with pytest.raises(
            UnsupportedFeatureError, match="ALTER COLUMN SET MASKING POLICY"
        ):
            _render(dialect, action)

    def test_cascade_is_refused(self, dialect):
        action = AlterColumnAction(
            dialect, "c", ColumnAlterOperation.DROP_NOT_NULL, cascade=True
        )

        with pytest.raises(UnsupportedFeatureError, match="ALTER COLUMN CASCADE"):
            _render(dialect, action)


class TestFullRespecificationIsTheAlternative:
    """The path the ``SET DEFAULT`` refusal names must actually render."""

    def test_modify_column_writes_a_number_default(self, dialect):
        action = ModifyColumnAction(
            dialect,
            ColumnDefinition(
                dialect,
                "c",
                IntegerType(dialect),
                constraints=[
                    ColumnConstraint(
                        dialect, branch=ColumnDefaultConstraint(dialect, 42)
                    )
                ],
            ),
        )

        sql, params = _render(dialect, action)

        assert sql == 'ALTER TABLE "t" MODIFY COLUMN "c" INTEGER DEFAULT 42'
        assert params == ()

    def test_modify_column_writes_a_quoted_string_default(self, dialect):
        """A DDL default is written inline; no bind placeholder survives."""
        action = ModifyColumnAction(
            dialect,
            ColumnDefinition(
                dialect,
                "c",
                VarCharType(dialect, length=50),
                constraints=[
                    ColumnConstraint(
                        dialect, branch=ColumnDefaultConstraint(dialect, "abcde")
                    )
                ],
            ),
        )

        sql, params = _render(dialect, action)

        assert sql == (
            'ALTER TABLE "t" MODIFY COLUMN "c" VARCHAR(50) DEFAULT \'abcde\''
        )
        assert params == ()
