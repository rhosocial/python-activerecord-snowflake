# src/rhosocial/activerecord/backend/impl/snowflake/mixins/clone.py
"""SnowflakeCloneMixin — CLONE operation support.

Snowflake CLONE is a zero-copy operation that shares storage with the
source object. It is supported at database, schema and table level.
"""


class SnowflakeCloneMixin:
    """Mixin for Snowflake CLONE operation support."""

    def supports_clone(self) -> bool:
        """Snowflake supports CLONE operations."""
        return True
