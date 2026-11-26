# tests/rhosocial/activerecord_snowflake_test/feature/query/snowflake/test_snowflake_explain_deep.py
"""Backend-local, construction-level EXPLAIN tests for the Snowflake dialect.

The shared testsuite contracts only assert that EXPLAIN *can run* against a live
account.  This file covers Snowflake's local EXPLAIN surface without a database:
the capability probes and the SQL that ``format_explain_statement`` renders.

Snowflake's native grammar is ``EXPLAIN [ USING { TABULAR | JSON | TEXT } ]
<statement>``: there is no ``ANALYZE`` / ``FORMAT`` / ``VERBOSE`` tail.  The
dialect leaves core's generic ``ExplainMixin`` in place and declares every
option switch False, so the generic formatter refuses -- by name -- any option
it would otherwise have rendered as PostgreSQL-style SQL the server rejects.

No real-DB result-interpretation test lives here: the only local database is the
fakesnow (DuckDB) emulator, which cannot parse ``EXPLAIN`` at all (it falls back
to ``DESCRIBE`` and raises ``DatabaseError``), and CI has no real account.  A
credential-gated real-account test would always skip today, so the honest
coverage at this layer is construction-level only.
"""

import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    Column,
    ComparisonPredicate,
    Literal,
    QueryStatement,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    ExplainFormat,
    ExplainOptions,
    ExplainStatement,
    ExplainType,
)

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


def _select(dialect):
    """A minimal SELECT statement used as the EXPLAIN target."""
    return QueryStatement(dialect, select=[Column(dialect, "id")], from_=Table(dialect, "users"))


#: Every format switch, paired with the enum member it answers for.
FORMAT_SWITCHES = {
    ExplainFormat.TEXT: "supports_explain_format_text",
    ExplainFormat.JSON: "supports_explain_format_json",
    ExplainFormat.XML: "supports_explain_format_xml",
    ExplainFormat.YAML: "supports_explain_format_yaml",
    ExplainFormat.TREE: "supports_explain_format_tree",
    ExplainFormat.TRADITIONAL: "supports_explain_format_traditional",
}


@pytest.mark.unit
class TestSnowflakeExplainCapabilities:
    """The dialect's EXPLAIN probes state what the Snowflake server accepts."""

    def test_explain_plan_is_available(self, dialect):
        """Snowflake has a row-returning EXPLAIN (the base default stays True)."""
        assert dialect.supports_explain_plan() is True

    def test_explain_capability_is_advertised(self, dialect):
        """SnowflakeCapabilityMixin advertises EXPLAIN explicitly."""
        assert dialect.supports_explain() is True

    def test_analyze_is_not_advertised(self, dialect):
        """Snowflake's EXPLAIN grammar has no ANALYZE keyword."""
        assert dialect.supports_explain_analyze() is False

    @pytest.mark.parametrize("fmt", list(ExplainFormat))
    def test_structured_formats_are_not_advertised(self, dialect, fmt):
        """No ExplainFormat value is advertised.

        Snowflake spells its output formats ``USING TEXT`` / ``USING JSON``;
        the shared formatter would emit ``FORMAT <NAME>``, so no enum member,
        including ``TABULAR``, maps to a renderable Snowflake option.
        """
        assert getattr(dialect, FORMAT_SWITCHES[fmt])() is False

    @pytest.mark.parametrize(
        "probe",
        [
            "supports_explain_verbose",
            "supports_explain_costs",
            "supports_explain_buffers",
            "supports_explain_timing",
            "supports_explain_settings",
            "supports_explain_wal",
        ],
    )
    def test_postgres_style_tails_are_not_advertised(self, dialect, probe):
        """None of the generic formatter's tail options is Snowflake syntax."""
        assert getattr(dialect, probe)() is False


