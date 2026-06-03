# src/rhosocial/activerecord/backend/impl/snowflake/collation.py
"""
Snowflake collation specs supported by the dialect whitelist.
"""

from enum import Enum
from typing import Optional, Tuple


class SnowflakeCollation(Enum):
    """Common Snowflake collation specs for expression-level COLLATE."""

    EN = "en"
    EN_CI = "en-ci"
    EN_CS = "en-cs"
    EN_CI_AI = "en-ci-ai"
    UPPER = "upper"
    LOWER = "lower"
    TRIM = "trim"


_SNOWFLAKE_COLLATIONS = {collation.value for collation in SnowflakeCollation}


def validate_snowflake_collation_name(
    name: str,
    version: Optional[Tuple[int, ...]] = None,
) -> str:
    normalized = name.lower()
    if normalized not in _SNOWFLAKE_COLLATIONS:
        raise ValueError(f"Unsupported Snowflake collation: {name!r}")
    return normalized
