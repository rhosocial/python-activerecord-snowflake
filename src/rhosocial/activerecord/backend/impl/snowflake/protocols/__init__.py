# src/rhosocial/activerecord/backend/impl/snowflake/protocols/__init__.py
"""Snowflake backend-specific protocol definitions.

This package defines protocols for features exclusive to Snowflake,
which are not part of the SQL standard and not supported by other
mainstream databases.
"""

from .time_travel import SnowflakeTimeTravelSupport
from .variant import SnowflakeVariantSupport
from .array import SnowflakeArraySupport
from .clone import SnowflakeCloneSupport
from .stage import SnowflakeStageSupport

__all__ = [
    "SnowflakeTimeTravelSupport",
    "SnowflakeVariantSupport",
    "SnowflakeArraySupport",
    "SnowflakeCloneSupport",
    "SnowflakeStageSupport",
]