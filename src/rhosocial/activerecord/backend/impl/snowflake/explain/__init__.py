# src/rhosocial/activerecord/backend/impl/snowflake/explain/__init__.py
"""Snowflake EXPLAIN result types."""

from .types import SnowflakeExplainRow, SnowflakeExplainResult

__all__ = ["SnowflakeExplainRow", "SnowflakeExplainResult"]