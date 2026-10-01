# src/rhosocial/activerecord/backend/impl/snowflake/functions/schema.py
"""
Snowflake schema resolution functions.

Provides a SQL expression factory for asking the server which namespace an
unqualified reference resolves against.

Follows the expression-dialect separation architecture:
- First parameter is always the dialect instance
- Returns an Expression object (FunctionCall)
- Does not concatenate SQL strings directly
"""

from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.expression import core

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


def current_schema(dialect: "SQLDialectBase") -> "core.FunctionCall":
    """Create a function call for the current schema.

    Returns the active schema, the first existing entry in the schema search
    path. NULL when the search path resolves to no existing schema.

    Usage:
        - current_schema(dialect)

    Args:
        dialect: The SQL dialect instance

    Returns:
        A FunctionCall instance that evaluates to the current schema name
    """
    return core.FunctionCall(dialect, "CURRENT_SCHEMA")
