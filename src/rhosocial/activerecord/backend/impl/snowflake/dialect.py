"""Snowflake backend SQL dialect implementation.

This dialect implements protocols for features that Snowflake actually supports,
based on the Snowflake version provided at initialization.

Snowflake SQL is largely ANSI SQL compliant with extensions for:
- VARIANT/ARRAY/OBJECT semi-structured data types
- Time travel queries (AT/BEFORE)
- CLONE operations
- Stage-based data loading (COPY INTO)
- MERGE with complex conditions
- Warehouse-based compute management
"""
from typing import Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.transaction import (
        BeginTransactionExpression,
        SetTransactionExpression,
    )

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.dialect.protocols import (
    AdvancedGroupingSupport,
    AlterTypeSupport,
    ArraySupport,
    AutoIncrementColumnSupport,
    CollationSupport,
    ConstraintSupport,
    CreateTypeSupport,
    CTESupport,
    DDLTypeSupport,
    DropTypeSupport,
    ExplainSupport,
    FilterClauseSupport,
    GeneratedColumnSupport,
    ILIKESupport,
    IdentityColumnSupport,
    IndexObjectSupport,
    IntrospectionSupport,
    JSONSupport,
    JoinSupport,
    LateralJoinSupport,
    MaterializedViewObjectSupport,
    MergeSupport,
    NamespaceSupport,
    OrderedSetAggregationSupport,
    PartitionSupport,
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
from rhosocial.activerecord.backend.dialect.mixins import (

    ArrayMixin,
    AutoIncrementMixin,
    CollationMixin,
    CommentOnMixin,
    ConstraintMixin,
    CTEMixin,
    DDLColumnMixin,
    DateTimeMixin,
    DMLMixin,
    DQLMixin,
    # The object tree: one ``format_<kind>_object`` per kind, each rendering
    # through ``NamespaceMixin`` for the namespace levels. Snowflake overrides
    # none of them; ``db.schema.table`` falls out of the slots they are handed.
    DatabaseNameMixin,
    IndexNameMixin,
    MaterializedViewNameMixin,
    NamespaceMixin,
    RelationSourceMixin,
    SchemaNameMixin,
    SequenceNameMixin,
    TableNameMixin,
    TypeNameMixin,
    ViewNameMixin,
    ExplainMixin,
    ExpressionMixin,
    IdentityColumnMixin,
    ILIKEMixin,
    IndexMixin,
    IntrospectionMixin,
    JoinMixin,
    JSONMixin,
    LateralJoinMixin,
    MergeMixin,
    PredicateMixin,
    SchemaMixin,
    SequenceMixin,
    SetOperationMixin,
    TableMixin,
    TransactionControlMixin,
    TruncateMixin,
    UpsertMixin,
    ViewMixin,
    WindowFunctionMixin,
)

from .reserved_words import SNOWFLAKE_RESERVED_WORDS
from .protocols import (
    SnowflakeArraySupport,
    SnowflakeCloneSupport,
    SnowflakeDMLSupport,
    SnowflakeFileFormatSupport,
    SnowflakeMaterializedViewSupport,
    SnowflakePartitionSupport,
    SnowflakePipeSupport,
    SnowflakePivotSupport,
    SnowflakeRoutineSupport,
    SnowflakeSampleSupport,
    SnowflakeShowSupport,
    SnowflakeStageSupport,
    SnowflakeStreamSupport,
    SnowflakeTableModifierSupport,
    SnowflakeTaskSupport,
    SnowflakeTimeTravelSupport,
    SnowflakeUndropSupport,
    SnowflakeVariantSupport,
    SnowflakeWarehouseSupport,
)
from .mixins import (
    SnowflakeArrayMixin,
    SnowflakeCloneMixin,
    SnowflakeNamespaceMixin,
    SnowflakeDMLMixin,
    SnowflakeFileFormatMixin,
    SnowflakeIntrospectionMixin,
    SnowflakeMaterializedViewMixin,
    SnowflakePartitionMixin,
    SnowflakePipeMixin,
    SnowflakePivotMixin,
    SnowflakeRoutineMixin,
    SnowflakeSampleMixin,
    SnowflakeShowMixin,
    SnowflakeStageMixin,
    SnowflakeStreamMixin,
    SnowflakeTableModifierMixin,
    SnowflakeTaskMixin,
    SnowflakeTimeTravelMixin,
    SnowflakeTransactionMixin,
    SnowflakeTypeDDLMixin,
    SnowflakeTypeSupportMixin,
    SnowflakeUndropMixin,
    SnowflakeVariantMixin,
    SnowflakeAlterColumnModifierMixin,
    SnowflakeWarehouseMixin,
    SnowflakeSchemaMixin,
    SnowflakeDatabaseMixin,
    SnowflakeSequenceMixin,
    # New mixins from dialect.py split
    SnowflakeDateTimeMixin,
    SnowflakeCollationMixin,
    SnowflakeSetOperationMixin,
    SnowflakeDQLMixin,
    SnowflakeCapabilityMixin,
    SnowflakeILIKEMixin,
    SnowflakeGeneratedColumnMixin,
    SnowflakeOrderedSetAggregationMixin,
    SnowflakeTruncateMixin,
)


class SnowflakeDialect(
    SQLDialectBase,
    RelationSourceMixin,
    # The whole naming side, stated once: which namespace levels a name may
    # carry, and the rule that a database is never usable without a schema.
    # Placed before every ``*NameMixin`` below and before NamespaceMixin, so it
    # overrides the shared defaults; each ``*NameMixin`` in turn precedes
    # NamespaceMixin so its own ``format_*_object`` wins over the inherited one.
    SnowflakeNamespaceMixin,
    # The object tree. Each ``*NameMixin`` renders one object kind. The object
    # protocols name those ``format_*_object`` methods and inherit
    # ``NamespaceSupport``, so they come last and lose to both.
    # The object kinds Snowflake's own statements hold. Trigger, routine,
    # foreign-table, synonym, domain and property-graph objects are left out on
    # purpose: the engine either has none of them, or exposes them through a
    # statement of its own that carries a bare name. Naming one is not a
    # capability to claim where no statement asks for it.
    TableNameMixin,
    ViewNameMixin,
    MaterializedViewNameMixin,
    IndexNameMixin,
    SequenceNameMixin,
    TypeNameMixin,
    SchemaNameMixin,
    DatabaseNameMixin,
    NamespaceMixin,
    TableObjectSupport,
    ViewObjectSupport,
    MaterializedViewObjectSupport,
    IndexObjectSupport,
    SequenceObjectSupport,
    TypeObjectSupport,
    NamespaceSupport,
    # New Snowflake-specific mixins (BEFORE generic mixins they override)
    SnowflakeDateTimeMixin,
    SnowflakeCollationMixin,
    SnowflakeSetOperationMixin,
    SnowflakeDQLMixin,
    SnowflakeCapabilityMixin,
    SnowflakeILIKEMixin,
    SnowflakeGeneratedColumnMixin,
    SnowflakeOrderedSetAggregationMixin,
    SnowflakeTruncateMixin,
    # New Mixins (shared by all modern backends)
    PredicateMixin,
    ILIKEMixin,
    ExpressionMixin,
    DateTimeMixin,
    DQLMixin,
    SnowflakeDMLMixin,  # Before DMLMixin to override INSERT OVERWRITE rendering
    DMLMixin,
    SnowflakeAlterColumnModifierMixin,  # Before DDLColumnMixin to override format_*_action
    DDLColumnMixin,
    AutoIncrementMixin,
    IdentityColumnMixin,
    SnowflakeTypeDDLMixin,
    SnowflakeTypeSupportMixin,
    TransactionControlMixin,
    SetOperationMixin,
    # Deliberate: Snowflake's own sequence grammar, placed immediately before
    # the core ``SequenceMixin`` so its three formatters win. Core's emits
    # MINVALUE / MAXVALUE / CYCLE / CACHE / NO ORDER / OWNED BY, all of which
    # Snowflake rejects; the probes in SnowflakeCapabilityMixin (above) declare
    # which options this dialect does accept.
    SnowflakeSequenceMixin,
    SequenceMixin,
    # Standard SQL mixins
    CollationMixin,
    CTEMixin,

    WindowFunctionMixin,
    JSONMixin,

    SnowflakeArrayMixin,  # Before ArrayMixin
    ArrayMixin,
    ExplainMixin,
    MergeMixin,

    UpsertMixin,
    LateralJoinMixin,
    JoinMixin,
    SnowflakeMaterializedViewMixin,  # Before ViewMixin to override materialized view rendering
    ViewMixin,
    TruncateMixin,
    SnowflakeSchemaMixin,  # Before SchemaMixin to enable Snowflake schema DDL
    SnowflakeDatabaseMixin,
    SchemaMixin,
    IndexMixin,
    SnowflakeTableModifierMixin,  # Before TableMixin to override create-table capability flags
    TableMixin,
    ConstraintMixin,
    CommentOnMixin,
    # Snowflake-specific mixins (before generic IntrospectionMixin to override methods)
    SnowflakeTransactionMixin,
    SnowflakeTimeTravelMixin,
    SnowflakeVariantMixin,
    SnowflakeCloneMixin,
    SnowflakeStageMixin,
    SnowflakeWarehouseMixin,
    SnowflakeStreamMixin,
    SnowflakeTaskMixin,
    SnowflakePipeMixin,
    SnowflakeFileFormatMixin,
    SnowflakeRoutineMixin,
    SnowflakeUndropMixin,
    SnowflakePartitionMixin,
    SnowflakeSampleMixin,
    SnowflakePivotMixin,
    SnowflakeShowMixin,
    SnowflakeIntrospectionMixin,  # Must be before IntrospectionMixin
    IntrospectionMixin,
    # Protocol supports (for isinstance checks)
    AdvancedGroupingSupport,
    ArraySupport,
    AutoIncrementColumnSupport,
    CollationSupport,
    CTESupport,
    ConstraintSupport,
    DDLTypeSupport,
    CreateTypeSupport,
    AlterTypeSupport,
    DropTypeSupport,
    ExplainSupport,
    FilterClauseSupport,
    GeneratedColumnSupport,
    ILIKESupport,
    IdentityColumnSupport,
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
    PartitionSupport,
    # Snowflake-specific protocol supports
    SnowflakePartitionSupport,
    SnowflakeTimeTravelSupport,
    SnowflakeVariantSupport,
    SnowflakeArraySupport,
    SnowflakeCloneSupport,
    SnowflakeStageSupport,
    SnowflakeWarehouseSupport,
    SnowflakeStreamSupport,
    SnowflakeTaskSupport,
    SnowflakePipeSupport,
    SnowflakeFileFormatSupport,
    SnowflakeRoutineSupport,
    SnowflakeUndropSupport,
    SnowflakeMaterializedViewSupport,
    SnowflakeTableModifierSupport,
    SnowflakeSampleSupport,
    SnowflakePivotSupport,
    SnowflakeDMLSupport,
    SnowflakeShowSupport,
):
    """Snowflake SQL dialect implementation.

    Snowflake supports most ANSI SQL features plus:
    - CTEs (including recursive)
    - Window functions
    - MERGE with complex conditions
    - QUALIFY clause for window function filtering
    - JSON/VARIANT semi-structured data
    - Time travel queries
    - CLONE operations

    Version is represented as (major, minor, patch) and used for
    feature gating where applicable.
    """

    def __init__(
        self,
        version: Tuple[int, ...] = (8, 0, 0),
        **kwargs: Any,
    ) -> None:
        """Initialize Snowflake dialect with version.

        Args:
            version: Snowflake server version as (major, minor, patch) tuple.
        """
        super().__init__(**kwargs)
        self._reserved_words = SNOWFLAKE_RESERVED_WORDS
        self.version = version

    def get_parameter_placeholder(self, index: int = 0) -> str:
        """Get the parameter placeholder for Snowflake.

        Snowflake uses pyformat style (%s) with snowflake-connector-python.
        """
        return "%s"

    def supports_dynamic_identifier(self) -> bool:
        """Snowflake supports IDENTIFIER() dynamic binding."""
        return True

    def format_identifier_dynamic(self, identifier: str) -> str:
        """Format an IDENTIFIER(placeholder) dynamic object reference."""
        placeholder = self.get_parameter_placeholder()
        return f"IDENTIFIER({placeholder})"

    def format_begin_transaction(self, expr: "BeginTransactionExpression") -> Tuple[str, tuple]:
        """Format BEGIN TRANSACTION for Snowflake, consuming its mode pairs.

        Snowflake's BEGIN takes no transaction characteristics; in particular
        it has no ``DEFERRABLE`` / ``NOT DEFERRABLE`` mode, which
        :meth:`supports_deferrable_transaction` already answers ``False`` for,
        and no ``WAIT`` / ``NO WAIT`` clause, which
        :meth:`supports_transaction_wait` answers ``False`` for. The shared
        formatter renders a bare ``BEGIN`` and ignores these pairs, so each
        requested spelling is refused by name here instead of being silently
        dropped. With neither pair set the base rendering is unchanged.

        https://docs.snowflake.com/en/sql-reference/sql/begin
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        params = expr.get_params()
        self._refuse_transaction_wait(params, "BEGIN TRANSACTION")
        if params.get("deferrable"):
            raise UnsupportedFeatureError(
                self.name,
                "BEGIN TRANSACTION DEFERRABLE",
                suggestion="Snowflake does not support DEFERRABLE transactions.",
            )
        if params.get("not_deferrable"):
            raise UnsupportedFeatureError(
                self.name,
                "BEGIN TRANSACTION NOT DEFERRABLE",
                suggestion="Snowflake does not support DEFERRABLE transactions.",
            )
        return super().format_begin_transaction(expr)

    def format_set_transaction(self, expr: "SetTransactionExpression") -> Tuple[str, tuple]:
        """Format SET TRANSACTION statement for Snowflake.

        Snowflake only supports READ COMMITTED isolation level, so
        no SET TRANSACTION is needed and the statement renders as nothing.
        Its grammar has no ``WAIT`` / ``NO WAIT`` clause (and no SET
        TRANSACTION statement at all), so a requested spelling is refused by
        name rather than dropped along with the rest of the statement.

        https://docs.snowflake.com/en/sql-reference/sql/begin
        """
        self._refuse_transaction_wait(expr.get_params(), "SET TRANSACTION")
        return ("", ())

    # ========== DDLType Support ==========

    def supports_data_type_integer(self) -> bool:
        return True

    def supports_data_type_bigint(self) -> bool:
        return True

    def supports_data_type_smallint(self) -> bool:
        return True

    def supports_data_type_float(self) -> bool:
        return True

    def supports_data_type_double(self) -> bool:
        return True

    def supports_data_type_decimal(self) -> bool:
        return True

    def supports_data_type_boolean(self) -> bool:
        return True

    def supports_data_type_varchar(self) -> bool:
        return True

    def supports_data_type_char(self) -> bool:
        return True

    def supports_data_type_text(self) -> bool:
        return True

    def supports_data_type_blob(self) -> bool:
        return True

    def supports_data_type_datetime(self) -> bool:
        return True

    def supports_data_type_date(self) -> bool:
        return True

    def supports_data_type_time(self) -> bool:
        return True

    def supports_data_type_timestamp(self) -> bool:
        return True

    def supports_data_type_json(self) -> bool:
        return True

    def supports_data_type_snowflake_varchar(self) -> bool:
        return True

    def supports_data_type_snowflake_number(self) -> bool:
        return True

    def supports_data_type_snowflake_float(self) -> bool:
        return True

    def supports_data_type_snowflake_boolean(self) -> bool:
        return True

    def supports_data_type_snowflake_timestamp_ltz(self) -> bool:
        return True

    def supports_data_type_snowflake_timestamp_ntz(self) -> bool:
        return True

    def supports_data_type_snowflake_timestamp_tz(self) -> bool:
        return True

    def supports_data_type_snowflake_date(self) -> bool:
        return True

    def supports_data_type_snowflake_time(self) -> bool:
        return True

    def supports_data_type_snowflake_binary(self) -> bool:
        return True

    def supports_data_type_snowflake_variant(self) -> bool:
        return True

    def supports_data_type_snowflake_object(self) -> bool:
        return True

    def supports_data_type_snowflake_array(self) -> bool:
        return True

    def supports_data_type_snowflake_geography(self) -> bool:
        return True

    def supports_data_type_snowflake_geometry(self) -> bool:
        return True

    # ========== Snowflake-Specific SQL Formatting ==========

    # Time travel, VARIANT, ARRAY, CLONE, and stage formatting methods
    # are provided by the corresponding Mixins above.
