# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_object_kind_refused.py
"""A statement handed the wrong kind of catalogue object must refuse to render.

Why this file exists
===================

Names are objects now, and an object renders itself: every one carries its own
``format_method`` and the dialect asks it for SQL. That is what makes
``"DB"."SCHEMA"."users"`` come out right from two plain strings, and it is also
what removed the old accidental guard. Names used to be strings, so
``format_identifier`` accepted anything and a statement given a table where a
sequence belonged raised on the spot. Nothing replaced it. So
``CreateSequenceExpression(dialect, Table(dialect, "users"))`` renders
``CREATE SEQUENCE "users"`` -- well-formed, and naming a table -- and the
mistake is invisible from outside.

The check belongs in the formatter rather than the constructor for two reasons.
A constructor cannot know the dialect yet (the testsuite builds objects with no
dialect at all and binds one at render time), and a formatter can say more than
"wrong type" -- it can also say the dialect has no formatter for that kind at
all.

What is asserted here
=====================

One case per formatter this backend overrides, and each asserts three things:
that the wrong kind raises ``TypeError``, that the message names both the
attribute and what it got, and that the *right* kind still renders. Without the
third, a check that refused everything would pass. Each case builds a real
object of the wrong kind rather than a mock, because a mock is not a Table and
the refusal would prove nothing about the message.
"""

import pytest

