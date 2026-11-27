# tests/rhosocial/activerecord_snowflake_test/feature/backend/dialect/test_artifact_registry.py
"""Snowflake owns its artifact registry; no other owner's kinds leak into it.

An expression artifact is data: parameters only, no dialect. Which kinds a read
may produce is decided by the registry it resolves through, and ownership is
per owner:

* the Snowflake dialect answers with ``backend_registry()`` — core's kinds
  composed with this backend's own expression package;
* the overlap with core is exactly that composition, never a merge with another
  backend;
* the assembled table is frozen, so a reader cannot widen it for everyone else;
* a kind whose SQL is caller-vouched text (``RawSQL`` / ``RawSQLPredicate``)
  stays out of the published table and is opted in by a private twin.
"""

import importlib
import inspect
import pkgutil

import pytest

from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.operators import RawSQL, RawSQLPredicate
from rhosocial.activerecord.backend.expression.registry import (
    RegistryError,
    RegistryReason,
)
from rhosocial.activerecord.backend.expression.serialization import (
    ExpressionDeserializationError,
    core_registry,
    deserialize,
    serialize,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression.types import (
    SnowflakeVarcharType,
)
from rhosocial.activerecord.backend.impl.snowflake.registry import backend_registry


class ForeignBackendKind(BaseExpression):
    """A kind owned by no registry here; stands in for another backend's node.

    The refusal under test is about the *kind name*, so a locally declared node
    exercises it without importing a foreign backend's implementation package.
    """

    def __init__(self, dialect):
        super().__init__(dialect)


def _dialect():
    return SnowflakeDialect(version=(8, 0, 0))


SNOWFLAKE_EXPR_PKG = "rhosocial.activerecord.backend.impl.snowflake.expression"


def _snowflake_nodes():
    """Every concrete expression class this backend's package defines."""
    pkg = importlib.import_module(SNOWFLAKE_EXPR_PKG)
    found = {}
    for _, modname, _ in pkgutil.walk_packages(
        pkg.__path__, pkg.__name__ + ".", onerror=lambda x: None
    ):
        try:
            module = importlib.import_module(modname)
        except Exception:  # noqa: BLE001 -- an unimportable module defines nothing
            continue
        for name in dir(module):
            obj = getattr(module, name, None)
            if (
                isinstance(obj, type)
                and obj.__module__ == modname
                and issubclass(obj, BaseExpression)
                and obj is not BaseExpression
                and not inspect.isabstract(obj)
            ):
                found.setdefault(obj, f"{modname}.{name}")
    return found


def _declares_a_formatter(cls):
    """Whether *cls* resolves a formatter that is not the base's sentinel."""
    for klass in cls.__mro__:
        if "format_method" in vars(klass):
            return klass is not BaseExpression
    return False


def test_the_dialect_answers_with_the_backends_own_registry():
    """``artifact_registry()`` is Snowflake's published table, cached and frozen."""
    dialect = _dialect()
    assert dialect.artifact_registry() is backend_registry()
    assert backend_registry() is backend_registry()
    assert backend_registry().is_frozen


def test_backend_proprietary_kind_resolves_and_core_kinds_are_the_overlap():
    """Snowflake's own kinds resolve; core's are reachable through the same table."""
    registry = _dialect().artifact_registry()

    assert registry.resolve_node(SnowflakeVarcharType.kind()) is SnowflakeVarcharType
    assert registry.resolve_node(Column.kind()) is Column

    kinds = registry.node_kinds()
    snowflake_kinds = [kind for kind in kinds if kind.startswith("snowflake_")]
    assert snowflake_kinds, "the Snowflake expression package contributed no kinds"

    # No other backend's kinds: composition with core is the only overlap.
    assert "sqlite_vacuum_statement" not in kinds
    assert "_dummy_type_definition" not in kinds


def test_every_formatter_declaring_node_is_discovered_by_the_walk():
    """Declaration is registration: no class needs adding by hand.

    ``registry_for_packages`` walks this package and registers each concrete
    node that resolves a ``format_method``. The statements, clauses and DDL
    nodes that used to render themselves declared none, so they were absent
    from the published table; now each declares one and the walk finds it.
    """
    registry = backend_registry()
    undiscovered = []
    for cls, fqn in _snowflake_nodes().items():
        if not _declares_a_formatter(cls):
            continue
        try:
            found = registry.resolve_node(cls.kind())
        except RegistryError:
            found = None
        if found is not cls:
            undiscovered.append((fqn, cls.kind()))
    assert not undiscovered, (
        "these nodes declare a format_method but the package walk did not "
        f"register them: {sorted(undiscovered)}"
    )


def test_a_foreign_backends_kind_is_refused_by_name():
    """A kind Snowflake does not own is refused, never resolved to another class."""
    artifact = serialize(ForeignBackendKind(_dialect()))

    with pytest.raises(ExpressionDeserializationError) as caught:
        deserialize(artifact, _dialect())
    assert ForeignBackendKind.kind() in str(caught.value)

    with pytest.raises(RegistryError) as refused:
        _dialect().artifact_registry().resolve_node(ForeignBackendKind.kind())
    assert refused.value.reason is RegistryReason.KIND_NOT_REGISTERED


def test_the_published_registry_refuses_mutation_by_name():
    """A frozen table is a value; a different set is a new registry."""
    registry = backend_registry()
    assert registry.is_frozen

    mutations = (
        lambda: registry.register_node(Column),
        lambda: registry.register_value_kinds(),
        lambda: registry.unregister_node(Column.kind()),
    )
    for mutate in mutations:
        with pytest.raises(RegistryError) as caught:
            mutate()
        assert caught.value.reason is RegistryReason.REGISTRY_FROZEN
        assert "frozen" in str(caught.value)
        assert caught.value.kind

    # The same set, differently: a twin is mutable and leaves the shared table alone.
    twin = registry.twin()
    assert not twin.is_frozen
    twin.unregister_node(Column.kind())
    assert Column.kind() not in twin.node_kinds()
    assert Column.kind() in registry.node_kinds()


def test_trusted_opt_ins_are_admitted_by_a_private_twin_only():
    """``RawSQL`` / ``RawSQLPredicate`` are caller-vouched text, not default kinds."""
    dialect = _dialect()
    artifact = serialize(RawSQL(dialect, "CURRENT_TIMESTAMP"))

    # The published table refuses the kind by name, as it would for any artifact.
    with pytest.raises(ExpressionDeserializationError) as caught:
        deserialize(artifact, dialect)
    assert "raw_sql" in str(caught.value)
    assert "raw_sql" not in backend_registry().node_kinds()
    assert "raw_sql_predicate" not in backend_registry().node_kinds()

    # A reader that trusts its artifacts opts in on its own copy.
    opt_in = backend_registry().twin()
    for cls in (RawSQL, RawSQLPredicate):
        opt_in.register_node(cls)

    restored = deserialize(artifact, dialect, registry=opt_in)
    assert isinstance(restored, RawSQL)

    predicate = RawSQLPredicate(dialect, "status = %s", ("active",))
    restored_predicate = deserialize(serialize(predicate), dialect, registry=opt_in)
    assert isinstance(restored_predicate, RawSQLPredicate)

    # The global table was never widened by that read.
    assert "raw_sql" not in backend_registry().node_kinds()
    assert core_registry() is not backend_registry()
