# src/rhosocial/activerecord/backend/impl/snowflake/expression/identifier.py
"""Snowflake IDENTIFIER() dynamic identifier expression.

Snowflake binds object names at compile time, so dynamically-supplied
object names (e.g. from a parameter) must be wrapped in the ``IDENTIFIER()``
function: ``IDENTIFIER(:name)`` / ``IDENTIFIER(?)``. The object name is
bound as a parameter value, avoiding SQL injection through identifier
concatenation.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- IDENTIFIER: https://docs.snowflake.com/en/sql-reference/identifier-literal
"""
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeIdentifierExpression",
]


class SnowflakeIdentifierExpression(BaseExpression):
    """Snowflake dynamic identifier reference expression.

    Attributes:
        identifier: Object name to bind dynamically.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        identifier: str,
    ):
        super().__init__(dialect)
        self.identifier = identifier

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate an ``IDENTIFIER(placeholder)`` reference.

        The identifier value is returned as a parameter to be bound at
        execution time.

        Returns:
            Tuple of (SQL string, identifier parameter tuple).

        """
        sql = self.dialect.format_identifier_dynamic(self.identifier)
        return sql, (self.identifier,)
