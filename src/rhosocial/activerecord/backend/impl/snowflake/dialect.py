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
from typing import Any, List, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.dialect.protocols import (
    AdvancedGroupingSupport,
    ArraySupport,
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
    PartitionSupport,
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
)
from rhosocial.activerecord.backend.dialect.mixins import (
    AdvancedGroupingMixin,
    ArrayMixin,
    CollationMixin,
    ConstraintMixin,
    CTEMixin,
    DDLColumnMixin,
    DDLTypeMixin,
    DateTimeMixin,
    DMLMixin,
    DQLMixin,
    ExplainMixin,
    ExpressionMixin,
    FilterClauseMixin,
    IdentifierMixin,
    IndexMixin,
    IntrospectionMixin,
    JoinMixin,
    JSONMixin,
    LateralJoinMixin,
    MergeMixin,
    PredicateMixin,
    QualifyClauseMixin,
    ReturningMixin,
    SchemaMixin,
    SequenceMixin,
    SetOperationMixin,
    TableMixin,
    TransactionControlMixin,
    UpsertMixin,
    ViewMixin,
    WindowFunctionMixin,
)
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from .collation import validate_snowflake_collation_name
from .protocols import (
    SnowflakeArraySupport,
    SnowflakeCloneSupport,
    SnowflakePartitionSupport,
    SnowflakeStageSupport,
    SnowflakeTimeTravelSupport,
    SnowflakeVariantSupport,
)
from .mixins import (
    SnowflakeArrayMixin,
    SnowflakeCloneMixin,
    SnowflakeIntrospectionMixin,
    SnowflakeJSONMixin,
    SnowflakePartitionMixin,
    SnowflakeStageMixin,
    SnowflakeTimeTravelMixin,
    SnowflakeTransactionMixin,
    SnowflakeTypeSupportMixin,
    SnowflakeVariantMixin,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.collation import CollateExpression
    from rhosocial.activerecord.backend.expression.statements import (
        CreateTableExpression, CreateViewExpression, DropViewExpression,
        ColumnDefinition, TableConstraint, IndexDefinition,
        ExplainExpression, InsertExpression,
    )


class SnowflakeDialect(
    SQLDialectBase,
    # New Mixins (shared by all modern backends)
    IdentifierMixin,
    PredicateMixin,
    ExpressionMixin,
    DateTimeMixin,
    DQLMixin,
    DMLMixin,
    DDLColumnMixin,
    SnowflakeTypeSupportMixin,
    TransactionControlMixin,
    SetOperationMixin,
    SequenceMixin,
    # Standard SQL mixins
    CollationMixin,
    CTEMixin,
    FilterClauseMixin,
    WindowFunctionMixin,
    SnowflakeJSONMixin,     # Must be before JSONMixin to override format_json_expression
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
    ReturningMixin,
    # Snowflake-specific mixins (before generic IntrospectionMixin to override methods)
    SnowflakeTransactionMixin,
    SnowflakeTimeTravelMixin,
    SnowflakeVariantMixin,
    SnowflakeArrayMixin,
    SnowflakeCloneMixin,
    SnowflakeStageMixin,
    SnowflakePartitionMixin,
    SnowflakeIntrospectionMixin,  # Must be before IntrospectionMixin
    IntrospectionMixin,
    # Protocol supports (for isinstance checks)
    AdvancedGroupingSupport,
    ArraySupport,
    CollationSupport,
    CTESupport,
    ConstraintSupport,
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
    PartitionSupport,
    # Snowflake-specific protocol supports
    SnowflakePartitionSupport,
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

    # ========== Identifier & Parameter Formatting ==========

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

    # ========== DateTime Formatting (Snowflake-specific override) ==========

    def format_interval_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        """Format an INTERVAL expression for Snowflake.

        Snowflake uses INTERVAL 'value' unit syntax.

        Args:
            expr: The interval expression.

        Returns:
            Tuple of (SQL string, parameters).
        """
        value = self._escape_sql_string(str(expr.value))
        sql = f"INTERVAL '{value}' {expr.unit.value.upper()}"
        return self._apply_value_expression_modifiers(sql, (), expr)

    def format_datetime_add_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        """Format a date/time addition expression using Snowflake DATEADD.

        Args:
            expr: The date/time add expression.

        Returns:
            Tuple of (SQL string, parameters).
        """
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        sql = f"DATEADD({unit}, %s, {source_sql})"
        return self._apply_value_expression_modifiers(
            sql, (expr.interval.value,) + source_params, expr
        )

    def format_datetime_subtract_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        """Format a date/time subtraction expression using Snowflake DATEADD.

        Snowflake does not have a native date subtraction operator,
        so DATEADD with a negative value is used.

        Args:
            expr: The date/time subtract expression.

        Returns:
            Tuple of (SQL string, parameters).
        """
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        sql = f"DATEADD({unit}, %s, {source_sql})"
        return self._apply_value_expression_modifiers(
            sql, (-expr.interval.value,) + source_params, expr
        )

    def format_datetime_diff_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        """Format a date/time difference expression using Snowflake DATEDIFF.

        Args:
            expr: The date/time diff expression.

        Returns:
            Tuple of (SQL string, parameters).
        """
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        sql = f"DATEDIFF({expr.unit.value.upper()}, {start_sql}, {end_sql})"
        return self._apply_value_expression_modifiers(sql, start_params + end_params, expr)

    def format_set_transaction(self, expr) -> Tuple[str, tuple]:
        """Format SET TRANSACTION statement for Snowflake.

        Snowflake only supports READ COMMITTED isolation level, so
        no SET TRANSACTION is needed.

        Args:
            expr: The set transaction expression.

        Returns:
            Tuple of (SQL string, parameters) - empty no-op.
        """
        return ("", ())

    def supports_collate_expression(self) -> bool:
        """Snowflake supports expression-level COLLATE."""
        return True

    def validate_collation_name(self, expr: "CollateExpression") -> str:
        """Validate Snowflake collation specs and return their SQL representation."""
        if expr.collation_options:
            unsupported = ", ".join(sorted(expr.collation_options))
            raise UnsupportedFeatureError(self.name, f"COLLATE options: {unsupported}")
        spec = validate_snowflake_collation_name(expr.collation_name, getattr(self, "version", None))
        return f"'{self._escape_sql_string(spec)}'"

    # ========== DDLType Support ==========

    def format_data_type(self, data_type: "Any") -> "Tuple[str, tuple]":
        """Render a DataType into a Snowflake SQL type string.

        Args:
            data_type: The DataType instance to format.

        Returns:
            Tuple of (SQL type string, params).
        """
        from .expression.types import SnowflakeDataTypeMixin
        if isinstance(data_type, SnowflakeDataTypeMixin):
            return data_type.format_type(self), ()
        from rhosocial.activerecord.backend.expression.types._base import DataType
        if hasattr(data_type, 'ddl') and callable(data_type.ddl):
            return data_type.ddl, ()
        if isinstance(data_type, DataType):
            return data_type.__class__.__name__.replace("Type", "").upper(), ()
        return str(data_type), ()

    def parse_type(self, raw: str) -> "Any":
        """Parse a raw Snowflake type string into a DataType.

        Delegates to SnowflakeTypeSupportMixin.parse_type for
        structured type parsing.

        Args:
            raw: Raw SQL type string.

        Returns:
            A DataType instance.
        """
        return SnowflakeTypeSupportMixin.parse_type(self, raw)

    def supports_data_types(self) -> List[Tuple["Any", str]]:
        """List (DataTypeClass, sql_name) pairs supported by this dialect.

        Returns:
            List of (DataTypeClass, sql_name) tuples.
        """
        from .expression.types import (
            SnowflakeVarcharType, SnowflakeNumberType, SnowflakeBooleanType,
            SnowflakeTimestampLtzType, SnowflakeTimestampNtzType, SnowflakeTimestampTzType,
            SnowflakeVariantType, SnowflakeArrayType, SnowflakeObjectType,
            SnowflakeGeographyType, SnowflakeGeometryType,
            SnowflakeDateType, SnowflakeTimeType, SnowflakeBinaryType,
        )
        return [
            (SnowflakeVarcharType, "VARCHAR"),
            (SnowflakeNumberType, "NUMBER"),
            (SnowflakeBooleanType, "BOOLEAN"),
            (SnowflakeTimestampLtzType, "TIMESTAMP_LTZ"),
            (SnowflakeTimestampNtzType, "TIMESTAMP_NTZ"),
            (SnowflakeTimestampTzType, "TIMESTAMP_TZ"),
            (SnowflakeVariantType, "VARIANT"),
            (SnowflakeArrayType, "ARRAY"),
            (SnowflakeObjectType, "OBJECT"),
            (SnowflakeGeographyType, "GEOGRAPHY"),
            (SnowflakeGeometryType, "GEOMETRY"),
            (SnowflakeDateType, "DATE"),
            (SnowflakeTimeType, "TIME"),
            (SnowflakeBinaryType, "BINARY"),
        ]

    # ========== SetOperation Support ==========

    def supports_union(self) -> bool:
        """Snowflake supports UNION."""
        return True

    def supports_union_all(self) -> bool:
        """Snowflake supports UNION ALL."""
        return True

    def supports_intersect(self) -> bool:
        """Snowflake supports INTERSECT."""
        return True

    def supports_except(self) -> bool:
        """Snowflake supports EXCEPT/MINUS."""
        return True

    def supports_set_operation_order_by(self) -> bool:
        """Snowflake supports ORDER BY in set operations."""
        return True

    def supports_set_operation_limit_offset(self) -> bool:
        """Snowflake supports LIMIT/OFFSET in set operations."""
        return True

    def supports_set_operation_for_update(self) -> bool:
        """Snowflake does not support FOR UPDATE in set operations."""
        return False

    # ========== DQL Support ==========

    def supports_offset_without_limit(self) -> bool:
        """Snowflake supports OFFSET without LIMIT."""
        return True

    def supports_for_update(self) -> bool:
        """Snowflake does not support FOR UPDATE clause."""
        return False

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

    def supports_returning_insert(self) -> bool:
        """Snowflake supports RETURNING for INSERT from version 7.32.0+."""
        return self.version >= (7, 32, 0)

    def supports_returning_update(self) -> bool:
        """Snowflake supports RETURNING for UPDATE from version 7.32.0+."""
        return self.version >= (7, 32, 0)

    def supports_returning_delete(self) -> bool:
        """Snowflake supports RETURNING for DELETE from version 7.32.0+."""
        return self.version >= (7, 32, 0)

    def supports_filter_clause(self) -> bool:
        """Snowflake supports FILTER clause."""
        return True

    def supports_indexes(self) -> bool:
        """Snowflake supports indexes (clustering keys and search optimization)."""
        return True

    def supports_constraints(self) -> bool:
        """Snowflake supports constraints (PK, FK, UNIQUE, NOT NULL, CHECK)."""
        return True

    def supports_sequences(self) -> bool:
        """Snowflake supports sequences."""
        return True

    def supports_explicit_inner_join(self) -> bool:
        """Snowflake supports explicit INNER JOIN syntax."""
        return True

    def supports_add_constraint(self) -> bool:
        """Snowflake supports ALTER TABLE ADD CONSTRAINT."""
        return True

    def supports_drop_constraint(self) -> bool:
        """Snowflake supports ALTER TABLE DROP CONSTRAINT."""
        return True

    def supports_modify_column(self) -> bool:
        """Snowflake supports ALTER TABLE MODIFY COLUMN."""
        return True

    # ========== Snowflake-Specific Capability Detection ==========

    def supports_array_type(self) -> bool:
        """Snowflake supports ARRAY type."""
        return True

    # ========== Snowflake-Specific SQL Formatting ==========

    # Time travel, VARIANT, ARRAY, CLONE, and stage formatting methods
    # are provided by the corresponding Mixins above.