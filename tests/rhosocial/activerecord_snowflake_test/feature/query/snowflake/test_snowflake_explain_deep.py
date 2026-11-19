# tests/rhosocial/activerecord_snowflake_test/feature/query/snowflake/test_snowflake_explain_deep.py
"""Backend-local, construction-level EXPLAIN tests for the Snowflake dialect.

The shared testsuite contracts only assert that EXPLAIN *can run* against a live
account.  This file covers Snowflake's local EXPLAIN surface without a database:
the capability probes and the SQL that ``format_explain_statement`` renders.

Snowflake's native grammar is ``EXPLAIN [ USING { TABULAR | TEXT } ] <query>``:
there is no ``ANALYZE`` / ``FORMAT`` / ``VERBOSE`` tail.  The dialect leaves
core's generic ``ExplainMixin`` in place, whose probes answer False for
``supports_explain_analyze()`` and ``supports_explain_format()``.  Callers must
consult those probes before passing PostgreSQL-style options.  The option
rendering tests below pin the *inherited generic renderer's* exact output so a
future Snowflake-specific renderer change is caught rather than silently
changing the generated SQL.

No real-DB result-interpretation test lives here: the only local database is the
fakesnow (DuckDB) emulator, which cannot parse ``EXPLAIN`` at all (it falls back
to ``DESCRIBE`` and raises ``DatabaseError``), and CI has no real account.  A
credential-gated real-account test would always skip today, so the honest
coverage at this layer is construction-level only.
"""

import pytest
from rhosocial.activerecord.backend.expression import Column, QueryStatement, RawSQL
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
        """Snowflake's EXPLAIN grammar has no ANALYZE keyword.

        The dialect keeps core's generic ExplainMixin, whose default probe is
        False.  Callers must gate on this before passing ``analyze=True``.
        """
        assert dialect.supports_explain_analyze() is False

    @pytest.mark.parametrize("fmt", list(ExplainFormat))
    def test_structured_formats_are_not_advertised(self, dialect, fmt):
        """No ExplainFormat value is advertised.

        Snowflake's ``USING TABULAR`` / ``USING TEXT`` are not modelled by
        ``supports_explain_format`` and the generic probe answers False for
        every enum member, including a raw ``TABULAR`` string.
        """
        assert dialect.supports_explain_format(fmt) is False

    def test_tabular_string_is_not_advertised(self, dialect):
        """The raw Snowflake ``TABULAR`` format keyword still answers False."""
        assert dialect.supports_explain_format("TABULAR") is False


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
        inner = RawSQL(dialect, 'SELECT "id" FROM "users" WHERE "age" > %s', (18,))
        sql, params = ExplainStatement(dialect, inner).to_sql()
        assert sql == 'EXPLAIN SELECT "id" FROM "users" WHERE "age" > %s'
        assert params == (18,)

    def test_analyze_option_renders_analyze_clause(self, dialect):
        """``analyze=True`` is echoed as ``ANALYZE`` by the generic renderer.

        The capability probe above reports ANALYZE unsupported; this test pins
        the inherited renderer's behaviour, not an endorsement of the syntax.
        """
        sql, _ = ExplainStatement(dialect, _select(dialect), ExplainOptions(analyze=True)).to_sql()
        assert sql == 'EXPLAIN ANALYZE SELECT "id" FROM "users"'

    def test_format_option_renders_format_clause(self, dialect):
        """A requested format is echoed as ``FORMAT <NAME>`` verbatim."""
        options = ExplainOptions(format=ExplainFormat.JSON)
        sql, _ = ExplainStatement(dialect, _select(dialect), options).to_sql()
        assert sql == 'EXPLAIN FORMAT JSON SELECT "id" FROM "users"'

    def test_costs_off_and_verbose_render(self, dialect):
        """``costs=False`` and ``verbose=True`` produce their generic clauses."""
        options = ExplainOptions(costs=False, verbose=True)
        sql, _ = ExplainStatement(dialect, _select(dialect), options).to_sql()
        assert sql == 'EXPLAIN COSTS OFF VERBOSE SELECT "id" FROM "users"'

    def test_all_options_render_in_documented_order(self, dialect):
        """The full option set renders in the generic formatter's fixed order.

        Pinning the exact string makes any change to the inherited renderer
        explicit.  None of these PostgreSQL-style clauses are valid Snowflake
        syntax; the capability probes are the authority on what to pass.
        """
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
        sql, params = ExplainStatement(dialect, _select(dialect), options).to_sql()
        assert sql == (
            "EXPLAIN ANALYZE FORMAT JSON COSTS OFF BUFFERS TIMING ON VERBOSE "
            'SETTINGS WAL SELECT "id" FROM "users"'
        )
        assert params == ()
