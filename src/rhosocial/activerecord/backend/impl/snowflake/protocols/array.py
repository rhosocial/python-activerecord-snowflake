# src/rhosocial/activerecord/backend/impl/snowflake/protocols/array.py
"""Snowflake ARRAY type protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake ARRAY type supports:
- Array construction: [1, 2, 3] or ARRAY_CONSTRUCT(1, 2, 3)
- Array access: arr[0] or arr[INDEX]
- ARRAY_APPEND, ARRAY_INSERT, ARRAY_REMOVE, etc.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/data-types-semistructured
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class SnowflakeArraySupport(Protocol):
    """Snowflake ARRAY type protocol."""

    def supports_array_type(self) -> bool:
        """Whether ARRAY type is supported."""
        ...

    def format_array_construct(self, elements: str) -> str:
        """Format array construction expression."""
        ...

    def format_array_access(self, array_expr: str, index: str) -> str:
        """Format array element access expression."""
        ...