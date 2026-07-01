# src/rhosocial/activerecord/backend/impl/snowflake/mixins/clone.py
"""SnowflakeCloneMixin — CLONE operation formatting."""


class SnowflakeCloneMixin:
    """Mixin for Snowflake CLONE operation support."""

    def supports_clone(self) -> bool:
        """Snowflake supports CLONE operations."""
        return True

    def format_clone_table(self, target: str, source: str) -> str:
        """Format CREATE TABLE ... CLONE statement."""
        return f'CREATE TABLE {target} CLONE {source}'