@pytest.mark.unit
class TestSnowflakeExplainRendering:
    """Construction-level rendering by the inherited generic ExplainMixin."""

    def test_basic_explain_renders_prefix(self, dialect):
        """A bare EXPLAIN wraps the statement with no option clauses."""
        sql, params = ExplainStatement(dialect, _select(dialect)).to_sql()
        assert sql == 'EXPLAIN SELECT "id" FROM "users"'
        assert params == ()

    def test_explicit_empty_options_render_like_bare_explain(self, dialect):
        """``ExplainOptions()`` (all defaults) adds no clauses."""
        sql, params = ExplainStatement(dialect, _select(dialect), ExplainOptions()).to_sql()
        assert sql == 'EXPLAIN SELECT "id" FROM "users"'
        assert params == ()

    def test_query_plan_type_falls_back_to_plain_explain(self, dialect):
        """``type=QUERY_PLAN`` has no Snowflake spelling; plain EXPLAIN is kept.

        Unlike SQLite, Snowflake has no ``EXPLAIN QUERY PLAN`` form, and the
        generic formatter only special-cases ``ExplainType.ANALYZE``.  The
        QUERY_PLAN type therefore renders the same SQL as a bare EXPLAIN.
        """
        options = ExplainOptions(type=ExplainType.QUERY_PLAN)
        sql, _ = ExplainStatement(dialect, _select(dialect), options).to_sql()
        assert sql == 'EXPLAIN SELECT "id" FROM "users"'

    def test_inner_statement_parameters_are_preserved(self, dialect):
        """The explained statement's bound params survive the EXPLAIN wrapper."""
        inner = QueryStatement(
            dialect,
            select=[Column(dialect, "id")],
            from_=Table(dialect, "users"),
            where=ComparisonPredicate(dialect, ">", Column(dialect, "age"), Literal(dialect, 18)),
        )
        sql, params = ExplainStatement(dialect, inner).to_sql()
        assert sql == 'EXPLAIN SELECT "id" FROM "users" WHERE "age" > %s'
        assert params == (18,)

    def test_analyze_option_is_refused(self, dialect):
        """``analyze=True`` has no Snowflake spelling and is named in the error."""
        with pytest.raises(UnsupportedFeatureError):
            ExplainStatement(dialect, _select(dialect), ExplainOptions(analyze=True)).to_sql()

    def test_every_requested_format_is_refused(self, dialect):
        """A requested ``FORMAT`` is invalid Snowflake syntax, so it is refused."""
        for fmt in ExplainFormat:
            options = ExplainOptions(format=fmt)
            with pytest.raises(UnsupportedFeatureError):
                ExplainStatement(dialect, _select(dialect), options).to_sql()

    def test_costs_off_is_refused(self, dialect):
        """``costs=False`` would render ``COSTS OFF``; Snowflake has no such option."""
        options = ExplainOptions(costs=False)
        with pytest.raises(UnsupportedFeatureError):
            ExplainStatement(dialect, _select(dialect), options).to_sql()

    def test_buffers_is_refused(self, dialect):
        """``buffers=True`` would render ``BUFFERS``; Snowflake has no such option."""
        options = ExplainOptions(buffers=True)
        with pytest.raises(UnsupportedFeatureError):
            ExplainStatement(dialect, _select(dialect), options).to_sql()

    def test_verbose_is_refused(self, dialect):
        """``verbose=True`` would render ``VERBOSE``; Snowflake has no such option."""
        options = ExplainOptions(verbose=True)
        with pytest.raises(UnsupportedFeatureError):
            ExplainStatement(dialect, _select(dialect), options).to_sql()

    def test_settings_is_refused(self, dialect):
        """``settings=True`` would render ``SETTINGS``; Snowflake has no such option."""
        options = ExplainOptions(settings=True)
        with pytest.raises(UnsupportedFeatureError):
            ExplainStatement(dialect, _select(dialect), options).to_sql()

    def test_wal_is_refused(self, dialect):
        """``wal=True`` would render ``WAL``; Snowflake has no such option."""
        options = ExplainOptions(wal=True)
        with pytest.raises(UnsupportedFeatureError):
            ExplainStatement(dialect, _select(dialect), options).to_sql()

    def test_timing_without_analyze_is_ignored(self, dialect):
        """``timing`` only accompanies ``analyze``, which is itself refused.

        Without ``analyze`` the generic formatter never emits ``TIMING``, so
        the default-shaped SQL is still produced.
        """
        options = ExplainOptions(timing=True)
        sql, _ = ExplainStatement(dialect, _select(dialect), options).to_sql()
        assert sql == 'EXPLAIN SELECT "id" FROM "users"'

    def test_all_options_are_refused_at_the_first_clause(self, dialect):
        """The full PostgreSQL option set stops at ``ANALYZE``."""
        options = ExplainOptions(
            analyze=True,
            format=ExplainFormat.JSON,
            costs=False,
            buffers=True,
            timing=True,
            verbose=True,
            settings=True,
            wal=True,
        )
        with pytest.raises(UnsupportedFeatureError):
            ExplainStatement(dialect, _select(dialect), options).to_sql()
