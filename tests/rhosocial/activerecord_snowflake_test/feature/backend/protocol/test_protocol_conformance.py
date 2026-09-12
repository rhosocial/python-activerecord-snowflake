# tests/rhosocial/activerecord_snowflake_test/feature/backend/protocol/test_protocol_conformance.py
"""Protocol conformance tests for Snowflake backend.

Per the project's testing rules, every backend must include 5 mandatory
protocol conformance test classes.
"""
import inspect
from typing import get_type_hints

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeTimeTravelSupport,
    SnowflakeVariantSupport,
    SnowflakeArraySupport,
    SnowflakeCloneSupport,
    SnowflakeStageSupport,
)
from rhosocial.activerecord.backend.impl.snowflake.mixins import (
    SnowflakeTimeTravelMixin,
    SnowflakeVariantMixin,
    SnowflakeArrayMixin,
    SnowflakeCloneMixin,
    SnowflakeStageMixin,
    SnowflakeTransactionMixin,
)
from rhosocial.activerecord.backend.dialect import protocols as dialect_protocols
from rhosocial.activerecord.backend.dialect.protocols import (
    AdvancedGroupingSupport,
    CollationSupport,
    ConstraintSupport,
    CTESupport,
    DDLTypeSupport,
    ExplainSupport,
    FilterClauseSupport,
    IndexSupport,
    IntrospectionSupport,
    JSONSupport,
    JoinSupport,
    LateralJoinSupport,
    MergeSupport,
    QualifyClauseSupport,
    ReturningSupport,
    SchemaSupport,
    SequenceSupport,
    SetOperationSupport,
    SQLFunctionSupport,
    TransactionControlSupport,
    UpsertSupport,
    ViewSupport,
    WildcardSupport,
    WindowFunctionSupport,
    ArraySupport as GenericArraySupport,
    AlterTableModifierSupport,
    PartitionSupport,
    TableSupport,
)


# All protocols that SnowflakeDialect should implement
SNOWFLAKE_PROTOCOLS = [
    # Generic protocols
    AdvancedGroupingSupport,
    CollationSupport,
    CTESupport,
    DDLTypeSupport,
    ExplainSupport,
    FilterClauseSupport,
    IndexSupport,
    IntrospectionSupport,
    JSONSupport,
    JoinSupport,
    LateralJoinSupport,
    MergeSupport,
    QualifyClauseSupport,
    ReturningSupport,
    SchemaSupport,
    SequenceSupport,
    SetOperationSupport,
    SQLFunctionSupport,
    TransactionControlSupport,
    UpsertSupport,
    ViewSupport,
    WildcardSupport,
    WindowFunctionSupport,
    GenericArraySupport,
    ConstraintSupport,
    # Generic protocols Snowflake also satisfies (previously omitted from this list).
    AlterTableModifierSupport,
    PartitionSupport,
    TableSupport,
    # Snowflake-specific protocols
    SnowflakeTimeTravelSupport,
    SnowflakeVariantSupport,
    SnowflakeArraySupport,
    SnowflakeCloneSupport,
    SnowflakeStageSupport,
]

# Snowflake-specific protocol-mixin pairs
PROTOCOL_MIXIN_PAIRS = [
    (SnowflakeTimeTravelSupport, SnowflakeTimeTravelMixin),
    (SnowflakeVariantSupport, SnowflakeVariantMixin),
    (SnowflakeArraySupport, SnowflakeArrayMixin),
    (SnowflakeCloneSupport, SnowflakeCloneMixin),
    (SnowflakeStageSupport, SnowflakeStageMixin),
]


def get_all_protocol_methods(proto: type) -> set:
    """Extract all methods from a protocol (including inherited)."""
    methods = set()
    for cls in proto.__mro__:
        if cls is object:
            continue
        for name in dir(cls):
            if name.startswith('_'):
                continue
            if callable(getattr(cls, name, None)):
                methods.add(name)
    return methods


