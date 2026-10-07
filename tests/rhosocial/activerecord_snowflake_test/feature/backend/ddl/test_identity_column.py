# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_identity_column.py
"""Snowflake identity columns render Snowflake's ``IDENTITY`` property.

Why this file exists
====================

Snowflake's column property is ``{ AUTOINCREMENT | IDENTITY }`` with an
optional ``( start_num , step_num )`` pair (or the ``START <num> INCREMENT
<num>`` spelling) and an optional ``ORDER | NOORDER`` tail. The two keywords
are synonyms. There is no ``GENERATED { ALWAYS | BY DEFAULT } AS IDENTITY``
form, no MINVALUE, no MAXVALUE, no CYCLE and no CACHE, and the bare marker is
spelled ``AUTOINCREMENT`` -- one word, no underscore -- not ``AUTO_INCREMENT``.

This dialect renders the parameterised ``IDENTITY(seed, step)`` spelling and
declares the capability probes that decide which parts of the request it can
carry. An option it cannot express raises ``UnsupportedFeatureError`` naming
that option; it is never silently dropped. ``ORDER`` / ``NOORDER`` sits
*outside* the parenthesis group -- ``IDENTITY(1, 1) NOORDER`` -- and the
negative form is Snowflake's one word. ``GENERATED ALWAYS`` remains the
behaviour change from the previous round: it used to render ``IDENTITY(1, 1)``,
byte for byte the same as ``BY DEFAULT``, and now refuses.

These assertions are string assertions only. **There is no Snowflake instance
on this machine and CI has none either**, so the SQL below was never executed
against a server: it was compared with the reference grammar -- the column
definition on the ``CREATE TABLE`` page
(https://docs.snowflake.com/en/sql-reference/sql/create-table) and
``tableColumnAction`` on the ``ALTER TABLE`` page
(https://docs.snowflake.com/en/sql-reference/sql/alter-table), both carrying
``[ { ORDER | NOORDER } ]`` after the parameter group. Every assertion here is
render-only (documentation plus render), not an execution result: a typo the
grammar checker would catch is a typo this file cannot. What it does pin is
that this dialect emits the ``IDENTITY`` spelling with the parameters it can
carry and refuses the options Snowflake does not have, rather than silently
dropping them.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import (
    AutoIncrementClause,
    ColumnDefinition,
    IdentityClause,
)
from rhosocial.activerecord.backend.expression.types import IntegerType
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.base import IdentityAttribute


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


def _identity(dialect, **kwargs):
    return IdentityClause(dialect, **kwargs)


def _column(dialect, attrs):
    col = ColumnDefinition(dialect, "id", IntegerType(dialect))
    col.attributes = attrs
    return col


class TestIdentityRendering:
    """``IDENTITY(seed, step)``, with both values defaulting to 1."""

    def test_bare(self, dialect):
        sql, params = _identity(dialect).to_sql()
        assert sql == " IDENTITY(1, 1)"
        assert params == ()

    def test_start(self, dialect):
        sql, _ = _identity(dialect, start=100).to_sql()
        assert sql == " IDENTITY(100, 1)"

    def test_increment(self, dialect):
        sql, _ = _identity(dialect, increment=5).to_sql()
        assert sql == " IDENTITY(1, 5)"

    def test_start_and_increment(self, dialect):
        sql, _ = _identity(dialect, start=100, increment=5).to_sql()
        assert sql == " IDENTITY(100, 5)"

    def test_order(self, dialect):
        """``ORDER`` follows the parenthesis group."""
        sql, _ = _identity(dialect, order=True).to_sql()
        assert sql == " IDENTITY(1, 1) ORDER"

    def test_noorder(self, dialect):
        """The negative spelling is Snowflake's one word, ``NOORDER``."""
        sql, _ = _identity(dialect, no_order=True).to_sql()
        assert sql == " IDENTITY(1, 1) NOORDER"

    def test_order_with_parameters(self, dialect):
        """The tail stays outside the parentheses when they carry values."""
        sql, _ = _identity(dialect, start=100, increment=5, no_order=True).to_sql()
        assert sql == " IDENTITY(100, 5) NOORDER"

    def test_order_keyword_is_outside_the_parentheses(self, dialect):
        """``IDENTITY(1, 1) NOORDER``, never ``IDENTITY(1, 1, NOORDER)``."""
        sql, _ = _identity(dialect, no_order=True).to_sql()
        assert sql.index("NOORDER") > sql.index(")")

    def test_by_default_renders_the_same_as_bare(self, dialect):
        """``BY DEFAULT`` is the semantics ``IDENTITY`` already has."""
        sql, _ = _identity(dialect, generation="BY DEFAULT").to_sql()
        assert sql == " IDENTITY(1, 1)"

    def test_rendered_in_a_column_definition(self, dialect):
        col = _column(dialect, [IdentityAttribute(start=5, increment=2)])
        assert col.to_sql() == ('"id" INTEGER IDENTITY(5, 2)', ())

    def test_column_attribute_defaults(self, dialect):
        col = _column(dialect, [IdentityAttribute()])
        assert col.to_sql() == ('"id" INTEGER IDENTITY(1, 1)', ())


