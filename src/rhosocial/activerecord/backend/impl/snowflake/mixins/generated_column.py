# src/rhosocial/activerecord/backend/impl/snowflake/mixins/generated_column.py
"""Snowflake generated column support mixin."""

from typing import Tuple


class SnowflakeGeneratedColumnMixin:
    """Snowflake generated (computed) column support."""

    def format_identity_clause(self, expr) -> Tuple[str, tuple]:
        """Snowflake uses ``IDENTITY(start, step)`` (synonym for AUTOINCREMENT).

        Snowflake does not accept the SQL-standard
        ``GENERATED ... AS IDENTITY`` form.
        """
        start = expr.start if expr.start is not None else 1
        increment = expr.increment if expr.increment is not None else 1
        return f" IDENTITY({start}, {increment})", ()

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
