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
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Union

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.dialect.protocols import (
    CTESupport,
    FilterClauseSupport,
    WindowFunctionSupport,
    MergeSupport,
    AdvancedGroupingSupport,
    ArraySupport,
    ExplainSupport,
    QualifyClauseSupport,
    UpsertSupport,
    LateralJoinSupport,
    JoinSupport,
    ViewSupport,
    SchemaSupport,
    IndexSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TransactionControlSupport,
    SQLFunctionSupport,
    JSONSupport,
)
from rhosocial.activerecord.backend.dialect.mixins import (
    CTEMixin,
    FilterClauseMixin,
    WindowFunctionMixin,
    JSONMixin,
    AdvancedGroupingMixin,
    ArrayMixin,
    ExplainMixin,
    MergeMixin,
    QualifyClauseMixin,
    UpsertMixin,
    LateralJoinMixin,
    JoinMixin,
    ViewMixin,
    SchemaMixin,
    IndexMixin,
    TableMixin,
    ConstraintMixin,
    IntrospectionMixin,
)
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from .protocols import (
    SnowflakeTimeTravelSupport,
    SnowflakeVariantSupport,
    SnowflakeArraySupport,
    SnowflakeCloneSupport,
    SnowflakeStageSupport,
)
from .mixins import (
    SnowflakeTransactionMixin,
    SnowflakeTimeTravelMixin,
    SnowflakeVariantMixin,
    SnowflakeArrayMixin,
    SnowflakeCloneMixin,
    SnowflakeStageMixin,
    SnowflakeIntrospectionMixin,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        CreateTableExpression, CreateViewExpression, DropViewExpression,
        ColumnDefinition, TableConstraint, IndexDefinition,
        ExplainExpression, InsertExpression,
    )


class SnowflakeDialect(
    SQLDialectBase,
    # Standard SQL mixins
    CTEMixin,
    FilterClauseMixin,
    WindowFunctionMixin,
    JSONMixin,
    AdvancedGroupingMixin,
    ArrayMixin,
    ExplainMixin,
    MergeMixin,
    QualifyClauseMixin,
    UpsertMixin,
    LateralJoinMixin,
    JoinMixin,
    ViewMixin,
    SchemaMixin,
    IndexMixin,
    TableMixin,
    ConstraintMixin,
    # Snowflake-specific mixins (before generic IntrospectionMixin to override methods)
    SnowflakeTransactionMixin,
    SnowflakeTimeTravelMixin,
    SnowflakeVariantMixin,
    SnowflakeArrayMixin,
    SnowflakeCloneMixin,
    SnowflakeStageMixin,
    SnowflakeIntrospectionMixin,  # Must be before IntrospectionMixin
    IntrospectionMixin,
    # Protocol supports (for isinstance checks)
    CTESupport,
    FilterClauseSupport,
    WindowFunctionSupport,
    JSONSupport,
    AdvancedGroupingSupport,
    ArraySupport,
    ExplainSupport,
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
    TransactionControlSupport,
    SQLFunctionSupport,
    # Snowflake-specific protocol supports
    SnowflakeTimeTravelSupport,
    SnowflakeVariantSupport,
    SnowflakeArraySupport,
    SnowflakeCloneSupport,
    SnowflakeStageSupport,
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
        self.version = version

    # ========== Identifier Formatting ==========

    def format_identifier(self, identifier: str) -> str:
        """Format an identifier (table name, column name, etc.) with double quotes.

        Snowflake uses double quotes for identifier quoting, which is the SQL standard.

        Args:
            identifier: The identifier to format.

        Returns:
            The quoted identifier string.
        """
        return f'"{identifier}"'

    def get_parameter_placeholder(self, index: int = 0) -> str:
        """Get the parameter placeholder for Snowflake.

        Snowflake uses pyformat style (%s) with snowflake-connector-python.

        Args:
            index: Parameter index (not used for pyformat style).

        Returns:
            The parameter placeholder string.
        """
        return "%s"

    # ========== Capability Detection ==========

    def supports_cte(self) -> bool:
        """Snowflake supports CTEs including recursive CTEs."""
        return True

    def supports_recursive_cte(self) -> bool:
        """Snowflake supports recursive CTEs."""
        return True

    def supports_window_functions(self) -> bool:
        """Snowflake supports window functions."""
        return True

    def supports_json_operations(self) -> bool:
        """Snowflake supports JSON via VARIANT type."""
        return True

    def supports_merge(self) -> bool:
        """Snowflake supports MERGE INTO with complex conditions."""
        return True

    def supports_qualify_clause(self) -> bool:
        """Snowflake supports QUALIFY clause for window function filtering."""
        return True

    def supports_upsert(self) -> bool:
        """Snowflake supports upsert via MERGE."""
        return True

    def supports_lateral_join(self) -> bool:
        """Snowflake supports LATERAL joins."""
        return True

    def supports_explain(self) -> bool:
        """Snowflake supports EXPLAIN."""
        return True

    def supports_advanced_grouping(self) -> bool:
        """Snowflake supports GROUPING SETS, ROLLUP, CUBE."""
        return True

    def supports_arrays(self) -> bool:
        """Snowflake supports ARRAY type natively."""
        return True

    def supports_schema(self) -> bool:
        """Snowflake uses a three-level namespace (database.schema.table)."""
        return True

    def supports_views(self) -> bool:
        """Snowflake supports views."""
        return True

    def supports_introspection(self) -> bool:
        """Snowflake supports introspection via INFORMATION_SCHEMA."""
        return True

    def supports_returning_clause(self) -> bool:
        """Snowflake supports RETURNING clause from version 7.32.0+.

        RETURNING was introduced as a Preview feature and has been
        progressively GA'd. Users on older versions can override
        via SnowflakeConnectionConfig.enable_returning.
        """
        return self.version >= (7, 32, 0)

    # ========== Snowflake-Specific Capability Detection ==========

    # Time travel, VARIANT, CLONE, and stage capabilities
    # are provided by SnowflakeTimeTravelMixin, SnowflakeVariantMixin,
    # SnowflakeCloneMixin, and SnowflakeStageMixin.

    # Note: supports_array_type() must be overridden here because the generic
    # ArrayMixin in the MRO returns False and takes precedence over
    # SnowflakeArrayMixin's True.

    def supports_array_type(self) -> bool:
        """Snowflake supports ARRAY type."""
        return True

    # ========== Snowflake-Specific SQL Formatting ==========

    # Time travel, VARIANT, ARRAY, CLONE, and stage formatting methods
    # are provided by the corresponding Mixins above.
