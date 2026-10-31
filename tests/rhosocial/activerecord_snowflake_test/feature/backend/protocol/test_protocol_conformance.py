# tests/rhosocial/activerecord_snowflake_test/feature/backend/protocol/test_protocol_conformance.py
"""Protocol conformance tests for Snowflake backend.

Per the project's testing rules, every backend must include 5 mandatory
protocol conformance test classes.
"""
import inspect

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
)
from rhosocial.activerecord.backend.dialect import protocols as dialect_protocols
from rhosocial.activerecord.backend.dialect.protocols import (
    AdvancedGroupingSupport,
    AlterDatabaseSupport,
    AlterSequenceSupport,
    AlterTableModifierSupport,
    AlterTableSupport,
    AlterTypeSupport,
    ArraySupport as GenericArraySupport,
    AutoIncrementColumnSupport,
    CollationSupport,
    ColumnAttributeSupport,
    ColumnTypeSupport,
    CommentSupport,
    ConstraintSupport,
    CreateDatabaseSupport,
    CreateIndexSupport,
    CreateSchemaSupport,
    CreateSequenceSupport,
    CreateTableAsSupport,
    CreateTableCloneSupport,
    CreateTableLikeSupport,
    CreateTableSupport,
    CreateTableUsingTemplateSupport,
    CreateTypeSupport,
    CreateViewSupport,
    CTESupport,
    DDLTypeSupport,
    TimestampSupport,
    DqlOrderSupport,
    DropDatabaseSupport,
    DropIndexSupport,
    DropSchemaSupport,
    DropSequenceSupport,
    DropTableSupport,
    DropTypeSupport,
    DropViewSupport,
    ExplainSupport,
    FilterClauseSupport,
    FulltextIndexSupport,
    GeneratedColumnSupport,
    IdentityColumnSupport,
    ILIKESupport,
    IndexObjectSupport,
    IntrospectionSupport,
    JSONSupport,
    JoinSupport,
    LateralJoinSupport,
    LockingSupport,
    MaterializedViewObjectSupport,
    MaterializedViewSupport,
    MergeSupport,
    NamespaceSupport,
    OrderedSetAggregationSupport,
    PartitionSupport,
    PivotSupport,
    QualifyClauseSupport,
    ReturningSupport,
    SequenceObjectSupport,
    SetOperationSupport,
    SQLFunctionSupport,
    TableObjectSupport,
    TransactionControlSupport,
    TruncateSupport,
    TypeObjectSupport,
    UpsertSupport,
    ViewObjectSupport,
    WildcardSupport,
    WindowFunctionSupport,
)


