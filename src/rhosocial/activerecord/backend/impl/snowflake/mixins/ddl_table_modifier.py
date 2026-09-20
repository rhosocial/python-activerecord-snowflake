# src/rhosocial/activerecord/backend/impl/snowflake/mixins/table_modifier.py
"""SnowflakeTableModifierMixin — table DDL modifier support.

Snowflake table DDL differs from the SQL standard in several ways:
- ``CREATE [OR REPLACE] [TRANSIENT | TEMPORARY] TABLE`` header modifiers.
- ``DATA_RETENTION_TIME_IN_DAYS`` / ``CHANGE_TRACKING`` create options.
- ``CLUSTER BY (...)`` and ``DROP CLUSTERING KEY`` instead of indexes.
- ``ADD SEARCH OPTIMIZATION`` for fast equality/pruning lookups.

These formatters are independently callable; the generic core
``TableMixin`` CREATE TABLE renderer is not modified.
"""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..expression.partition import SnowflakeClusterByClause


class SnowflakeTableModifierMixin:
    """Mixin for Snowflake table DDL modifier support."""

    def supports_create_or_replace_table(self) -> bool:
        """Snowflake supports CREATE OR REPLACE TABLE."""
        return True

    def format_cluster_by_clause(self, expr: "SnowflakeClusterByClause") -> Tuple[str, tuple]:
        """Format ``CLUSTER BY ( <expr> [, ...] )`` clustering keys.

        Args:
            expr: SnowflakeClusterByClause carrying the clustering key expressions.

        Returns:
            Tuple of (SQL string, parameters tuple).
        """
        parts = []
        params = []
        for key in expr.keys:
            key_sql, key_params = key.to_sql()
            parts.append(key_sql)
            params.extend(key_params)
        return f" CLUSTER BY ({', '.join(parts)})", tuple(params)

    def supports_transient_table(self) -> bool:
        """Snowflake supports TRANSIENT tables."""
        return True

    def supports_cluster_by(self) -> bool:
        """Snowflake supports CLUSTER BY clustering keys."""
        return True

    def supports_search_optimization(self) -> bool:
        """Snowflake supports SEARCH OPTIMIZATION."""
        return True

    def supports_create_table_like(self) -> bool:
        """Snowflake supports CREATE TABLE ... LIKE (empty copy)."""
        return True

    def supports_create_table_clone(self) -> bool:
        """Snowflake supports CREATE TABLE ... CLONE (zero-copy copy)."""
        return True

    def supports_create_table_using_template(self) -> bool:
        """Snowflake supports CREATE TABLE ... USING TEMPLATE."""
        return True
