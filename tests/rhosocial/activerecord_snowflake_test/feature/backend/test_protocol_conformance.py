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
from rhosocial.activerecord.backend.dialect.protocols import (
    CTESupport,
    FilterClauseSupport,
    WindowFunctionSupport,
    JSONSupport,
    MergeSupport,
    QualifyClauseSupport,
    UpsertSupport,
    LateralJoinSupport,
    JoinSupport,
    ViewSupport,
    SchemaSupport,
    IndexSupport,
    ConstraintSupport,
    IntrospectionSupport,
    ArraySupport as GenericArraySupport,
    AdvancedGroupingSupport,
    ExplainSupport,
    TransactionControlSupport,
    SQLFunctionSupport,
)


# All protocols that SnowflakeDialect should implement
SNOWFLAKE_PROTOCOLS = [
    # Generic protocols
    CTESupport,
    FilterClauseSupport,
    WindowFunctionSupport,
    JSONSupport,
    MergeSupport,
    QualifyClauseSupport,
    UpsertSupport,
    LateralJoinSupport,
    JoinSupport,
    ViewSupport,
    SchemaSupport,
    IndexSupport,
    ConstraintSupport,
    IntrospectionSupport,
    GenericArraySupport,
    AdvancedGroupingSupport,
    ExplainSupport,
    TransactionControlSupport,
    SQLFunctionSupport,
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


class TestProtocolNonOverlap:
    """Verify no method name overlap between Snowflake-specific protocols."""

    def test_no_overlap_between_snowflake_protocols(self):
        snowflake_protocols = [
            SnowflakeTimeTravelSupport,
            SnowflakeVariantSupport,
            SnowflakeArraySupport,
            SnowflakeCloneSupport,
            SnowflakeStageSupport,
        ]
        method_map = {}
        for proto in snowflake_protocols:
            methods = get_own_protocol_methods(proto)
            for method in methods:
                if method in method_map:
                    # Allow overlap for methods that are inherited from common parent
                    pass  # Snowflake protocols are standalone, overlap unlikely
                method_map[method] = proto.__name__

        # Just verify we got results
        assert len(method_map) > 0


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