class TestRefusedOptions:
    """An option Snowflake's grammar has no clause for is refused by name."""

    @pytest.mark.parametrize(
        "kwargs,feature",
        [
            ({"minvalue": 0}, "IDENTITY MINVALUE"),
            ({"maxvalue": 99}, "IDENTITY MAXVALUE"),
            ({"cycle": True}, "IDENTITY CYCLE"),
            ({"no_cycle": True}, "IDENTITY CYCLE"),
            ({"cache": 10}, "IDENTITY CACHE"),
            ({"no_cache": True}, "IDENTITY CACHE"),
        ],
        ids=[
            "minvalue",
            "maxvalue",
            "cycle-true",
            "no-cycle",
            "cache-count",
            "no-cache",
        ],
    )
    def test_option_is_refused(self, dialect, kwargs, feature):
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            _identity(dialect, **kwargs).to_sql()
        assert exc_info.value.feature_name == feature

    def test_cache_zero_is_refused_at_construction(self, dialect):
        """``cache=0`` is no longer a sentinel spelling; ``no_cache`` is."""
        with pytest.raises(ValueError, match="cache must be a positive integer"):
            _identity(dialect, cache=0)

    def test_cycle_false_is_unspecified(self, dialect):
        """``cycle=False`` is no longer a spelling: the unset pair emits nothing."""
        sql, _ = _identity(dialect, cycle=False).to_sql()
        assert sql == " IDENTITY(1, 1)"

    def test_order_pair_is_mutually_exclusive(self, dialect):
        with pytest.raises(ValueError, match="order and no_order are mutually exclusive"):
            _identity(dialect, order=True, no_order=True)

    def test_always_is_refused(self, dialect):
        """``ALWAYS`` used to render byte-identical to ``BY DEFAULT``."""
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            _identity(dialect, generation="ALWAYS").to_sql()
        assert exc_info.value.feature_name == "IDENTITY GENERATED ALWAYS"

    def test_always_with_parameters_is_still_refused(self, dialect):
        """The generation mode is checked before the parameters are read."""
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            _identity(dialect, generation="ALWAYS", start=10, increment=2).to_sql()
        assert exc_info.value.feature_name == "IDENTITY GENERATED ALWAYS"

    def test_column_attribute_always_is_refused(self, dialect):
        col = _column(
            dialect,
            [IdentityAttribute(generation="ALWAYS", start=10, increment=2)],
        )
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            col.to_sql()
        assert exc_info.value.feature_name == "IDENTITY GENERATED ALWAYS"


class TestAutoIncrementMarker:
    """Core's parameterless marker is not Snowflake's spelling."""

    def test_probe_is_false(self, dialect):
        assert dialect.supports_auto_increment_column() is False

    def test_marker_is_refused(self, dialect):
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            AutoIncrementClause(dialect).to_sql()
        assert exc_info.value.feature_name == "AUTO_INCREMENT column"


