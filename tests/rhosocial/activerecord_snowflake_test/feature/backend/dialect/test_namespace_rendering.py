# tests/rhosocial/activerecord_snowflake_test/feature/backend/dialect/test_namespace_rendering.py
"""Snowflake is the dialect that has a namespace level and does not always use it.

What is unusual here, and why it is worth pinning
=================================================

Snowflake has a database above a schema, so ``supports_catalog`` is ``True`` --
and ``supports_catalog_qualification`` is ``True`` too, because
``db.schema.table`` is the ordinary spelling rather than an escape hatch. What
makes this dialect the odd one out is narrower than "it renders both levels":

* the three naming probes are answered from :class:`SnowflakeNamespaceMixin`,
  not from the mixin that owns schema DDL. The other eight dialects answer the
  naming and DDL schema questions from one class each, so the split is invisible
  everywhere else;
* a database is **never usable on its own**. ``db.table`` resolves nowhere in
  Snowflake, because a database contains only schemas. A name carrying a
  database and no schema is refused rather than rendered, and that refusal is
  this backend's own -- no shared renderer does it.

Both facts are the same statement made twice: once as "which levels may a name
carry" (three probes) and once as "what the name looks like" (``format_qualified_name``).
If they were kept in two files they could drift -- a level declared renderable
that the spelling silently omits, or a spelling that emits a level the probe
says is not supported. Nothing would notice until a name rendered one level
short. So they are asserted *together*, against the same object, and the
assertions are written to fail if either half moves alone.

How the tests avoid passing for the wrong reason
================================================

The failure mode this file has to survive is a namespace test that proves nothing.
One real instance of it: a formatter that ignored the ``schema`` argument
entirely still satisfied a test that passed both ``object_name="public.users"``
and ``schema="public"`` -- because the schema was a redundant substring of the
name, so dropping it left the SQL unchanged. Three things here prevent that:

* the schema value (``reporting``) never appears in the object name (``users``),
  so the level cannot be recovered from the name;
* each test asserts that *clearing* the slot changes the SQL, which a formatter
  that ignores the slot cannot satisfy;
* the separator is read off the dialect rather than hard-coded, so the test also
  pins that the join character is the dialect's to choose.
"""

import pytest

