# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_sequence_ddl.py
"""Snowflake sequence DDL renders Snowflake's grammar, not the SQL standard one.

Why this file exists
====================

Snowflake has sequences, but core's shared
:class:`~rhosocial.activerecord.backend.dialect.mixins.SequenceMixin` renders the
SQL-standard shape, which Snowflake rejects in five places: ``MINVALUE``,
``MAXVALUE``, ``CYCLE``, ``CACHE`` and ``OWNED BY`` have no Snowflake clause,
and ``NOORDER`` is one word where core writes ``NO ORDER``. Before this backend
stated its own formatters the dialect refused every sequence statement, because
the master switch core consults is spelled ``supports_sequence`` (singular) and
this backend answered ``supports_sequences`` (plural) -- a probe nothing read.

These assertions are string assertions only. **There is no Snowflake instance on
this machine and CI has none either**, so the SQL below was never executed
against a server: it was compared with the grammar in the ``CREATE SEQUENCE``,
``ALTER SEQUENCE`` and ``DROP SEQUENCE`` reference pages. A typo the grammar
checker would catch is a typo this file cannot. What it does pin is that this
dialect emits Snowflake's clause spellings and refuses the five clauses
Snowflake does not have, rather than silently dropping them.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Sequence, Table
from rhosocial.activerecord.backend.expression.statements.ddl_sequence import (
    AlterSequenceExpression,
    CreateSequenceExpression,
    DropSequenceExpression,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


def _seq(dialect):
    return Sequence(dialect, "s")


class TestCreateSequenceRendering:
    """``CREATE SEQUENCE`` in Snowflake's clause order."""

    def test_plain(self, dialect):
        sql, params = CreateSequenceExpression(dialect, _seq(dialect)).to_sql()
        assert sql == 'CREATE SEQUENCE "s"'
        assert params == ()

    def test_every_supported_option(self, dialect):
        """The maximal Snowflake-legal option set, in grammar order."""
        sql, params = CreateSequenceExpression(
            dialect,
            _seq(dialect),
            if_not_exists=True,
            start=1000,
            increment=5,
            order=True,
        ).to_sql()
        assert sql == 'CREATE SEQUENCE IF NOT EXISTS "s" START WITH 1000 INCREMENT BY 5 ORDER'
        assert params == ()

    def test_no_order_renders_noorder(self, dialect):
        """``no_order`` is the parameter that spells Snowflake's ``NOORDER``."""
        sql, _ = CreateSequenceExpression(dialect, _seq(dialect), no_order=True).to_sql()
        assert sql == 'CREATE SEQUENCE "s" NOORDER'

    def test_order_pair_is_mutually_exclusive(self, dialect):
        with pytest.raises(ValueError, match="order and no_order are mutually exclusive"):
            CreateSequenceExpression(dialect, _seq(dialect), order=True, no_order=True)

    def test_namespaced_name(self, dialect):
        """The sequence object renders its own namespace; the formatter does not."""
        sql, _ = CreateSequenceExpression(
            dialect,
            Sequence(dialect, "s", schema_name="reporting", catalog_name="analytics"),
        ).to_sql()
        assert sql == 'CREATE SEQUENCE "analytics"."reporting"."s"'


class TestDropSequenceRendering:
    """``DROP SEQUENCE`` in Snowflake's grammar."""

    def test_plain(self, dialect):
        sql, params = DropSequenceExpression(dialect, _seq(dialect)).to_sql()
        assert sql == 'DROP SEQUENCE "s"'
        assert params == ()

    def test_if_exists(self, dialect):
        sql, _ = DropSequenceExpression(dialect, _seq(dialect), if_exists=True).to_sql()
        assert sql == 'DROP SEQUENCE IF EXISTS "s"'


class TestAlterSequenceRendering:
    """``ALTER SEQUENCE`` in Snowflake's grammar."""

    def test_increment(self, dialect):
        sql, _ = AlterSequenceExpression(dialect, _seq(dialect), increment=2).to_sql()
        assert sql == 'ALTER SEQUENCE "s" INCREMENT BY 2'

    def test_order(self, dialect):
        sql, _ = AlterSequenceExpression(dialect, _seq(dialect), order=True).to_sql()
        assert sql == 'ALTER SEQUENCE "s" ORDER'

    def test_noorder_is_one_word(self, dialect):
        """Snowflake spells it ``NOORDER``; core's shared renderer writes ``NO ORDER``."""
        sql, _ = AlterSequenceExpression(dialect, _seq(dialect), no_order=True).to_sql()
        assert sql == 'ALTER SEQUENCE "s" NOORDER'
        assert "NO ORDER" not in sql

    def test_increment_and_order(self, dialect):
        sql, _ = AlterSequenceExpression(
            dialect, _seq(dialect), increment=2, no_order=True
        ).to_sql()
        assert sql == 'ALTER SEQUENCE "s" INCREMENT BY 2 NOORDER'

    def test_cycle_false_is_unspecified_and_emits_nothing(self, dialect):
        """``cycle=False`` is no longer a spelling: the unset pair emits nothing."""
        sql, _ = AlterSequenceExpression(dialect, _seq(dialect), cycle=False).to_sql()
        assert sql == 'ALTER SEQUENCE "s"'

    def test_no_cycle_is_refused_by_name(self, dialect):
        """``NO CYCLE`` is the words Snowflake rejects, so its parameter raises."""
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            AlterSequenceExpression(dialect, _seq(dialect), no_cycle=True).to_sql()
        assert exc_info.value.feature_name == "ALTER SEQUENCE CYCLE"

    def test_no_cache_is_refused_by_name(self, dialect):
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            AlterSequenceExpression(dialect, _seq(dialect), no_cache=True).to_sql()
        assert exc_info.value.feature_name == "ALTER SEQUENCE CACHE"

    def test_order_pair_is_mutually_exclusive(self, dialect):
        with pytest.raises(ValueError, match="order and no_order are mutually exclusive"):
            AlterSequenceExpression(dialect, _seq(dialect), order=True, no_order=True)