# All protocols that SnowflakeDialect should implement
SNOWFLAKE_PROTOCOLS = [
    # Generic protocols
    AdvancedGroupingSupport,
    # The identity protocol and the parameterless AUTO_INCREMENT protocol are
    # separate mechanisms. Snowflake implements both interfaces: the
    # parameterised IDENTITY clause renders, while the bare AUTO_INCREMENT
    # marker is refused by its probe (Snowflake's keyword is AUTOINCREMENT,
    # one word, and it is parameterised). A protocol's presence records that
    # the dialect can answer the question, not that every answer is "yes".
    AutoIncrementColumnSupport,
    IdentityColumnSupport,
    CollationSupport,
    CTESupport,
    ColumnAttributeSupport,
    # Column classes: which operations a value carries, where DDLTypeSupport
    # answers how it is stored. SnowflakeColumnTypeMixin supplies the table.
    ColumnTypeSupport,
    CommentSupport,
    DDLTypeSupport,
    ExplainSupport,
    FilterClauseSupport,
    GeneratedColumnSupport,
    ILIKESupport,
    IntrospectionSupport,
    JSONSupport,
    JoinSupport,
    LateralJoinSupport,
    MergeSupport,
    OrderedSetAggregationSupport,
    QualifyClauseSupport,
    ReturningSupport,
    SetOperationSupport,
    SQLFunctionSupport,
    TransactionControlSupport,
    TruncateSupport,
    UpsertSupport,
    WildcardSupport,
    WindowFunctionSupport,
    GenericArraySupport,
    ConstraintSupport,
    # Named-object protocols: Snowflake renders each of these kinds, and the
    # database above the schema is the catalog namespace -- ``db.schema.table``
    # is the ordinary spelling, so both namespace levels are rendered.
    TableObjectSupport,
    ViewObjectSupport,
    MaterializedViewObjectSupport,
    IndexObjectSupport,
    SequenceObjectSupport,
    TypeObjectSupport,
    NamespaceSupport,
    # Generic protocols Snowflake also satisfies (previously omitted from this list).
    AlterTableModifierSupport,
    LockingSupport,
    PartitionSupport,
    # One protocol per DDL statement expression Snowflake actually renders.
    AlterDatabaseSupport,
    AlterSequenceSupport,
    AlterTableSupport,
    AlterTypeSupport,
    CreateDatabaseSupport,
    CreateIndexSupport,
    CreateSchemaSupport,
    CreateSequenceSupport,
    CreateTableAsSupport,
    CreateTableCloneSupport,
    CreateTableLikeSupport,
    CreateTableSupport,
    CreateTableUsingTemplateSupport,
    CreateTypeSupport,
    CreateViewSupport,
    TimestampSupport,
    DqlOrderSupport,
    DropDatabaseSupport,
    DropIndexSupport,
    DropSchemaSupport,
    DropSequenceSupport,
    DropTableSupport,
    DropTypeSupport,
    DropViewSupport,
    FulltextIndexSupport,
    MaterializedViewSupport,
    PivotSupport,
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
    # UUID value expressions (generation / nil-max constants / cast) are not
    # implemented yet on this dialect. Listed here so the omission is a
    # recorded decision rather than a gap; move it to the implemented list
    # when the mixin lands.
    dialect_protocols.UUIDSupport,
    # --- Intentional non-support ---
    # Snowflake has no SQL/PGQ property-graph tables.
    dialect_protocols.GraphTableSupport,
    # Snowflake has no Cypher/property-graph query support.
    dialect_protocols.GraphSupport,
    # Snowflake has no triggers, so it neither names one nor creates one.
    dialect_protocols.TriggerObjectSupport,
    dialect_protocols.CreateTriggerSupport,
    dialect_protocols.DropTriggerSupport,
    # Snowflake exposes routine DDL through SnowflakeRoutineSupport (SQL,
    # JavaScript, Java, Python and Scala bodies) rather than the generic
    # SQL/PSM statement shape. The Snowflake routine expressions carry a bare
    # name and their formatters spell the clause themselves, so the dialect
    # names no ``Function`` object either.
    dialect_protocols.RoutineObjectSupport,
    dialect_protocols.CreateRoutineSupport,
    dialect_protocols.DropRoutineSupport,
    # Snowflake has no FOREIGN TABLE and no SYNONYM.
    dialect_protocols.ForeignTableObjectSupport,
    dialect_protocols.SynonymObjectSupport,
    # Snowflake has no DOMAIN.
    dialect_protocols.CreateDomainSupport,
    dialect_protocols.AlterDomainSupport,
    dialect_protocols.DropDomainSupport,
    # Snowflake time travel uses AT(TIMESTAMP => ...) / AT(OFFSET => ...) /
    # BEFORE(...) rather than the SQL-standard FOR SYSTEM_TIME AS OF rendered
    # by TemporalTableSupport; it is exposed via SnowflakeTimeTravelSupport.
    dialect_protocols.TemporalTableSupport,
    # Snowflake has no SQL/XML support.
    dialect_protocols.SQLXMLSupport,
    dialect_protocols.SQLXMLParsingSupport,
    dialect_protocols.SQLXMLSerializationSupport,
    dialect_protocols.SQLXMLConstructionSupport,
    dialect_protocols.SQLXMLAggregationSupport,
    dialect_protocols.SQLXMLQueryingSupport,
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
        all_protos = set(get_all_generic_protocols().values())
        positive = {p for p in SNOWFLAKE_PROTOCOLS if p in all_protos}
        negative = set(SNOWFLAKE_NOT_IMPLEMENTED)

        overlap = {p.__name__ for p in positive & negative}
        assert not overlap, f"Protocols in BOTH lists: {sorted(overlap)}"

        unclassified = all_protos - positive - negative
        unclassified_names = sorted(p.__name__ for p in unclassified)
        assert not unclassified, (
            f"Generic protocols not classified for Snowflake: {unclassified_names}. "
            f"Add each to SNOWFLAKE_PROTOCOLS or SNOWFLAKE_NOT_IMPLEMENTED."
        )


class TestProtocolNonOverlap:
    """Verify no method name overlap between the protocols Snowflake claims support."""

    def test_no_overlap_between_snowflake_protocols(self):
        # Own members only: every named-object protocol inherits
        # NamespaceSupport by design, and a shared base is not a collision.
        method_map = {proto.__name__: get_own_protocol_methods(proto) for proto in SNOWFLAKE_PROTOCOLS}

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


class TestTheBackendOwnAnswersAreTheEffectiveOnes:
    """A backend mixin's method must resolve to a backend class.

    The other checks in this file are about the *declaration*: the mixin
    declares the method, and the protocol declares it too. This one is
    about the *resolution*. A core class that wins the MRO makes the
    backend's implementation dead code, and the answer a caller gets is
    core's rather than the backend's -- so the backend never says what it
    means about itself, and nothing else in the suite notices: the
    declaration is there either way.

    A protocol class is a declaration rather than an implementation (its
    body is ``...``), so a core class may legitimately precede it; only
    the mixins are held to this.
    """

    def test_no_backend_method_is_shadowed_by_a_core_class(self):
        mro = type(SnowflakeDialect(version=(8, 0, 0))).__mro__
        own = "rhosocial.activerecord.backend.impl.snowflake"
        shadowed = []
        for klass in mro:
            if not klass.__module__.startswith(own):
                continue
            if not klass.__name__.endswith("Mixin"):
                continue
            for name in vars(klass):
                if not name.startswith(("format_", "supports_", "get_")):
                    continue
                if not callable(vars(klass)[name]):
                    continue
                winner = next((k for k in mro if name in k.__dict__), None)
                if winner is None or winner.__module__.startswith(own):
                    continue
                shadowed.append(f"{klass.__name__}.{name} -> {winner.__name__}")
        assert not shadowed, (
            "a core class wins these backend methods, so the backend's "
            f"implementation is dead code: {shadowed}"
        )
