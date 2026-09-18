# src/rhosocial/activerecord/backend/impl/snowflake/mixins/ordered_set_aggregation.py
"""Snowflake ordered-set aggregation support mixin."""


class SnowflakeOrderedSetAggregationMixin:
    """Snowflake WITHIN GROUP (ORDER BY ...) aggregate support."""

    def supports_ordered_set_aggregation(self) -> bool:
        """Snowflake supports WITHIN GROUP (ORDER BY ...) aggregates."""
        return True


__all__ = ['SnowflakeOrderedSetAggregationMixin']