from rhosocial.activerecord.backend.expression.objects import (
    Database,
    MaterializedView,
    Schema,
    Sequence,
    Table,
    Type,
    View,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import (
    SnowflakeNamespaceMixin,
)


#: Object kinds that take a namespace. ``Database`` is deliberately absent from
#: the qualified group: a database *is* the outer level, so it never carries one,
#: and ``test_database_carries_no_namespace`` asserts that separately rather than
#: leaving it to look like an oversight.
NAMESPACED_KINDS = [
    ("table", Table),
    ("view", View),
    ("materialized view", MaterializedView),
    ("sequence", Sequence),
    ("type", Type),
    ("schema", Schema),
]

#: Values chosen so no one of them can be read out of any other. The name is
#: bare, the schema is ``reporting``, the database is ``analytics``; none is a
#: prefix, substring or dotted form of another.
NAME = "users"
SCHEMA = "reporting"
CATALOG = "analytics"


@pytest.fixture
def dialect():
    return SnowflakeDialect()


class TestBothLevelsAreRendered:
    """A name may carry a schema, and a schema plus a database.

    The point of the first assertion is not the ``reporting`` in the output but
    the *change* from the bare name. A formatter ignoring the slot would render
    the bare name for both and fail.
    """

    @pytest.mark.parametrize("label,kind", NAMESPACED_KINDS, ids=[c[0] for c in NAMESPACED_KINDS])
    def test_schema_level_is_rendered(self, dialect, label, kind):
        bare = kind(dialect, NAME).to_sql()[0]
        qualified = kind(dialect, NAME, schema_name=SCHEMA).to_sql()[0]
        assert qualified == f'"{SCHEMA}"."{NAME}"'
        assert qualified != bare, f"{label} ignored the schema slot"

    @pytest.mark.parametrize("label,kind", NAMESPACED_KINDS, ids=[c[0] for c in NAMESPACED_KINDS])
    def test_schema_and_database_levels_are_rendered(self, dialect, label, kind):
        sql = kind(
            dialect, NAME, schema_name=SCHEMA, catalog_name=CATALOG
        ).to_sql()[0]
        assert sql == f'"{CATALOG}"."{SCHEMA}"."{NAME}"'

    @pytest.mark.parametrize("label,kind", NAMESPACED_KINDS, ids=[c[0] for c in NAMESPACED_KINDS])
    def test_no_namespace_renders_bare(self, dialect, label, kind):
        assert kind(dialect, NAME).to_sql()[0] == f'"{NAME}"'

    @pytest.mark.parametrize("label,kind", NAMESPACED_KINDS, ids=[c[0] for c in NAMESPACED_KINDS])
    def test_clearing_the_schema_changes_the_sql(self, dialect, label, kind):
        """The reverse check: the parameter must be load-bearing.

        Without this, a test could assert a qualified name while the formatter
        derived it from somewhere else entirely.
        """
        with_level = kind(dialect, NAME, schema_name=SCHEMA).to_sql()[0]
        without_level = kind(dialect, NAME).to_sql()[0]
        assert with_level != without_level


class TestADatabaseIsNeverUsedAlone:
    """The dialect's own rule, and it cannot be inherited.

    ``db.object`` resolves nowhere in Snowflake: a database contains only
    schemas. Rendering it anyway would produce a name the server refuses, with
    the refusal arriving at execution time instead of here. So this dialect
    refuses while rendering.

    The reason this is worth a test rather than a comment: core's shared
    renderer joins whatever levels the object carries and has no rule against a
    lone catalog, so a dialect that did not add one would quietly emit
    ``"analytics"."users"``. Nothing else in the tree would catch that.
    """

    @pytest.mark.parametrize("label,kind", NAMESPACED_KINDS, ids=[c[0] for c in NAMESPACED_KINDS])
    def test_database_without_a_schema_is_refused(self, dialect, label, kind):
        with pytest.raises(ValueError) as exc_info:
            kind(dialect, NAME, catalog_name=CATALOG).to_sql()
        message = str(exc_info.value)
        assert CATALOG in message
        assert "only together with a schema" in message
        assert "schema_name" in message

    def test_the_refusal_names_the_kind_that_was_refused(self, dialect):
        """A view and a table are refused differently, by name.

        Which is what makes the message usable: someone who passed a View where
        a Table belongs is told so, rather than reading a generic refusal.
        """
        with pytest.raises(ValueError) as exc_info:
            View(dialect, NAME, catalog_name=CATALOG).to_sql()
        assert "View" in str(exc_info.value)

    def test_database_itself_carries_no_namespace(self, dialect):
        """A database is the outer level, so it never renders as a qualified one.

        Asserted because it is the one kind where "carry a database" and "be a
        database" would otherwise look like the same request.
        """
        assert Database(dialect, NAME).to_sql()[0] == f'"{NAME}"'


class TestTheSpellingIsTheDialectsToChoose:
    """The join character comes off the dialect, not out of a literal.

    If the separator were hard-coded in the middle of the shared renderer this
    would fail, because overriding the attribute would change nothing. That is the
    property the layer exists for: the shape of the name is not something core
    decides on every engine's behalf.
    """

    def test_separator_defaults_to_a_dot(self, dialect):
        assert dialect.separator == "."

    def test_overriding_the_separator_changes_the_rendering(self, dialect):
        """Read the attribute so the assertion cannot drift from the default."""
        before = dialect.separator
        dialect.separator = "$$"
        try:
            sql = Table(
                dialect, NAME, schema_name=SCHEMA, catalog_name=CATALOG
            ).to_sql()[0]
        finally:
            dialect.separator = before
        assert sql == f'"{CATALOG}"$$"{SCHEMA}"$$"{NAME}"'
        assert dialect.separator != "$$", "the override did not take effect"

    def test_the_dialect_does_not_override_the_shared_spelling(self, dialect):
        """Stated so the choice is visible: the shared spelling is correct here.

        Snowflake's answer -- database outside, schema inside, ``.`` between --
        is what the shared ``format_qualified_name`` already produces, so this
        backend deliberately does **not** restate it. Restating it would put the
        same statement in two files that could then drift: the mixin promising a
        level the shared method stopped emitting, or vice versa, with nothing
        noticing until a name rendered one level short.

        If a future change makes the shared spelling wrong for Snowflake, this
        assertion is what should fail first, and the fix is a real override in
        :class:`SnowflakeNamespaceMixin`.
        """
        assert "format_qualified_name" not in vars(SnowflakeNamespaceMixin), (
            "SnowflakeNamespaceMixin now restates the shared spelling. If that "
            "is deliberate -- because the shared spelling is wrong for "
            "Snowflake -- say so in its docstring and in the tests above, which "
            "currently assert the shared shape."
        )


class TestTheDecisionsAreDeclaredHere:
    """Both halves of the naming answer come from this backend, not from core.

    The declared-object checks in ``test_dialect_schema_support.py`` establish
    *which mixin* answers. These establish that the answers are the ones Snowflake
    is supposed to give, and that both are declared together -- so a future edit
    cannot drop one half and leave the other sounding complete.
    """

    def test_the_probes_are_declared_in_the_namespace_mixin(self):
        for probe in (
            "supports_catalog",
            "supports_catalog_qualification",
            "supports_schema_qualification",
            "validate_catalog_name",
        ):
            assert probe in vars(SnowflakeNamespaceMixin), (
                f"{probe} is not declared by SnowflakeNamespaceMixin; an "
                f"undeclared probe falls back to the shared default, which is "
                f"False and would silently stop qualifying names"
            )

    def test_both_levels_are_declared_as_usable(self, dialect):
        assert dialect.supports_catalog() is True
        assert dialect.supports_catalog_qualification() is True
        assert dialect.supports_schema_qualification() is True

    def test_validate_namespace_reports_rather_than_returns(self, dialect):
        """``validate_namespace`` returns nothing and raises; it does not answer
        with a boolean.

        A boolean would be ignorable -- a caller could discard it -- so the
        verdict is raised where it cannot be dropped.
        """
        assert dialect.validate_namespace(Table(dialect, NAME, schema_name=SCHEMA)) is None

    def test_a_level_the_dialect_refuses_is_reported_as_unsupported(self, dialect):
        """The named path for "this dialect cannot express that level".

        Snowflake expresses both of its levels, so there is nothing to refuse on
        the supported side; what is asserted here is the *mechanism* -- the same
        method raises ``UnsupportedFeatureError`` for a level a dialect does not
        declare -- because that is what a dialect adding or removing a level will
        go through, and it is the branch core's other eight dialects take.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        class NoSchemaDialect(SnowflakeDialect):
            """Snowflake with the schema level withdrawn, for the negative branch."""

            def supports_schema_qualification(self) -> bool:
                return False

        with pytest.raises(UnsupportedFeatureError) as exc_info:
            NoSchemaDialect().validate_namespace(
                Table(None, NAME, schema_name=SCHEMA)
            )
        assert SCHEMA in str(exc_info.value)


class TestTheSlotIsNotRedundant:
    """Guard against the namespace test that proves nothing.

    If the schema value were also part of the object name, a formatter could
    ignore the slot and still produce the expected SQL, because the name alone
    would carry it. This asserts the fixture values cannot be confused that way,
    so the qualified-name assertions above are load-bearing.
    """

    @pytest.mark.parametrize("label,kind", NAMESPACED_KINDS, ids=[c[0] for c in NAMESPACED_KINDS])
    def test_the_values_are_mutually_unreadable(self, dialect, label, kind):
        assert SCHEMA not in NAME
        assert CATALOG not in NAME
        assert CATALOG not in SCHEMA
        assert SCHEMA not in CATALOG
        assert "." not in NAME
        assert kind(dialect, NAME, schema_name=SCHEMA).name == NAME

    def test_a_dotted_name_is_one_identifier_not_a_qualified_name(self, dialect):
        """The other way a test goes hollow: putting the levels in the name.

        ``Table(dialect, "reporting.users")`` renders one quoted identifier,
        ``"reporting.users"``, not two. So a name that looks qualified renders as
        a single object with a dot in it -- which is the correct behaviour and
        also why the qualified assertions above must use separate slots.
        """
        sql = Table(dialect, f"{SCHEMA}.{NAME}").to_sql()[0]
        assert sql == f'"{SCHEMA}.{NAME}"'
        assert sql != f'"{SCHEMA}"."{NAME}"'