class TestIdentityProbes:
    """Every identity probe has its own answer, declared by this dialect."""

    def test_mechanism_probes(self, dialect):
        assert dialect.supports_identity_column() is True
        assert dialect.supports_auto_increment_column() is False

    def test_parameter_probes(self, dialect):
        assert dialect.supports_identity_generation_always() is False
        assert dialect.supports_identity_start() is True
        assert dialect.supports_identity_increment() is True
        assert dialect.supports_identity_minvalue() is False
        assert dialect.supports_identity_maxvalue() is False
        assert dialect.supports_identity_cycle() is False
        assert dialect.supports_identity_order() is True
        assert dialect.supports_identity_cache() is False


class TestOrderDeclarationMatchesRender:
    """The ``ORDER`` probe and the renderer agree.

    Core's conformance rule is checked in both directions: a probe answering
    ``True`` must have a renderer, and a probe answering ``False`` must refuse
    by name. Here only the ``True`` branch has a subject -- this dialect
    declares the tail -- so each test reads the probe and the render together.
    Withdrawing the probe makes ``to_sql()`` raise (the test goes red); a
    renderer that stops emitting the tail makes the equality go red.

    These are render assertions compared with the reference grammar, not
    server execution: there is no Snowflake instance on this machine and none
    in CI.
    """

    def test_order_declaration_matches_render(self, dialect):
        declared = dialect.supports_identity_order()
        sql = _identity(dialect, order=True).to_sql()[0]
        assert declared is True, (
            f"SnowflakeDialect answers supports_identity_order() with "
            f"{declared!r} yet rendered {sql!r}; a declared capability needs "
            f"a renderer."
        )
        assert sql == " IDENTITY(1, 1) ORDER"

    def test_noorder_declaration_matches_render(self, dialect):
        declared = dialect.supports_identity_order()
        sql = _identity(dialect, no_order=True).to_sql()[0]
        assert declared is True, (
            f"SnowflakeDialect answers supports_identity_order() with "
            f"{declared!r} yet rendered {sql!r}; a declared capability needs "
            f"a renderer."
        )
        assert sql == " IDENTITY(1, 1) NOORDER"

    def test_negative_spelling_comes_from_the_keyword_hook(self, dialect):
        """``NOORDER``, not core's spaced SQL-standard ``NO ORDER``."""
        assert dialect.identity_order_keyword(True) == "ORDER"
        assert dialect.identity_order_keyword(False) == "NOORDER"


class TestSentinels:
    """Each channel is shown rejecting a deliberately wrong statement.

    A string assertion that has never been observed to fail is not evidence.
    These are the local counterpart of the server-side sentinel -- a
    deliberately broken ``CREATE TABLE`` that the classifier must report as
    refused -- for a dialect with no server to ask. Each test feeds the
    assertion channel a wrong claim and asserts the channel *rejects* it.
    """

    def test_wrong_expected_render_is_rejected(self, dialect):
        sql, _ = _identity(dialect, start=100, increment=5).to_sql()
        with pytest.raises(AssertionError):
            assert sql == " IDENTITY(5, 100)"

    def test_wrong_expected_feature_name_is_rejected(self, dialect):
        with pytest.raises(AssertionError):
            with pytest.raises(UnsupportedFeatureError) as exc_info:
                _identity(dialect, minvalue=0).to_sql()
            assert exc_info.value.feature_name == "IDENTITY MAXVALUE"

    def test_wrong_probe_value_is_rejected(self, dialect):
        with pytest.raises(AssertionError):
            assert dialect.supports_identity_generation_always() is True

    def test_wrong_order_probe_value_is_rejected(self, dialect):
        with pytest.raises(AssertionError):
            assert dialect.supports_identity_order() is False

    def test_wrong_order_spelling_is_rejected(self, dialect):
        """The spelling channel: ``NOORDER`` is one word, not ``NO ORDER``."""
        sql, _ = _identity(dialect, no_order=True).to_sql()
        with pytest.raises(AssertionError):
            assert sql == " IDENTITY(1, 1) NO ORDER"

    def test_wrong_refusal_claim_is_rejected(self, dialect):
        """A parameter Snowflake accepts must not be refused."""
        refused = False
        try:
            _identity(dialect, start=1).to_sql()
        except UnsupportedFeatureError:
            refused = True
        assert refused is False
