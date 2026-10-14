# tests/rhosocial/activerecord_snowflake_test/feature/backend/expression/test_snowflake_wildcards.py
"""Snowflake's two wildcard spellings: the filter and the qualified row count.

Core splits the asterisk by grammar position (spec 4.10).  Snowflake then adds a
filter to both positions and a qualifier to the row-count one, transcribed from

  https://docs.snowflake.com/en/sql-reference/functions/count
  https://docs.snowflake.com/en/sql-reference/sql/select

**not server-verified.**  There is no Snowflake instance reachable from this
repository; every assertion below is a rendering assertion over the transcribed
grammar, never a measurement.  The reference pages are quoted in the node's and
the mixin's docstrings; the ``SELECT`` page's own worked examples are the fixtures
where a spelling could be got wrong (``* EXCLUDE department_id``,
``* EXCLUDE (department_id, employee_id)``, ``* ILIKE '%id%'``,
``COUNT(n.*)``).
"""

import pytest

from rhosocial.activerecord.backend.expression.core import (
    AllColumnsWildcard,
    RowCountWildcard,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeAllColumnsWildcard,
    SnowflakeRowCountWildcard,
)
from rhosocial.activerecord.backend.impl.snowflake.mixins.wildcard import (
    SnowflakeWildcardMixin,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


def _relation(dialect, name="employee_table", alias=None, schema_name=None):
    table = Table(dialect, name, schema_name=schema_name)
    return NamedRelationRef(dialect, table, alias=alias)


class TestCoreFormsAreUnchanged:
    """The override exists for the filter, not for the bare asterisk."""

    def test_bare_all_columns(self, dialect):
        assert AllColumnsWildcard(dialect).to_sql() == ("*", ())

    def test_bare_row_count(self, dialect):
        assert RowCountWildcard(dialect).to_sql() == ("*", ())

    def test_core_qualified_all_columns_still_renders(self, dialect):
        node = AllColumnsWildcard(dialect, relation=_relation(dialect, alias="e"))
        assert node.to_sql() == ('"e".*', ())

    def test_an_unfiltered_snowflake_node_is_the_core_spelling(self, dialect):
        """The derived node with no filter is byte-identical to core's."""
        assert SnowflakeAllColumnsWildcard(dialect).to_sql() == ("*", ())
        assert SnowflakeRowCountWildcard(dialect).to_sql() == ("*", ())


class TestAllColumnsFilters:
    """``SELECT * ILIKE ...`` / ``SELECT * EXCLUDE ...`` -- the SELECT grammar."""

    def test_ilike_pattern(self, dialect):
        node = SnowflakeAllColumnsWildcard(dialect, ilike="%id%")
        assert node.to_sql() == ("* ILIKE '%id%'", ())

    def test_ilike_single_character_wildcards_survive(self, dialect):
        """``_`` and ``%`` are the pattern's own metacharacters, not quoting."""
        node = SnowflakeAllColumnsWildcard(dialect, ilike="col_%")
        assert node.to_sql() == ("* ILIKE 'col_%'", ())

    def test_exclude_one_column_is_unparenthesised(self, dialect):
        """``* EXCLUDE department_id`` -- the page's own single-name spelling."""
        node = SnowflakeAllColumnsWildcard(dialect, exclude="department_id")
        assert node.to_sql() == ('* EXCLUDE "department_id"', ())

    def test_exclude_several_columns_is_parenthesised(self, dialect):
        """``* EXCLUDE (department_id, employee_id)`` -- the page's list spelling."""
        node = SnowflakeAllColumnsWildcard(
            dialect, exclude=["department_id", "employee_id"]
        )
        assert node.to_sql() == ('* EXCLUDE ("department_id", "employee_id")', ())

    def test_exclude_rides_a_qualified_wildcard(self, dialect):
        """``table_a.* EXCLUDE column_in_table_a`` -- the join example."""
        node = SnowflakeAllColumnsWildcard(
            dialect,
            relation=_relation(dialect, "employee_table", alias="employee_table"),
            exclude="department_id",
        )
        assert node.to_sql() == ('"employee_table".* EXCLUDE "department_id"', ())

    def test_qualified_ilike_rides_the_alias(self, dialect):
        node = SnowflakeAllColumnsWildcard(
            dialect,
            relation=_relation(dialect, "employee_table", alias="e"),
            ilike="%name%",
        )
        assert node.to_sql() == ('"e".* ILIKE \'%name%\'', ())

    def test_a_pattern_with_a_quote_is_escaped(self, dialect):
        node = SnowflakeAllColumnsWildcard(dialect, ilike="a'b%")
        sql, _ = node.to_sql()
        assert sql == "* ILIKE 'a''b%'"


class TestRowCountFiltersAndQualifier:
    """``COUNT(<alias>.*)`` -- a different number from ``COUNT(*)``."""

    def test_qualified_row_count(self, dialect):
        """The page's own example: ``SELECT COUNT(n.*) FROM basic_example AS n``."""
        node = SnowflakeRowCountWildcard(
            dialect, relation=_relation(dialect, "basic_example", alias="n")
        )
        assert node.to_sql() == ('"n".*', ())

    def test_qualified_row_count_uses_the_relation_name_without_an_alias(self, dialect):
        node = SnowflakeRowCountWildcard(dialect, relation=_relation(dialect))
        assert node.to_sql() == ('"employee_table".*', ())

    def test_qualified_row_count_with_a_filter(self, dialect):
        node = SnowflakeRowCountWildcard(
            dialect, relation=_relation(dialect, alias="e"), exclude="department_id"
        )
        assert node.to_sql() == ('"e".* EXCLUDE "department_id"', ())

    def test_the_two_counts_are_different_nodes(self, dialect):
        """Why this is a derived node and not a flag on core's.

        ``COUNT(*)`` counts every record; ``COUNT(t.*)`` counts the records with
        no NULL.  Two different numbers, so two different nodes -- the same
        reasoning PostgreSQL's own row-count wildcard is derived under.
        """
        assert not isinstance(SnowflakeRowCountWildcard(dialect), AllColumnsWildcard)
        assert RowCountWildcard(dialect).to_sql() == ("*", ())
        assert SnowflakeRowCountWildcard(
            dialect, relation=_relation(dialect, alias="n")
        ).to_sql() == ('"n".*', ())


class TestFilterCombinationsAreRefused:
    """The two keywords cannot be combined, and the node refuses it by name."""

    @pytest.mark.parametrize("cls", (SnowflakeAllColumnsWildcard, SnowflakeRowCountWildcard))
    def test_ilike_with_exclude_is_refused(self, dialect, cls):
        with pytest.raises(ValueError) as exc_info:
            cls(dialect, ilike="%id%", exclude="department_id")
        assert "can't be combined" in str(exc_info.value)

    @pytest.mark.parametrize("cls", (SnowflakeAllColumnsWildcard, SnowflakeRowCountWildcard))
    def test_non_string_pattern_is_refused(self, dialect, cls):
        with pytest.raises(TypeError):
            cls(dialect, ilike=42)

    @pytest.mark.parametrize("cls", (SnowflakeAllColumnsWildcard, SnowflakeRowCountWildcard))
    def test_non_string_exclude_member_is_refused(self, dialect, cls):
        with pytest.raises(TypeError):
            cls(dialect, exclude=["ok", 3])

    @pytest.mark.parametrize("cls", (SnowflakeAllColumnsWildcard, SnowflakeRowCountWildcard))
    def test_empty_filter_shapes_are_refused(self, dialect, cls):
        with pytest.raises(ValueError):
            cls(dialect, ilike="")
        with pytest.raises(ValueError):
            cls(dialect, exclude=[])
        with pytest.raises(TypeError):
            cls(dialect, exclude=3)


class TestTheMixinDelegatesCoreForms:
    """The override is class-tested, never an attribute probe."""

    def test_the_mixin_declares_both_formatters(self):
        assert "format_all_columns_wildcard" in vars(SnowflakeWildcardMixin)
        assert "format_row_count_wildcard" in vars(SnowflakeWildcardMixin)

    def test_delegation_does_not_probe_for_a_missing_attribute(self, dialect):
        """Core's nodes have no ``ilike`` at all, and are still rendered.

        The rule 9.8 objection to ``getattr(expr, 'ilike', None)`` is that it
        would make a core node answer a question it cannot have; the class test
        is what keeps the two paths apart, and this asserts the core path works
        through the dialect (not just through ``to_sql``).
        """
        assert dialect.format_all_columns_wildcard(AllColumnsWildcard(dialect)) == ("*", ())
        assert dialect.format_row_count_wildcard(RowCountWildcard(dialect)) == ("*", ())

    def test_the_dialect_renders_the_snowflake_nodes(self, dialect):
        assert dialect.format_all_columns_wildcard(
            SnowflakeAllColumnsWildcard(dialect, ilike="%id%")
        ) == ("* ILIKE '%id%'", ())
        assert dialect.format_row_count_wildcard(
            SnowflakeRowCountWildcard(
                dialect, relation=_relation(dialect, alias="n")
            )
        ) == ('"n".*', ())


class TestWildcardInASelectList:
    """The nodes render where a query actually puts them."""

    def test_select_star_ilike(self, dialect):
        from rhosocial.activerecord.backend.expression.statements.dql import (
            QueryStatement,
        )

        query = QueryStatement(
            dialect,
            select=[SnowflakeAllColumnsWildcard(dialect, ilike="%id%")],
            from_=_relation(dialect, "employee_table"),
        )
        sql, params = query.to_sql()
        assert sql == 'SELECT * ILIKE \'%id%\' FROM "employee_table"'
        assert params == ()

    def test_count_of_the_qualified_row_count(self, dialect):
        """The node renders the qualified form when the node is what renders.

        Note the reachability: core's shared ``format_function_call`` special-cases
        a ``RowCountWildcard`` argument to the bare asterisk *before* consulting
        any formatter, so a ``FunctionCall(dialect, "COUNT", qualified)`` still
        renders ``COUNT(*)`` on this core.  The qualified spelling is therefore
        reachable by rendering the node (or by a clause that dispatches to it),
        not through the aggregate's factory -- the same gap PostgreSQL's own
        row-count wildcard has.  Fixing it means changing core's shared formatter,
        which is outside this branch; it is pinned below so the day it changes
        fails here instead of passing quietly.
        """
        node = SnowflakeRowCountWildcard(
            dialect, relation=_relation(dialect, "basic_example", alias="n")
        )
        assert node.to_sql() == ('"n".*', ())
        assert dialect.format_row_count_wildcard(node) == ('"n".*', ())

    def test_count_star_is_still_the_bare_asterisk(self, dialect):
        from rhosocial.activerecord.backend.expression.core import FunctionCall

        sql, params = FunctionCall(
            dialect, "COUNT", RowCountWildcard(dialect)
        ).to_sql()
        assert sql == "COUNT(*)"
        assert params == ()

    def test_the_aggregate_factory_masks_the_qualified_form(self, dialect):
        """Pins core's special case, so the gap above is visible rather than lost.

        ``format_function_call`` answers ``COUNT(<any RowCountWildcard>)`` with the
        bare asterisk, and the Snowflake node is a subclass.  That is core's
        behaviour on every backend with a derived row-count node; this asserts it
        rather than pretending the preferred spelling is reached, so a change in
        core moves this test rather than silently changing what Snowflake emits.
        """
        from rhosocial.activerecord.backend.expression.core import FunctionCall

        node = SnowflakeRowCountWildcard(
            dialect, relation=_relation(dialect, "basic_example", alias="n")
        )
        assert FunctionCall(dialect, "COUNT", node).to_sql() == ("COUNT(*)", ())
        assert node.to_sql() == ('"n".*', ())
