# src/rhosocial/activerecord/backend/impl/snowflake/mixins/generated_column.py
"""Snowflake generated column support mixin."""


class SnowflakeGeneratedColumnMixin:
    """Snowflake generated (computed) column support."""

    def supports_generated_columns(self) -> bool:
        """Snowflake supports generated (computed) columns."""
        return True

    def supports_stored_generated_columns(self) -> bool:
        """Snowflake generated columns are virtual only; STORED is unsupported."""
        return False

    def supports_virtual_generated_columns(self) -> bool:
        """Snowflake exposes generated columns as virtual columns."""
        return True


__all__ = ['SnowflakeGeneratedColumnMixin']