#: ``(label, create_kwargs, alter_kwargs)`` for each clause Snowflake lacks.
#: Both statements are checked, because both core formatters emit these shapes.
#: The two-spelling options contribute one row per spelling: the negative
#: parameters are separate requests and must be refused by name exactly like
#: the positive ones.
UNSUPPORTED_OPTIONS = [
    ("minvalue", {"minvalue": 0}, {"minvalue": 0}),
    ("maxvalue", {"maxvalue": 99}, {"maxvalue": 99}),
    ("cycle", {"cycle": True}, {"cycle": True}),
    ("no_cycle", {"no_cycle": True}, {"no_cycle": True}),
    ("cache", {"cache": 10}, {"cache": 10}),
    ("no_cache", {"no_cache": True}, {"no_cache": True}),
    ("owned_by", {"owned_by": "t.c"}, {"owned_by": "t.c"}),
    # The initial value cannot be changed after creation, so ALTER has no
    # START or RESTART clause at all. CREATE has no RESTART field.
    ("alter restart", None, {"restart": 1}),
    ("alter start", None, {"start": 1}),
]


class TestUnsupportedOptionsAreRefused:
    """A requested option Snowflake lacks raises; it is never silently dropped."""

    @pytest.mark.parametrize(
        "label,create_kwargs,alter_kwargs",
        UNSUPPORTED_OPTIONS,
        ids=[case[0] for case in UNSUPPORTED_OPTIONS],
    )
    def test_create_refuses(self, dialect, label, create_kwargs, alter_kwargs):
        if create_kwargs is None:
            pytest.skip("no CREATE-side option for this row")
        with pytest.raises(UnsupportedFeatureError):
            CreateSequenceExpression(dialect, _seq(dialect), **create_kwargs).to_sql()

    @pytest.mark.parametrize(
        "label,create_kwargs,alter_kwargs",
        UNSUPPORTED_OPTIONS,
        ids=[case[0] for case in UNSUPPORTED_OPTIONS],
    )
    def test_alter_refuses(self, dialect, label, create_kwargs, alter_kwargs):
        with pytest.raises(UnsupportedFeatureError):
            AlterSequenceExpression(dialect, _seq(dialect), **alter_kwargs).to_sql()


class TestAlterSequenceStartProbe:
    """The ALTER-side START refusal is answered by its own probe.

    ``supports_sequence_start`` is True here -- ``CREATE SEQUENCE`` accepts
    ``START`` -- while ``supports_alter_sequence_start`` is False, because the
    initial value cannot be changed after creation. The ALTER formatter consults
    the latter, so the two statements disagree without the formatter hard-coding
    the refusal.
    """

    def test_probes_disagree(self, dialect):
        assert dialect.supports_sequence_start() is True
        assert dialect.supports_alter_sequence_start() is False

    def test_alter_start_is_refused_by_the_probe(self, dialect):
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            AlterSequenceExpression(dialect, _seq(dialect), start=5).to_sql()
        assert "ALTER SEQUENCE START" in str(exc_info.value)


class TestWrongObjectKindIsRefused:
    """A table in the sequence slot is refused before any SQL exists."""

    @pytest.mark.parametrize(
        "build",
        [
            lambda d, o: CreateSequenceExpression(d, o),
            lambda d, o: DropSequenceExpression(d, o),
            lambda d, o: AlterSequenceExpression(d, o),
        ],
        ids=["create", "drop", "alter"],
    )
    def test_table_in_the_sequence_slot(self, dialect, build):
        expression = build(dialect, Table(dialect, "users"))
        with pytest.raises(TypeError) as exc_info:
            expression.to_sql()
        assert "must be a Sequence, got Table" in str(exc_info.value)