def get_own_protocol_methods(proto: type) -> set:
    """Extract only methods declared by the protocol itself (not inherited)."""
    methods = set()
    own_dict = getattr(proto, '__dict__', {})
    for name in own_dict:
        if name.startswith('_'):
            continue
        methods.add(name)
    # Also check annotations for protocol method declarations
    annotations = getattr(proto, '__annotations__', {})
    for name in annotations:
        if name.startswith('_'):
            continue
        methods.add(name)
    return methods


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeDialectProtocolConformance:
    """Verify Dialect instance satisfies all declared Protocol isinstance checks."""

    @pytest.mark.parametrize("protocol", SNOWFLAKE_PROTOCOLS)
    def test_implements_protocol(self, dialect, protocol):
        assert isinstance(dialect, protocol), (
            f"SnowflakeDialect does not implement {protocol.__name__}"
        )


# Generic protocols SnowflakeDialect intentionally does NOT implement.
#
# Listing them makes the omission a deliberate, tested contract: if Snowflake
# ever satisfies one by accident, the negative test fails and forces a conscious
# decision (move to SNOWFLAKE_PROTOCOLS or revert).
SNOWFLAKE_NOT_IMPLEMENTED = [
    # --- Intentional non-support ---
    # Snowflake has no SQL/XML support.
    dialect_protocols.SQLXMLSupport,
    dialect_protocols.SQLXMLParsingSupport,
    dialect_protocols.SQLXMLSerializationSupport,
    dialect_protocols.SQLXMLConstructionSupport,
    dialect_protocols.SQLXMLAggregationSupport,
    dialect_protocols.SQLXMLQueryingSupport,
    # Snowflake has no SQL/PGQ property-graph tables.
    dialect_protocols.GraphTableSupport,
    # Snowflake has no Cypher/property-graph query support.
    dialect_protocols.GraphSupport,
    # Snowflake does not support SELECT ... FOR UPDATE row locking.
    dialect_protocols.LockingSupport,
    # Snowflake does not support triggers.
    dialect_protocols.TriggerSupport,
    # --- Known gaps (feature exists, generic protocol not yet declared) ---
    # TODO: Snowflake supports AUTOINCREMENT/IDENTITY; compose AutoIncrementMixin
    # and move this to SNOWFLAKE_PROTOCOLS.
    dialect_protocols.AutoIncrementSupport,
    # TODO: Snowflake supports generated columns; implement
    # GeneratedColumnMixin overrides and move to SNOWFLAKE_PROTOCOLS.
    dialect_protocols.GeneratedColumnSupport,
    # TODO: Snowflake supports TRUNCATE TABLE; declare TruncateSupport and move
    # this to SNOWFLAKE_PROTOCOLS.
    dialect_protocols.TruncateSupport,
    # TODO: Snowflake supports ILIKE; declare ILIKESupport and move this to
    # SNOWFLAKE_PROTOCOLS.
    dialect_protocols.ILIKESupport,
    # TODO: Snowflake supports SQL UDFs; the generic SQL/PSM FunctionSupport is
    # not declared (Snowflake exposes routines via SnowflakeRoutineSupport).
    dialect_protocols.FunctionSupport,
    # TODO: Snowflake LISTAGG supports WITHIN GROUP; declare
    # OrderedSetAggregationSupport and move this to SNOWFLAKE_PROTOCOLS.
    dialect_protocols.OrderedSetAggregationSupport,
    # TODO: Snowflake time travel is exposed via SnowflakeTimeTravelSupport;
    # the generic TemporalTableSupport is not declared.
    dialect_protocols.TemporalTableSupport,
]


def get_all_generic_protocols() -> dict:
    """Discover every generic dialect protocol defined in protocols.py."""
    from typing import Protocol

    discovered = {}
    for name, obj in inspect.getmembers(dialect_protocols, inspect.isclass):
        if Protocol in getattr(obj, "__mro__", []) and name.endswith("Support"):
            discovered[name] = obj
    return discovered


