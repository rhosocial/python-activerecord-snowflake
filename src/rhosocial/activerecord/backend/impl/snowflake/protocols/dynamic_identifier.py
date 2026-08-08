# src/rhosocial/activerecord/backend/impl/snowflake/protocols/dynamic_identifier.py
"""Snowflake dynamic identifier protocol.

Feature Source: Snowflake native (not SQL standard)

``IDENTIFIER()`` binds a value supplied at runtime as an object identifier
instead of a string literal. The placeholder comes from the dialect and the
value is bound as a parameter, avoiding SQL injection.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/identifier-literal
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class SnowflakeDynamicIdentifierSupport(Protocol):
    """Snowflake IDENTIFIER() dynamic binding protocol."""

    def supports_dynamic_identifier(self) -> bool:
        """Whether dynamic identifier binding is supported."""
        ...

    def format_identifier_dynamic(self, identifier: str) -> str:
        """Format an ``IDENTIFIER(placeholder)`` dynamic object reference."""
        ...
