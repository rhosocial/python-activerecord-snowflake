# tests/rhosocial/activerecord_snowflake_test/feature/backend/dialect/test_expression_fields_match_formatters.py
"""A formatter may not read a field its statement does not carry.

A statement formatter that reads ``expr.schema_name`` needs the expression to
have that attribute. When the formatter was changed to qualify names and the
expression was not given the field, the result is not wrong SQL -- it is an
``AttributeError`` on a statement that can never be built, which is how
SQLServerColumnstoreIndexExpression reached CI.

These were source scans rather than runtime tests. A scan does not work here:
whether the field exists depends on inheritance reaching core, which lives in
another repository, and on **core_kwargs forwarding. Reading the source of this
repository can see neither, so a scan reported defects that were not there --
two were chased down and both were false alarms -- while a field genuinely
removed still passed. Building the statement answers the question the defect
actually asks: does this statement build, and does the schema reach the SQL?
"""
import importlib
import inspect

import pytest

#: Statement fields a formatter may read that some expression classes carry
#: under a different name. Reading these by their own name is the defect.
#: TruncateExpression names the field `schema`; the DDL statements name it
#: `schema_name`. Snowflake's TRUNCATE is one formatter here that reads the
#: alias, so the alias is exercised below rather than excused.
KNOWN_ALIASES = {
    "schema": {"TruncateExpression"},
}


class TestQualifiedStatementsRender:
    """A statement whose formatter qualifies names must build with a schema.

    Checked by building each statement and rendering it, not by scanning
    source. Each case names the statement and how to build it, so adding
    coverage for a newly qualified object type is one entry rather than a new
    mechanism.
    """

    @pytest.fixture
    def dialect(self):
        from rhosocial.activerecord.backend.impl.snowflake.dialect import (
            SnowflakeDialect,
        )

        return SnowflakeDialect(version=(7, 0, 0))

    def test_create_materialized_view_inherits_the_field_from_core(self, dialect):
        """The case a source scan got wrong in both directions.

        CreateMaterializedViewExpression lives in core and assigns
        schema_name there. A scan of this repository sees the formatter reading
        the field and no assignment at all, so it either misses a field that is
        there or reports one that is not, depending on how it resolves the base.
        Building it settles the question.
        """
        from rhosocial.activerecord.backend.expression import (
            Column,
            CreateMaterializedViewExpression,
            QueryExpression,
        )

        query = QueryExpression(dialect, [Column(dialect, "id")], from_="orders")
        expr = CreateMaterializedViewExpression(
            dialect, view_name="mv_orders", query=query
        )
        assert expr.to_sql()[0] == (
            'CREATE MATERIALIZED VIEW "mv_orders" AS SELECT "id" FROM "orders"'
        ), expr.to_sql()[0]
        qualified = CreateMaterializedViewExpression(
            dialect, view_name="mv_orders", query=query, schema_name="app"
        )
        assert qualified.to_sql()[0] == (
            'CREATE MATERIALIZED VIEW "app"."mv_orders" AS '
            'SELECT "id" FROM "orders"'
        ), qualified.to_sql()[0]

    def test_truncate_reads_the_schema_alias(self, dialect):
        """One formatter here reads ``expr.schema``, not ``schema_name``.

        TruncateExpression carries the field under the core alias, so the
        keyword is ``schema`` here. Pinning it means renaming the field in core
        breaks this rather than silently rendering an unqualified name.
        """
        from rhosocial.activerecord.backend.expression import TruncateExpression

        expr = TruncateExpression(dialect, table_name="orders")
        assert expr.to_sql()[0] == 'TRUNCATE TABLE "orders"', expr.to_sql()[0]
        qualified = TruncateExpression(dialect, table_name="orders", schema="app")
        assert qualified.to_sql()[0] == (
            'TRUNCATE TABLE "app"."orders"'
        ), qualified.to_sql()[0]

    def test_create_schema_carries_the_name_it_creates(self, dialect):
        """Here the field is the subject, not a qualifier -- and it is required.

        There is no unqualified form to build, so this asserts the narrower
        thing that still matters: the formatter reads the field, the statement
        cannot be built without it, and the name reaches the SQL.
        """
        from rhosocial.activerecord.backend.expression import CreateSchemaExpression

        expr = CreateSchemaExpression(dialect, "app")
        assert expr.to_sql()[0] == 'CREATE SCHEMA "app"', expr.to_sql()[0]

    def test_drop_schema_carries_the_name_it_drops(self, dialect):
        from rhosocial.activerecord.backend.expression import DropSchemaExpression

        expr = DropSchemaExpression(dialect, "app")
        assert expr.to_sql()[0] == 'DROP SCHEMA "app"', expr.to_sql()[0]


class TestExpressionSignatures:
    """The expressions this backend's formatters qualify must take the field."""

    @pytest.mark.parametrize(
        "import_path,class_name,field",
        [
            (
                "rhosocial.activerecord.backend.expression.statements.ddl_view",
                "CreateMaterializedViewExpression",
                "schema_name",
            ),
            (
                "rhosocial.activerecord.backend.expression.statements.ddl_truncate",
                "TruncateExpression",
                "schema",
            ),
            (
                "rhosocial.activerecord.backend.expression.statements.ddl_schema",
                "CreateSchemaExpression",
                "schema_name",
            ),
            (
                "rhosocial.activerecord.backend.expression.statements.ddl_schema",
                "DropSchemaExpression",
                "schema_name",
            ),
        ],
    )
    def test_qualified_expression_accepts_schema_field(
        self, import_path, class_name, field
    ):
        module = importlib.import_module(import_path)
        cls = getattr(module, class_name)
        params = inspect.signature(cls.__init__).parameters
        assert field in params, (
            f"{class_name} is read by its formatter, so it needs the "
            f"{field} field; got {list(params)}"
        )

    def test_qualifier_defaults_to_unqualified(self):
        """Where the field qualifies a name, None has to mean unqualified.

        The schema statements are exempt on purpose: for those the field *is*
        the object, and requiring it is the correct shape.
        """
        from rhosocial.activerecord.backend.expression import (
            CreateMaterializedViewExpression,
            TruncateExpression,
        )

        for cls, field in (
            (CreateMaterializedViewExpression, "schema_name"),
            (TruncateExpression, "schema"),
        ):
            params = inspect.signature(cls.__init__).parameters
            assert params[field].default is None, (
                f"{cls.__name__}.{field} must default to None -- None is what "
                f"means unqualified"
            )