class TestSnowflakeDialectNegativeProtocolConformance:
    """Assert SnowflakeDialect does not implement intentionally-unsupported protocols."""

    @pytest.fixture
    def dialect(self):
        return SnowflakeDialect(version=(8, 0, 0))

    @pytest.mark.parametrize("protocol", SNOWFLAKE_NOT_IMPLEMENTED)
    def test_does_not_implement_protocol(self, dialect, protocol):
        """SnowflakeDialect must NOT implement any protocol in SNOWFLAKE_NOT_IMPLEMENTED."""
        assert not isinstance(dialect, protocol), (
            f"SnowflakeDialect unexpectedly implements {protocol.__name__}. "
            f"If intentional, move it from SNOWFLAKE_NOT_IMPLEMENTED to SNOWFLAKE_PROTOCOLS "
            f"(and implement the behaviour fully)."
        )

    def test_positive_and_negative_lists_partition_all_protocols(self):
        """Every generic protocol must be classified for Snowflake."""
        all_protos = set(get_all_generic_protocols())
        positive = {
            p.__name__
            for p in SNOWFLAKE_PROTOCOLS
            if p.__module__ == dialect_protocols.__name__
        }
        negative = {p.__name__ for p in SNOWFLAKE_NOT_IMPLEMENTED}

        overlap = positive & negative
        assert not overlap, f"Protocols in BOTH lists: {sorted(overlap)}"

        unclassified = all_protos - positive - negative
        assert not unclassified, (
            f"Generic protocols not classified for Snowflake: {sorted(unclassified)}. "
            f"Add each to SNOWFLAKE_PROTOCOLS or SNOWFLAKE_NOT_IMPLEMENTED."
        )


class TestProtocolNonOverlap:
    """Verify no method name overlap between the protocols Snowflake claims support."""

    def test_no_overlap_between_snowflake_protocols(self):
        method_map = {}
        for proto in SNOWFLAKE_PROTOCOLS:
            for method in get_all_protocol_methods(proto):
                method_map.setdefault(proto.__name__, set()).add(method)

        for name, members in method_map.items():
            assert len(members) > 0, f"Protocol {name} has no members defined"

        excluded_overlaps = {
            # Snowflake's ARRAY protocol restates the generic ARRAY capability.
            ("ArraySupport", "SnowflakeArraySupport"),
            ("SnowflakeArraySupport", "ArraySupport"),
        }

        from itertools import combinations

        violations = []
        for (name_a, members_a), (name_b, members_b) in combinations(method_map.items(), 2):
            if (name_a, name_b) in excluded_overlaps:
                continue
            overlap = members_a & members_b
            if overlap:
                violations.append(f"{name_a} ∩ {name_b} = {overlap}")

        assert not violations, (
            "The following protocols have overlapping interfaces, need to merge or rename:\n"
            + "\n".join(f"  • {v}" for v in violations)
        )


class TestProtocolMethodSignatureConformance:
    """Verify Dialect method signatures match Protocol definitions."""

    @pytest.mark.parametrize("protocol", SNOWFLAKE_PROTOCOLS)
    def test_protocol_methods_exist_on_dialect(self, dialect, protocol):
        proto_methods = get_all_protocol_methods(protocol)
        for method_name in proto_methods:
            assert hasattr(dialect, method_name), (
                f"SnowflakeDialect missing method '{method_name}' from {protocol.__name__}"
            )


class TestProtocolMixinForwardCoverage:
    """Verify protocol-declared methods exist in their implementation."""

    @pytest.mark.parametrize("protocol,impl", PROTOCOL_MIXIN_PAIRS)
    def test_protocol_declared_methods_are_implemented(self, protocol, impl):
        proto_methods = get_own_protocol_methods(protocol)
        impl_methods = {name for name in dir(impl) if not name.startswith('_')}
        missing = proto_methods - impl_methods
        assert not missing, (
            f"{impl.__name__} missing methods from {protocol.__name__}: {missing}"
        )


class TestProtocolMixinReverseCoverage:
    """Verify implementation methods are declared in their protocol."""

    @pytest.mark.parametrize("protocol,impl", PROTOCOL_MIXIN_PAIRS)
    def test_impl_public_methods_are_declared_in_protocol(self, protocol, impl):
        proto_methods = get_all_protocol_methods(protocol)
        impl_own_methods = {
            name for name in dir(impl)
            if name.startswith(('format_', 'supports_', 'get_'))
            and name in impl.__dict__
        }
        undeclared = impl_own_methods - proto_methods
        assert not undeclared, (
            f"{impl.__name__} has undeclared methods in {protocol.__name__}: {undeclared}"
        )
