# src/rhosocial/activerecord/backend/impl/snowflake/mixins/clone.py
"""SnowflakeCloneMixin — CLONE operation formatting.

Snowflake CLONE is a zero-copy operation that shares storage with the
source object. It is supported at database, schema and table level.
"""


class SnowflakeCloneMixin:
    """Mixin for Snowflake CLONE operation support."""

    def supports_clone(self) -> bool:
        """Snowflake supports CLONE operations."""
        return True

    def format_clone_table(self, target: str, source: str) -> str:
        """Format CREATE TABLE ... CLONE statement."""
        return f'CREATE TABLE {target} CLONE {source}'

    def format_clone_schema(self, target: str, source: str) -> str:
        """Format CREATE SCHEMA ... CLONE statement."""
        return f'CREATE SCHEMA {target} CLONE {source}'

    def format_clone_database(self, target: str, source: str) -> str:
        """Format CREATE DATABASE ... CLONE statement."""
        return f'CREATE DATABASE {target} CLONE {source}'