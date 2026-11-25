# src/rhosocial/activerecord/backend/impl/snowflake/mixins/__init__.py
"""Snowflake dialect-specific Mixin implementations.

This package provides shared non-I/O mixin classes for the Snowflake backend,
including backend mixin, transaction mixin, concurrency mixins, and
Snowflake-specific feature mixins for time travel, VARIANT, ARRAY,
CLONE, stage, warehouse, stream, task, pipe, file format, routine,
undrop, materialized view, table modifiers support.
"""

from .create_table_layout_suggestion import SnowflakeCreateTableLayoutSuggestionMixin
from .generated_value_suggestion import SnowflakeGeneratedValueSuggestionMixin
from .string_concatenation_suggestion import SnowflakeStringConcatenationSuggestionMixin
from .column_reorder_suggestion import SnowflakeColumnReorderSuggestionMixin
from .table_constraint_change_suggestion import SnowflakeTableConstraintChangeSuggestionMixin
from .table_index_change_suggestion import SnowflakeTableIndexChangeSuggestionMixin
from .partition_scheme_change_suggestion import SnowflakePartitionSchemeChangeSuggestionMixin
from .partition_build_suggestion import SnowflakePartitionBuildSuggestionMixin
from .partition_add_suggestion import SnowflakePartitionAddSuggestionMixin
from .partition_drop_suggestion import SnowflakePartitionDropSuggestionMixin
from .partition_retention_suggestion import SnowflakePartitionRetentionSuggestionMixin
from .partition_table_drop_suggestion import SnowflakePartitionTableDropSuggestionMixin
from .partition_table_alter_suggestion import SnowflakePartitionTableAlterSuggestionMixin
from .partition_split_suggestion import SnowflakePartitionSplitSuggestionMixin
from .partition_merge_suggestion import SnowflakePartitionMergeSuggestionMixin
from .array import SnowflakeArrayMixin
from .backend import SnowflakeBackendMixin
from .clone import SnowflakeCloneMixin
from .namespace import SnowflakeNamespaceMixin
from .dml import SnowflakeDMLMixin
from .file_format import SnowflakeFileFormatMixin
from .introspection import SnowflakeIntrospectionMixin
from .materialized_view import SnowflakeMaterializedViewMixin
from .partition import SnowflakePartitionMixin
from .pipe import SnowflakePipeMixin
from .pivot import SnowflakePivotMixin
from .routine import SnowflakeRoutineMixin
from .sample import SnowflakeSampleMixin
from .show import SnowflakeShowMixin
from .stage import SnowflakeStageMixin
from .stream import SnowflakeStreamMixin
from .ddl_table_modifier import SnowflakeTableModifierMixin
from .task import SnowflakeTaskMixin
from .time_travel import SnowflakeTimeTravelMixin
from .transaction import (
    AsyncSnowflakeConcurrencyMixin,
    SnowflakeConcurrencyMixin,
    SnowflakeTransactionMixin,
)
from .undrop import SnowflakeUndropMixin
from .variant import SnowflakeVariantMixin
from .types import SnowflakeTypeSupportMixin
from .column_type import SnowflakeColumnTypeMixin
from .data_type_suggestions import SnowflakeDataTypeSuggestionsMixin
from .warehouse import SnowflakeWarehouseMixin
from .ddl import SnowflakeAlterColumnModifierMixin
from .ddl_type import SnowflakeTypeDDLMixin
from .index import SnowflakeIndexMixin
# New mixins from dialect.py split
from .datetime import SnowflakeDateTimeMixin
from .collation import SnowflakeCollationMixin
from .trim import SnowflakeTrimMixin
from .set_operation import SnowflakeSetOperationMixin
from .dql import SnowflakeDQLMixin
from .capabilities import SnowflakeCapabilityMixin
from .constraint import SnowflakeConstraintMixin
from .ilike import SnowflakeILIKEMixin
from .generated_column import SnowflakeGeneratedColumnMixin
from .ordered_set_aggregation import SnowflakeOrderedSetAggregationMixin
from .truncate import SnowflakeTruncateMixin
from .wildcard import SnowflakeWildcardMixin
from .literal import SnowflakeLiteralValueMixin
from .schema import SnowflakeSchemaMixin
from .ddl_database import SnowflakeDatabaseMixin
from .sequence import SnowflakeSequenceMixin

__all__ = [
    'SnowflakeCreateTableLayoutSuggestionMixin',
    'SnowflakeGeneratedValueSuggestionMixin',
    'SnowflakePartitionBuildSuggestionMixin',
    'SnowflakePartitionAddSuggestionMixin',
    'SnowflakePartitionDropSuggestionMixin',
    'SnowflakePartitionRetentionSuggestionMixin',
    'SnowflakePartitionTableDropSuggestionMixin',
    'SnowflakePartitionTableAlterSuggestionMixin',
    'SnowflakePartitionSplitSuggestionMixin',
    'SnowflakePartitionMergeSuggestionMixin',
    'SnowflakeStringConcatenationSuggestionMixin',
    'SnowflakeColumnReorderSuggestionMixin',
    'SnowflakeTableConstraintChangeSuggestionMixin',
    'SnowflakeTableIndexChangeSuggestionMixin',
    'SnowflakePartitionSchemeChangeSuggestionMixin',
    "SnowflakeArrayMixin",
    "SnowflakeBackendMixin",
    "SnowflakeCloneMixin",
    "SnowflakeDMLMixin",
    "SnowflakeFileFormatMixin",
    "SnowflakeIntrospectionMixin",
    "SnowflakeMaterializedViewMixin",
    "SnowflakeNamespaceMixin",
    "SnowflakePartitionMixin",
    "SnowflakePipeMixin",
    "SnowflakePivotMixin",
    "SnowflakeRoutineMixin",
    "SnowflakeSampleMixin",
    "SnowflakeShowMixin",
    "SnowflakeStageMixin",
    "SnowflakeStreamMixin",
    "SnowflakeTableModifierMixin",
    "SnowflakeTaskMixin",
    "SnowflakeTimeTravelMixin",
    "SnowflakeTransactionMixin",
    "SnowflakeConcurrencyMixin",
    "AsyncSnowflakeConcurrencyMixin",
    "SnowflakeUndropMixin",
    "SnowflakeVariantMixin",
    "SnowflakeTypeSupportMixin",
    "SnowflakeColumnTypeMixin",
    "SnowflakeWarehouseMixin",
    "SnowflakeAlterColumnModifierMixin",
    "SnowflakeTypeDDLMixin",
    "SnowflakeIndexMixin",
    "SnowflakeDataTypeSuggestionsMixin",
    "SnowflakeDateTimeMixin",
    "SnowflakeCollationMixin",
    "SnowflakeTrimMixin",
    "SnowflakeSetOperationMixin",
    "SnowflakeDQLMixin",
    "SnowflakeCapabilityMixin",
    "SnowflakeConstraintMixin",
    "SnowflakeILIKEMixin",
    "SnowflakeGeneratedColumnMixin",
    "SnowflakeOrderedSetAggregationMixin",
    "SnowflakeTruncateMixin",
    "SnowflakeWildcardMixin",
    "SnowflakeLiteralValueMixin",
    "SnowflakeSchemaMixin",
    "SnowflakeDatabaseMixin",
    "SnowflakeSequenceMixin",
]
