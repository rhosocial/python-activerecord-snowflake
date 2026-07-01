# src/rhosocial/activerecord/backend/impl/snowflake/protocols/variant.py
"""Snowflake VARIANT semi-structured data type protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake VARIANT type can store semi-structured data (JSON, Avro, ORC, Parquet).
Key operations:
- Path access: variant_col:path (dot notation) or variant_col['path']
- Type casting: variant_col:path::type
- FLATTEN: Explode semi-structured data into rows

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/data-types-semistructured
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class SnowflakeVariantSupport(Protocol):
    """Snowflake VARIANT semi-structured data type protocol."""

    def supports_variant_type(self) -> bool:
        """Whether VARIANT type is supported."""
        ...

    def format_variant_path_access(self, column: str, path: str) -> str:
        """Format VARIANT path access expression."""
        ...

    def format_variant_cast(self, column: str, path: str, target_type: str) -> str:
        """Format VARIANT path access with explicit cast."""
        ...