#: ``(option, kwargs, create_probe, alter_probe)`` for every sequence option
#: whose decision must come from the capability probes. The kwargs request the
#: option; the probe named for the formatter answers whether the dialect can
#: express it.
#:
#: ``start`` is the one option whose two formatters ask different questions:
#: CREATE's ``START WITH`` sets the initial value and is answered by
#: ``supports_sequence_start``, while ALTER's clause of the same spelling
#: cannot change it and is answered by ``supports_alter_sequence_start``. Core
#: keeps the two probes apart, so the table does too.
SEQUENCE_OPTION_PROBES = [
    (
        "start",
        {"start": 1},
        "supports_sequence_start",
        "supports_alter_sequence_start",
    ),
    (
        "increment",
        {"increment": 1},
        "supports_sequence_increment",
        "supports_sequence_increment",
    ),
    (
        "minvalue",
        {"minvalue": 0},
        "supports_sequence_minvalue",
        "supports_sequence_minvalue",
    ),
    (
        "maxvalue",
        {"maxvalue": 99},
        "supports_sequence_maxvalue",
        "supports_sequence_maxvalue",
    ),
    (
        "cycle",
        {"cycle": True},
        "supports_sequence_cycle",
        "supports_sequence_cycle",
    ),
    (
        "cache",
        {"cache": 10},
        "supports_sequence_cache",
        "supports_sequence_cache",
    ),
    (
        "order",
        {"order": True},
        "supports_sequence_order",
        "supports_sequence_order",
    ),
    (
        "no_order",
        {"no_order": True},
        "supports_sequence_order",
        "supports_sequence_order",
    ),
    (
        "owned_by",
        {"owned_by": "t.c"},
        "supports_sequence_owned_by",
        "supports_sequence_owned_by",
    ),
]


def _flipped_dialect(probe_name):
    """A stock Snowflake dialect with exactly one capability probe flipped.

    The flip is the only difference from the stock dialect, so any behaviour
    change between the two is attributable to that probe alone.
    """
    stock_value = getattr(SnowflakeDialect(version=(8, 0, 0)), probe_name)()
    flipped = type(
        f"SnowflakeDialectFlipped{probe_name}",
        (SnowflakeDialect,),
        {probe_name: lambda self: not stock_value},
    )
    return flipped(version=(8, 0, 0))


def _render_outcome(expression_cls, dialect, kwargs):
    """Render one statement; a refusal is an outcome, not an error.

    Returns ``("rendered", (sql, params))`` or ``("refused", message)`` so the
    guard can compare the two dialects' behaviour without ``pytest.raises``.
    """
    try:
        sql, params = expression_cls(dialect, _seq(dialect), **kwargs).to_sql()
    except UnsupportedFeatureError as exc:
        return "refused", str(exc)
    return "rendered", (sql, params)


class TestEverySequenceOptionProbeIsLoadBearing:
    """Flipping any one sequence-option probe must change the formatter's answer.

    A capability probe is load-bearing when the formatter's decision follows
    it: flip the probe's answer and the rendered statement (or the refusal)
    flips with it. A probe whose answer can change while the behaviour does not
    is decorative -- a capability nobody consults. The first round gated five
    options but left five answers hard-coded -- CREATE's start, increment and
    owned_by, and ALTER's increment and owned_by -- so flipping those probes
    changed nothing; this walk named exactly those five red before the second
    round gated them, and reverting any one gate in ``mixins/sequence.py``
    turns the matching case below red.

    Each case subclasses the stock dialect with exactly one probe flipped and
    renders the same expression through the CREATE and the ALTER formatter.
    The stock dialect answers ``True`` for CREATE's start, increment and order,
    so those cases must render on the stock dialect and refuse on the flipped
    one; it answers ``False`` for minvalue, maxvalue, cycle, cache, owned_by
    and ALTER's start, so those cases must refuse on the stock dialect and
    render on the flipped one.
    """

    @pytest.mark.parametrize(
        "option,kwargs,create_probe,alter_probe",
        SEQUENCE_OPTION_PROBES,
        ids=[case[0] for case in SEQUENCE_OPTION_PROBES],
    )
    @pytest.mark.parametrize(
        "statement,expression_cls",
        [
            ("CREATE", CreateSequenceExpression),
            ("ALTER", AlterSequenceExpression),
        ],
        ids=["create", "alter"],
    )
    def test_every_sequence_option_probe_is_load_bearing(
        self,
        dialect,
        statement,
        expression_cls,
        option,
        kwargs,
        create_probe,
        alter_probe,
    ):
        probe_name = create_probe if statement == "CREATE" else alter_probe
        stock_probe = getattr(dialect, probe_name)()
        flipped_dialect = _flipped_dialect(probe_name)

        stock_kind, stock_detail = _render_outcome(expression_cls, dialect, kwargs)
        flipped_kind, flipped_detail = _render_outcome(
            expression_cls, flipped_dialect, kwargs
        )

        expected_stock = "rendered" if stock_probe else "refused"
        expected_flipped = "refused" if stock_probe else "rendered"
        assert stock_kind == expected_stock, (
            f"{statement} SEQUENCE {option}: the stock dialect answers "
            f"{probe_name}()={stock_probe}, so the option must be "
            f"{expected_stock}; got {stock_kind}: {stock_detail!r}"
        )
        assert flipped_kind == expected_flipped, (
            f"{statement} SEQUENCE {option}: with {probe_name}() flipped to "
            f"{not stock_probe}, the option must be {expected_flipped}; got "
            f"{flipped_kind}: {flipped_detail!r}. The probe is decorative: "
            f"the formatter ignores its answer."
        )