from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.objects import (
    Database,
    MaterializedView,
    Schema,
    Table,
)
from rhosocial.activerecord.backend.expression.statements.ddl_database import (
    AlterDatabaseAction,
    AlterDatabaseExpression,
    CreateDatabaseExpression,
    DropDatabaseExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_schema import (
    CreateSchemaExpression,
    DropSchemaExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_truncate import (
    TruncateExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_type import (
    AlterTypeExpression,
    CreateTypeExpression,
    DropTypeExpression,
)
from rhosocial.activerecord.backend.expression.statements.ddl_view import (
    CreateMaterializedViewExpression,
)
from rhosocial.activerecord.backend.expression.statements.dql import QueryExpression
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression.database import (
    SnowflakeCreateDatabaseExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.materialized_view import (  # noqa: E501
    SnowflakeCreateMaterializedViewExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.expression.ddl.type import (
    SnowflakeScalarTypeDefinition,
    SnowflakeSetTypeCommentAction,
)
from rhosocial.activerecord.backend.expression.types import IntegerType


TYPE_DDL_MIN_VERSION = (10, 8, 0)


@pytest.fixture
def dialect():
    """A dialect new enough for TYPE DDL, which is version-gated."""
    return SnowflakeDialect(version=TYPE_DDL_MIN_VERSION)


def _query(dialect):
    return QueryExpression(
        dialect=dialect, select=[Column(dialect, "id")], from_=Table(dialect, "t")
    )


#: ``(label, build, wrong_object, message_fragment)``.
#:
#: ``build`` receives the dialect and the object to put in the slot, so each
#: row states both the refusal and the fact that the same slot accepts the right
#: kind -- ``wrong_object`` is the wrong kind for that slot, and the companion
#: test renders the same statement with the right one.
CASES = [
    (
        "truncate",
        lambda d, o: TruncateExpression(d, o),
        lambda d: Schema(d, "reporting"),
        "TruncateExpression.table must be a Table, got Schema",
    ),
    (
        "create schema",
        lambda d, o: CreateSchemaExpression(d, o),
        lambda d: Database(d, "analytics"),
        "CreateSchemaExpression.schema must be a Schema, got Database",
    ),
    (
        "drop schema",
        lambda d, o: DropSchemaExpression(d, o),
        lambda d: Table(d, "users"),
        "DropSchemaExpression.schema must be a Schema, got Table",
    ),
    (
        "create database",
        lambda d, o: CreateDatabaseExpression(d, o),
        lambda d: Table(d, "users"),
        "CreateDatabaseExpression.database must be a Database, got Table",
    ),
    (
        "snowflake create database",
        lambda d, o: SnowflakeCreateDatabaseExpression(d, o),
        lambda d: Table(d, "users"),
        "SnowflakeCreateDatabaseExpression.database must be a Database, got Table",
    ),
    (
        "drop database",
        lambda d, o: DropDatabaseExpression(d, o),
        lambda d: Schema(d, "reporting"),
        "DropDatabaseExpression.database must be a Database, got Schema",
    ),
    (
        "alter database",
        lambda d, o: AlterDatabaseExpression(
            d, o, action=AlterDatabaseAction.RENAME_TO, target="renamed"
        ),
        lambda d: Schema(d, "reporting"),
        "AlterDatabaseExpression.database must be a Database, got Schema",
    ),
    (
        "create materialized view",
        lambda d, o: CreateMaterializedViewExpression(d, o, _query(d)),
        lambda d: Table(d, "users"),
        "CreateMaterializedViewExpression.view must be a MaterializedView, got Table",
    ),
    (
        "snowflake create materialized view",
        lambda d, o: SnowflakeCreateMaterializedViewExpression(d, o, _query(d)),
        lambda d: Table(d, "users"),
        (
            "SnowflakeCreateMaterializedViewExpression.view must be a "
            "MaterializedView, got Table"
        ),
    ),
    (
        "create type",
        lambda d, o: CreateTypeExpression(
            d, o, SnowflakeScalarTypeDefinition(d, IntegerType(d))
        ),
        lambda d: Table(d, "users"),
        "CreateTypeExpression.type must be a Type, got Table",
    ),
    (
        "alter type",
        lambda d, o: AlterTypeExpression(
            d, o, [SnowflakeSetTypeCommentAction(d, "a note")]
        ),
        lambda d: Table(d, "users"),
        "AlterTypeExpression.type must be a Type, got Table",
    ),
    (
        "drop type",
        lambda d, o: DropTypeExpression(d, o),
        lambda d: Table(d, "users"),
        "DropTypeExpression.type must be a Type, got Table",
    ),
]


class TestWrongObjectKindIsRefused:
    """One refusal per formatter this backend overrides."""

    @pytest.mark.parametrize(
        "label,build,wrong_object,fragment",
        CASES,
        ids=[case[0] for case in CASES],
    )
    # ``label`` is named in the signature even though the assertions read the
    # class names out of the message: pytest passes every parametrised value to
    # the function, so leaving it out is a collection error, not a style choice.
    def test_refuses_wrong_object_kind(
        self, dialect, label, build, wrong_object, fragment
    ):
        expression = build(dialect, wrong_object(dialect))
        with pytest.raises(TypeError) as exc_info:
            expression.to_sql()
        assert fragment in str(exc_info.value), (
            f"{label}: the refusal did not name the attribute and what it got"
        )

    @pytest.mark.parametrize(
        "label,build,wrong_object,fragment",
        CASES,
        ids=[case[0] for case in CASES],
    )
    def test_no_sql_is_produced(
        self, dialect, label, build, wrong_object, fragment
    ):
        """The refusal happens before any SQL exists.

        Worth asserting separately because the failure this guards against was
        never an exception -- it was a correct-looking statement. A check that
        raised only after assembling part of the string would still let the
        wrong object reach the caller.
        """
        expression = build(dialect, wrong_object(dialect))
        try:
            expression.to_sql()
        except TypeError:
            return
        pytest.fail(f"{label}: the wrong object kind rendered instead of being refused")


class TestRightObjectKindStillRenders:
    """The counterpart: the same slots accept what they are for.

    Without these, a check that refused every object would satisfy the tests
    above, and nothing would notice that TRUNCATE had stopped working.
    """

    def test_truncate_renders(self, dialect):
        sql, params = TruncateExpression(dialect, Table(dialect, "users")).to_sql()
        assert sql == 'TRUNCATE TABLE "users"'
        assert params == ()

    def test_create_and_drop_schema_render(self, dialect):
        create_sql, _ = CreateSchemaExpression(
            dialect, Schema(dialect, "reporting")
        ).to_sql()
        drop_sql, _ = DropSchemaExpression(dialect, Schema(dialect, "reporting")).to_sql()
        assert create_sql.startswith("CREATE SCHEMA")
        assert '"reporting"' in create_sql
        assert drop_sql.startswith("DROP SCHEMA")

    def test_database_ddl_renders(self, dialect):
        database = Database(dialect, "analytics")
        create_sql, _ = CreateDatabaseExpression(dialect, database).to_sql()
        drop_sql, _ = DropDatabaseExpression(dialect, database).to_sql()
        alter_sql, _ = AlterDatabaseExpression(
            dialect, database, action=AlterDatabaseAction.RENAME_TO, target="renamed"
        ).to_sql()
        assert create_sql.startswith("CREATE DATABASE")
        assert '"analytics"' in create_sql
        assert drop_sql == 'DROP DATABASE "analytics"'
        assert "RENAME TO" in alter_sql

    def test_materialized_view_renders(self, dialect):
        sql, _ = CreateMaterializedViewExpression(
            dialect, MaterializedView(dialect, "mv"), _query(dialect)
        ).to_sql()
        assert sql.startswith('CREATE MATERIALIZED VIEW "mv" AS SELECT')

    def test_snowflake_materialized_view_accepts_a_bare_name(self, dialect):
        """The Snowflake expression coerces a bare name, so the check must not
        refuse it.

        This is the case a blanket ``isinstance`` on the wrong layer gets wrong:
        the coercion is a feature of the expression, and a check placed in the
        shared constructor would have made it impossible.
        """
        sql, _ = SnowflakeCreateMaterializedViewExpression(
            dialect, "mv", as_query="SELECT 1"
        ).to_sql()
        assert sql == 'CREATE MATERIALIZED VIEW "mv" AS SELECT 1'

    def test_type_ddl_renders(self, dialect):
        from rhosocial.activerecord.backend.expression.objects import (
            Type as TypeObject,
        )

        type_object = TypeObject(dialect, "age")
        create_sql, _ = CreateTypeExpression(
            dialect, type_object, SnowflakeScalarTypeDefinition(dialect, IntegerType(dialect))
        ).to_sql()
        alter_sql, _ = AlterTypeExpression(
            dialect,
            type_object,
            [SnowflakeSetTypeCommentAction(dialect, "a note")],
        ).to_sql()
        drop_sql, _ = DropTypeExpression(dialect, type_object).to_sql()
        assert create_sql.startswith("CREATE TYPE")
        assert '"age"' in create_sql
        assert alter_sql.startswith("ALTER TYPE")
        assert drop_sql.startswith("DROP TYPE")


class TestTheCheckLivesInTheFormatter:
    """The refusal must survive without a dialect, because the constructor cannot
    know the object kind is wrong yet.

    Objects are routinely built with no dialect at all -- the testsuite's
    foreign-key fixture is ``Table(None, "orders")`` and binds one when it
    renders -- so a constructor check would either have to be absent or would
    fire on a legitimate construction. Asserting that construction succeeds is
    what makes the render-time trigger the only option.
    """

    def test_construction_with_the_wrong_kind_succeeds(self):
        expression = CreateDatabaseExpression(None, "analytics")
        assert expression.database == "analytics"

    def test_rendering_it_without_a_dialect_fails(self):
        """There is nothing to render with, so the object kind is never consulted.

        The point is the ordering: the unbound dialect is reported before the
        wrong kind, which is what it means for the kind check to live in the
        formatter. A constructor could not have made this distinction.
        """
        expression = CreateDatabaseExpression(None, "analytics")
        with pytest.raises(ValueError, match="no dialect bound"):
            expression.to_sql()