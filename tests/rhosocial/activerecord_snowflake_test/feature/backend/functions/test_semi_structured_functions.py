# tests/rhosocial/activerecord_snowflake_test/feature/backend/functions/test_semi_structured_functions.py
"""Rendering assertions for the semi-structured function factories.

**not server-verified** -- this repository reaches no Snowflake instance, so
every assertion below is a rendering assertion over the documented spellings,
never a measurement. When a live server contradicts a spelling here, change
the spelling, not the test.

The boundary this file pins is the one the function wave draws: a factory
whose function core has classed migrates to that class (``ARRAY_AGG`` is
``ArrayAggregateFunction``, with DISTINCT and the window clauses an aggregate
takes, and an artifact naming ``array_aggregate_function``); a function core
has not classed stays a bare ``FunctionCall`` until core classes it --
``ARRAY_CONSTRUCT`` and ``PARSE_JSON`` are pinned here as the stay-side
witnesses, so a future classing is a visible change to this file rather than
a silent drift.
"""

import pytest

from rhosocial.activerecord.backend.expression.core import Column, FunctionCall
from rhosocial.activerecord.backend.expression.functions.array import (
    ArrayAggregateFunction,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.functions import (
    array_agg,
    array_construct,
    parse_json,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestArrayAggIsTheClassedAggregate:
    """``ARRAY_AGG`` renders through the node core classes for it."""

    def test_the_factory_returns_the_classed_node(self, dialect):
        node = array_agg(dialect, "tags")
        assert isinstance(node, ArrayAggregateFunction)
        assert not isinstance(node, FunctionCall)

    def test_a_bare_string_becomes_a_column_as_before(self, dialect):
        node = array_agg(dialect, "tags")
        assert isinstance(node.operand, Column)
        assert node.operand.name == "tags"

    def test_the_spelling_is_what_the_call_used_to_render(self, dialect):
        sql, params = array_agg(dialect, "tags").to_sql()
        assert sql == 'ARRAY_AGG("tags")'
        assert params == ()

    def test_an_expression_operand_passes_through(self, dialect):
        operand = Column(dialect, "tag", table="rows")
        sql, params = array_agg(dialect, operand).to_sql()
        assert sql == 'ARRAY_AGG("rows"."tag")'
        assert params == ()

    def test_the_aggregate_clauses_render_through_the_node(self, dialect):
        """DISTINCT and the alias are the aggregate capabilities the call lacked."""
        node = array_agg(dialect, "tags").as_("collected")
        sql, _ = node.to_sql()
        assert sql == 'ARRAY_AGG("tags") AS "collected"'

        distinct = ArrayAggregateFunction(
            dialect, array_agg(dialect, "tags").operand, distinct=True
        )
        sql, _ = distinct.to_sql()
        assert sql == 'ARRAY_AGG(DISTINCT "tags")'


class TestTheUnclassedOnesStayCalls:
    """Functions core has not classed keep their bare ``FunctionCall`` shape.

    Each assertion names the function it watches, so a future classing in core
    fails this file by changing a type -- the migration then becomes a
    deliberate edit here rather than a silent drift.
    """

    def test_array_construct_is_still_a_call(self, dialect):
        node = array_construct(dialect, "a", "b")
        assert type(node) is FunctionCall
        sql, params = node.to_sql()
        assert sql == 'ARRAY_CONSTRUCT("a", "b")'
        assert params == ()

    def test_parse_json_is_still_a_call(self, dialect):
        node = parse_json(dialect, "payload")
        assert type(node) is FunctionCall
        sql, params = node.to_sql()
        assert sql == 'PARSE_JSON("payload")'
        assert params == ()
