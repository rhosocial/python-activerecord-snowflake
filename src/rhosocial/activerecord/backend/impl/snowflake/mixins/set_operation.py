# src/rhosocial/activerecord/backend/impl/snowflake/mixins/set_operation.py
"""Snowflake set operation support mixin."""


class SnowflakeSetOperationMixin:
    """Snowflake set operation support.

    Snowflake supports UNION, UNION ALL, INTERSECT, EXCEPT,
    plus ORDER BY and LIMIT/OFFSET within set operations.
    """

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


__all__ = ['SnowflakeSetOperationMixin']
