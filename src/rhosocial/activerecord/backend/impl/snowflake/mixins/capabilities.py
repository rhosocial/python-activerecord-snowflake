# src/rhosocial/activerecord/backend/impl/snowflake/mixins/capabilities.py
"""Snowflake capability detection mixin."""
from typing import Tuple


class SnowflakeCapabilityMixin:
    """Snowflake capability detection.

    Aggregated capability checks for Snowflake features.
    """

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

    def supports_create_or_replace_view(self) -> bool:
        """Snowflake supports CREATE OR REPLACE VIEW."""
        return True

    def supports_if_not_exists_view(self) -> bool:
        """Snowflake supports CREATE VIEW IF NOT EXISTS."""
        return True

    def supports_introspection(self) -> bool:
        """Snowflake supports introspection."""
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

    def supports_if_exists_table(self) -> bool:
        """Snowflake supports DROP TABLE IF EXISTS."""
        return True

    def supports_drop_table_cascade(self) -> bool:
        """Snowflake does not support standard CASCADE for DROP TABLE."""
        return False

    def supports_alter_column_type(self) -> bool:
        """Snowflake changes a column type in place via MODIFY COLUMN."""
        return True

    def alter_column_type_action(self, old_col, new_col):
        """Build the in-place type-change action (MODIFY COLUMN)."""
        from rhosocial.activerecord.backend.expression.statements.ddl_alter import ModifyColumn

        return ModifyColumn(self, column=new_col)

    def format_modify_column_action(self, action) -> Tuple[str, tuple]:
        """Render Snowflake ALTER TABLE ... MODIFY COLUMN <col> <type>."""
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

    def supports_alter_column_properties(self) -> bool:
        """Snowflake has no independent ALTER COLUMN SET DEFAULT clause."""
        return False

    def supports_alter_table_index_actions(self) -> bool:
        """Snowflake has no traditional indexes."""
        return False


__all__ = ['SnowflakeCapabilityMixin']
