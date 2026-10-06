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
        sql, _ = AlterSequenceExpression(dialect, _seq(dialect), order=False).to_sql()
        assert sql == 'ALTER SEQUENCE "s" NOORDER'
        assert "NO ORDER" not in sql

    def test_increment_and_order(self, dialect):
        sql, _ = AlterSequenceExpression(
            dialect, _seq(dialect), increment=2, order=False
        ).to_sql()
        assert sql == 'ALTER SEQUENCE "s" INCREMENT BY 2 NOORDER'

    def test_cycle_false_is_the_default_and_emits_nothing(self, dialect):
        """``NO CYCLE`` is the words Snowflake rejects, so it is never emitted."""
        sql, _ = AlterSequenceExpression(dialect, _seq(dialect), cycle=False).to_sql()
        assert sql == 'ALTER SEQUENCE "s"'


#: ``(label, create_kwargs, alter_kwargs)`` for each clause Snowflake lacks.
#: Both statements are checked, because both core formatters emit these shapes.
UNSUPPORTED_OPTIONS = [
    ("minvalue", {"minvalue": 0}, {"minvalue": 0}),
    ("maxvalue", {"maxvalue": 99}, {"maxvalue": 99}),
    ("cycle", {"cycle": True}, {"cycle": True}),
    ("cache", {"cache": 10}, {"cache": 10}),
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
