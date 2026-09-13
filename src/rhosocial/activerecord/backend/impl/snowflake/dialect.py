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
from rhosocial.activerecord.backend.expression.types import (
    BigIntType, BooleanType, CharType, DateTimeType, DateType, DecimalType,
    DoubleType, FloatType, IntegerType, JsonType, SmallIntType, TextType,
    TimeType, TimestampType, VarCharType, BlobType,
)
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
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.collation import CollateExpression


class SnowflakeDialect(
    SQLDialectBase,
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
    SnowflakeWarehouseMixin,
    SnowflakeStreamMixin,
    SnowflakeTaskMixin,
    SnowflakePipeMixin,
    SnowflakeFileFormatMixin,
    SnowflakeRoutineMixin,
    SnowflakeUndropMixin,
    SnowflakeTableModifierMixin,
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

    # ========== Identifier & Parameter Formatting ==========


    def get_parameter_placeholder(self, index: int = 0) -> str:
        """Get the parameter placeholder for Snowflake.

        Snowflake uses pyformat style (%s) with snowflake-connector-python.

        Args:
            index: Parameter index (not used for pyformat style).

        Returns:
            The parameter placeholder string.
        """
        return "%s"

    def supports_dynamic_identifier(self) -> bool:
        """Snowflake supports IDENTIFIER() dynamic binding."""
        return True

    def format_identifier_dynamic(self, identifier: str) -> str:
        """Format an ``IDENTIFIER(placeholder)`` dynamic object reference.

        Object names supplied at runtime must be wrapped in ``IDENTIFIER()``
        so Snowflake treats the bound parameter value as an identifier instead
        of a string literal. The placeholder is produced by the dialect and the
        actual value is bound as a parameter, preventing SQL injection.

        Args:
            identifier: The object name to bind dynamically (used only for
                the parameter value by the caller).

        Returns:
            The ``IDENTIFIER(%s)`` SQL fragment using the dialect placeholder.
        """
        placeholder = self.get_parameter_placeholder()
        return f"IDENTIFIER({placeholder})"

    # ========== DateTime Formatting (Snowflake-specific override) ==========


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
        return self.apply_alias(
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
        return self.apply_alias(
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
        return self.apply_alias(sql, start_params + end_params, expr)

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




    # ========== supports_data_type_<name> (1:1 with format_data_type_<name>) ==========

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

    # ========== suggested_data_types ==========


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


    # ========== DQL Support ==========

    def supports_offset_without_limit(self) -> bool:
        """Snowflake supports OFFSET without LIMIT."""
        return True


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



    def supports_modify_column(self) -> bool:
        """Snowflake supports ALTER TABLE MODIFY COLUMN."""
        return True

    # region CreateTableExpressionDiffSupport hooks

    def _supports_alter_column_type(self) -> bool:
        """Snowflake changes a column type in place via ``MODIFY COLUMN``.
        The accompanying formatter is overridden below."""
        return True

    def alter_column_type_action(self, old_col, new_col):
        """Build the in-place type-change action (``MODIFY COLUMN``)."""
        from rhosocial.activerecord.backend.expression.statements.ddl_alter import ModifyColumn

        return ModifyColumn(self, column=new_col)

    def format_modify_column_action(self, action) -> Tuple[str, tuple]:
        """Render Snowflake ``ALTER TABLE ... MODIFY COLUMN <col> <type>``.

        Snowflake redefines a column wholesale with ``MODIFY COLUMN`` carrying
        the full new definition (type + constraints). ``DEFAULT``/``NOT NULL``
        ride along inside the rendered column spec.
        """
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            ColumnConstraintType,
        )

        col = action.column
        type_sql, _ = self.format_data_type(col.data_type)
        parts = [type_sql]
        for c in col.constraints:
            if c.constraint_type == ColumnConstraintType.NOT_NULL:
                parts.append("NOT NULL")
            elif c.constraint_type == ColumnConstraintType.NULL:
                parts.append("NULL")
            elif c.constraint_type == ColumnConstraintType.DEFAULT and c.default_value is not None:
                from rhosocial.activerecord.backend.expression.core import Literal

                lit_sql, lit_params = Literal(self, c.default_value).to_sql()
                parts.append(f"DEFAULT {lit_sql}")
        spec = " ".join(parts)
        return f"MODIFY COLUMN {self.format_identifier(col.name)} {spec}", ()

    def _supports_alter_column_properties(self) -> bool:
        """Snowflake has no independent ``ALTER COLUMN SET DEFAULT`` clause;
        property changes ride inside ``MODIFY COLUMN``. The generic diff path
        emits standalone ``ALTER COLUMN SET/DROP DEFAULT`` actions, which
        Snowflake rejects — route property-only changes to a rebuild.
        """
        return False

    def _supports_alter_table_index_actions(self) -> bool:
        """Snowflake has no traditional indexes (only SEARCH INDEX via a
        separate statement) — index changes route to a rebuild plan.
        """
        return False

    # endregion

    # ========== Generated Column Support ==========

    def supports_generated_columns(self) -> bool:
        """Snowflake supports generated (computed) columns."""
        return True

    def supports_stored_generated_columns(self) -> bool:
        """Snowflake generated columns are virtual only; STORED is unsupported."""
        return False

    def supports_virtual_generated_columns(self) -> bool:
        """Snowflake exposes generated columns as virtual columns.

        Snowflake computes the value at query time from ``[GENERATED ALWAYS]
        AS (<expr>) [VIRTUAL]``.
        """
        return True

    # ========== ILIKE Support ==========

    def supports_ilike(self) -> bool:
        """Snowflake supports the native ILIKE operator."""
        return True

    def format_ilike_expression(self, column, pattern: str, negate: bool = False):
        """Format a native Snowflake ``[NOT] ILIKE`` expression.

        Snowflake's ILIKE operator performs case-insensitive matching, so
        no LOWER() workaround is needed.
        """
        if isinstance(column, str):
            col_sql = self.format_identifier(column)
        elif hasattr(column, "to_sql"):
            col_sql, _ = column.to_sql()
        else:
            col_sql = str(column)
        operator = "NOT ILIKE" if negate else "ILIKE"
        return f"{col_sql} {operator} %s", (pattern,)

    # ========== Ordered-Set Aggregation Support ==========

    def supports_ordered_set_aggregation(self) -> bool:
        """Snowflake supports ``WITHIN GROUP (ORDER BY ...)`` aggregates.

        Snowflake renders ordered-set aggregates such as ``LISTAGG`` and
        ``ARRAY_AGG`` through ``WITHIN GROUP (ORDER BY ...)``; the standard
        formatting is provided by ``OrderedSetAggregationMixin``.
        """
        return True

    # ========== Truncate Support ==========

    def format_truncate_statement(self, expr) -> Tuple[str, tuple]:
        """Format Snowflake ``TRUNCATE TABLE <name>``.

        Snowflake's TRUNCATE has neither a ``RESTART IDENTITY`` nor a
        ``CASCADE`` option, so requesting either is rejected rather than
        silently emitting invalid SQL.
        """
        if expr.restart_identity:
            raise UnsupportedFeatureError(
                self.name,
                "TRUNCATE ... RESTART IDENTITY",
                suggestion="Snowflake TRUNCATE has no RESTART IDENTITY option.",
            )
        if expr.cascade:
            raise UnsupportedFeatureError(
                self.name,
                "TRUNCATE ... CASCADE",
                suggestion="Snowflake TRUNCATE has no CASCADE option.",
            )
        return f"TRUNCATE TABLE {self.format_identifier(expr.table_name)}", ()

    # ========== Snowflake-Specific Capability Detection ==========

    def supports_array_type(self) -> bool:
        """Snowflake supports ARRAY type."""
        return True

    # ========== Snowflake-Specific SQL Formatting ==========

    # Time travel, VARIANT, ARRAY, CLONE, and stage formatting methods
    # are provided by the corresponding Mixins above.