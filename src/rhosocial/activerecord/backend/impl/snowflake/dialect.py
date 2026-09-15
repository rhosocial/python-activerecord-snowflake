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
from typing import Any, Dict, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.transaction import (
        SetTransactionExpression,
    )

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.dialect.protocols import (
    AdvancedGroupingSupport,
    ArraySupport,
    AutoIncrementSupport,
    CollationSupport,
    ConstraintSupport,
    CTESupport,
    DDLTypeSupport,
    ExplainSupport,
    FilterClauseSupport,
    GeneratedColumnSupport,
    ILIKESupport,
    IndexSupport,
    IntrospectionSupport,
    JSONSupport,
    JoinSupport,
    LateralJoinSupport,
    MergeSupport,
    OrderedSetAggregationSupport,
    PartitionSupport,
    QualifyClauseSupport,
    ReturningSupport,
    SchemaSupport,
    SequenceSupport,
    SetOperationSupport,
    SQLFunctionSupport,
    TransactionControlSupport,
    TruncateSupport,
    UpsertSupport,
    ViewSupport,
    WildcardSupport,
    WindowFunctionSupport,
)
from rhosocial.activerecord.backend.dialect.mixins import (
    AdvancedGroupingMixin,
    ArrayMixin,
    AutoIncrementMixin,
    CollationMixin,
    ConstraintMixin,
    CTEMixin,
    DDLColumnMixin,
    DateTimeMixin,
    DMLMixin,
    DQLMixin,
    ExplainMixin,
    ExpressionMixin,
    FilterClauseMixin,
    ILIKEMixin,
    IndexMixin,
    IntrospectionMixin,
    JoinMixin,
    JSONMixin,
    LateralJoinMixin,
    MergeMixin,
    OrderedSetAggregationMixin,
    PredicateMixin,
    QualifyClauseMixin,
    ReturningMixin,
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
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from .collation import validate_snowflake_collation_name
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
    SnowflakeTypeSupportMixin,
    SnowflakeUndropMixin,
    SnowflakeVariantMixin,
    SnowflakeAlterColumnModifierMixin,
    SnowflakeWarehouseMixin,
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
    SnowflakeTypeSupportMixin,
    TransactionControlMixin,
    SetOperationMixin,
    SequenceMixin,
    # Standard SQL mixins
    CollationMixin,
    CTEMixin,
    FilterClauseMixin,
    WindowFunctionMixin,
    JSONMixin,
    AdvancedGroupingMixin,
    OrderedSetAggregationMixin,
    SnowflakeArrayMixin,  # Before ArrayMixin
    ArrayMixin,
    ExplainMixin,
    MergeMixin,
    QualifyClauseMixin,
    UpsertMixin,
    LateralJoinMixin,
    JoinMixin,
    SnowflakeMaterializedViewMixin,  # Before ViewMixin to override materialized view rendering
    ViewMixin,
    TruncateMixin,
    SchemaMixin,
    IndexMixin,
    SnowflakeTableModifierMixin,  # Before TableMixin to override create-table capability flags
    TableMixin,
    ConstraintMixin,
    ReturningMixin,
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
    AutoIncrementSupport,
    CollationSupport,
    CTESupport,
    ConstraintSupport,
    DDLTypeSupport,
    ExplainSupport,
    FilterClauseSupport,
    GeneratedColumnSupport,
    ILIKESupport,
    IndexSupport,
    IntrospectionSupport,
    JSONSupport,
    JoinSupport,
    LateralJoinSupport,
    MergeSupport,
    OrderedSetAggregationSupport,
    QualifyClauseSupport,
    ReturningSupport,
    SchemaSupport,
    SequenceSupport,
    SetOperationSupport,
    SQLFunctionSupport,
    TransactionControlSupport,
    TruncateSupport,
    UpsertSupport,
    ViewSupport,
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

    def __init__(self, version: Tuple[int, ...] = (8, 0, 0), **kwargs):
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

    def format_set_transaction(self, expr: "SetTransactionExpression") -> Tuple[str, tuple]:
        """Format SET TRANSACTION statement for Snowflake.

        Snowflake only supports READ COMMITTED isolation level, so
        no SET TRANSACTION is needed.
        """
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
