# src/rhosocial/activerecord/backend/impl/snowflake/protocols/clone.py
"""Snowflake CLONE protocol.

Feature Source: Snowflake native (not SQL standard)

Snowflake supports cloning databases, schemas, and tables:
- CREATE TABLE ... CLONE source_table
- CREATE SCHEMA ... CLONE source_schema
- CREATE DATABASE ... CLONE source_database

Clones are zero-copy operations that share storage with the source.

Official Documentation:
- https://docs.snowflake.com/en/sql-reference/sql/create-clone
"""
from typing import Protocol, Tuple, runtime_checkable


@runtime_checkable
class SnowflakeCloneSupport(Protocol):
    """Snowflake CLONE protocol."""

    def supports_clone(self) -> bool:
        """Whether CLONE operations are supported."""
        ...

    def format_clone_table(self, target: str, source: str) -> Tuple[str, tuple]:
        """Format CREATE TABLE ... CLONE statement."""
        ...

    def format_clone_schema(self, target: str, source: str) -> Tuple[str, tuple]:
        """Format CREATE SCHEMA ... CLONE statement."""
        ...

    def format_clone_database(self, target: str, source: str) -> Tuple[str, tuple]:
        """Format CREATE DATABASE ... CLONE statement."""
        ...