# src/rhosocial/activerecord/backend/impl/snowflake/collation.py
"""
Snowflake collation specs supported by the dialect whitelist.
"""

from enum import Enum
from typing import Optional, Tuple


class SnowflakeCollation(str, Enum):
    """Common Snowflake collation specs for expression-level COLLATE."""
    #: A member *is* the word it carries: ``str()`` and f-string
    #: interpolation must yield the value, not ``ClassName.MEMBER``, or the
    #: rendered SQL and the artifact would carry the Python spelling.
    #: ``(str, Enum)`` alone does not give that -- ``Enum.__str__`` wins --
    #: so it is stated here once.
    __str__ = str.__str__

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
