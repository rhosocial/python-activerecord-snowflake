# tests/rhosocial/activerecord_snowflake_test/test_dialect_schema_support.py
"""Tests for the schema capability declared on the Snowflake dialect.

Two switches are deliberately named apart and both are exercised here.
``supports_schema()`` is the DDL-side umbrella -- does the engine have schemas
at all -- and is owned by ``SnowflakeSchemaMixin`` beside the granular CREATE /
DROP flags it covers. ``NamespaceSupport`` is the naming protocol: which
namespace levels a name may carry, which for Snowflake is database, schema and
name. Snowflake renders both, so both answers are ``True``.

Which mixin owns which is itself part of the contract, so it is asserted rather
than assumed: this backend answers the naming side from exactly one class, and
the one it used to answer it from twice is gone.
"""
from rhosocial.activerecord.backend.dialect.protocols import NamespaceSupport
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import (
    SnowflakeNamespaceMixin,
    SnowflakeSchemaMixin,
)


def _declaring_mixin(dialect, method_name):
    """Return the name of the first class in the MRO that defines *method_name*."""
    return next(
        klass.__name__
        for klass in type(dialect).__mro__
        if method_name in vars(klass)
    )


class TestSchemaCapability:
    """Umbrella flag and granular schema DDL capability bits."""

    def _dialect(self) -> SnowflakeDialect:
        return SnowflakeDialect()

    def test_supports_schema_is_true(self):
        assert self._dialect().supports_schema() is True

    def test_implements_namespace_support_protocol(self):
        assert isinstance(self._dialect(), NamespaceSupport)

    def test_granular_ddl_flags_true(self):
        """SnowflakeSchemaMixin wires up CREATE/DROP SCHEMA DDL."""
        d = self._dialect()
        assert d.supports_create_schema() is True
        assert d.supports_drop_schema() is True
        assert d.supports_schema_if_not_exists() is True
        assert d.supports_schema_if_exists() is True

    def test_namespace_levels_are_rendered(self):
        """A name may carry a schema and a database, and both are rendered."""
        d = self._dialect()
        assert d.supports_schema_qualification() is True
        assert d.supports_catalog() is True
        assert d.supports_catalog_qualification() is True


class TestNamingSideIsStatedOnce:
    """One ``supports_schema``, one owner per naming question.

    The bug these guard against was not a wrong answer -- every copy returned
    ``True`` -- it was one name meaning two things. Two mixins declared
    ``supports_schema``, the earlier MRO position silently won, and because both
    docstrings described the *naming* layer the copy that got shadowed was the
    one that read correctly. Nothing looked wrong from outside.

    So the invariant is structural: the DDL-side switch has exactly one
    declaring class in this backend, and the naming side is answered from a
    single mixin. Dropping either declaration cannot pass unnoticed, because the
    answer would then be inherited from the shared default -- which is ``False``
    for all three qualification probes, so names would silently stop being
    qualified rather than start raising.
    """

    def _dialect(self) -> SnowflakeDialect:
        return SnowflakeDialect()

    def test_supports_schema_has_exactly_one_declaring_class(self):
        assert _declaring_mixin(self._dialect(), "supports_schema") == (
            "SnowflakeSchemaMixin"
        )

    def test_naming_probes_all_come_from_the_namespace_mixin(self):
        d = self._dialect()
        for probe in (
            "supports_catalog",
            "supports_catalog_qualification",
            "supports_schema_qualification",
        ):
            assert _declaring_mixin(d, probe) == "SnowflakeNamespaceMixin", (
                f"{probe} is answered from somewhere other than "
                f"SnowflakeNamespaceMixin; the naming side must be stated once"
            )

    def test_catalog_validation_comes_from_the_namespace_mixin(self):
        assert _declaring_mixin(
            self._dialect(), "validate_catalog_name"
        ) == "SnowflakeNamespaceMixin"

    def test_the_two_mixins_declare_disjoint_methods(self):
        """No name is declared by both, so nothing can be shadowed by accident."""
        shared = set(SnowflakeNamespaceMixin.__dict__) & set(SnowflakeSchemaMixin.__dict__)
        public = {name for name in shared if not name.startswith("_")}
        assert not public, (
            f"declared by both naming and DDL mixins: {sorted(public)}"
        )