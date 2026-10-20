# tests/rhosocial/activerecord_snowflake_test/feature/backend/expression/test_snowflake_nextval.py
"""``<sequence>.NEXTVAL`` -- the node, and the statement that reads it.

Snowflake reads a sequence's next value as a pseudo-column on the sequence
(`seq.nextval`), which is neither the SQL-standard ``NEXT VALUE FOR seq`` nor
PostgreSQL's ``nextval('seq')`` function form. The node exists so that the
value can be named and read without any layer spelling SQL by hand.

**not server-verified** -- there is no Snowflake instance reachable from this
repository; the spelling below is transcribed from the official page and
checked as a rendering assertion, never a measurement.

https://docs.snowflake.com/en/sql-reference/functions/nextval
"""

import pytest

from rhosocial.activerecord.backend.expression.statements.dql import QueryStatement
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression.sequence import (
    SnowflakeNextvalExpression,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect()


class TestNextvalRendering:
    def test_the_pseudo_column_is_named(self, dialect):
        sql, params = SnowflakeNextvalExpression(dialect, "order_id_seq").to_sql()
        assert sql == '"order_id_seq".NEXTVAL'
        assert params == ()

    def test_the_alias_rides_along(self, dialect):
        sql, params = SnowflakeNextvalExpression(
            dialect, "order_id_seq", alias="next_id"
        ).to_sql()
        assert sql == '"order_id_seq".NEXTVAL AS "next_id"'
        assert params == ()

    def test_the_name_is_quoted_once_by_the_dialect(self, dialect):
        # A name that needs quoting is the dialect's business, not the node's.
        sql, _ = SnowflakeNextvalExpression(dialect, "My Seq").to_sql()
        assert sql == '"My Seq".NEXTVAL'

    def test_an_empty_name_is_refused_at_construction(self, dialect):
        with pytest.raises(ValueError, match="non-empty sequence name"):
            SnowflakeNextvalExpression(dialect, "")


class TestNextvalInAQuery:
    def test_it_is_a_projection_and_renders_through_its_query(self, dialect):
        query = QueryStatement(
            dialect,
            select=[
                SnowflakeNextvalExpression(dialect, "order_id_seq", alias="next_id")
            ],
        )
        sql, params = query.to_sql()
        assert sql == 'SELECT "order_id_seq".NEXTVAL AS "next_id"'
        assert params == ()
