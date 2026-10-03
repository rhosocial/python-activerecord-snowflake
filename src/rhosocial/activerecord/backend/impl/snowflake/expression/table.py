# src/rhosocial/activerecord/backend/impl/snowflake/expression/table.py
"""Snowflake three-level table reference.

Snowflake namespaces a table as ``database.schema.table``, which is one level
deeper than the schema qualification core's
:class:`~rhosocial.activerecord.backend.expression.core.TableExpression`
carries. The extra level is declared here as a real field rather than
concatenated into the name at the call site, so the formatter renders it and a
caller cannot build ``"RAW.STAGING.t"`` by hand and lose the quoting each part
needs.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- Fully qualified names: https://docs.snowflake.com/en/sql-reference/identifiers-syntax
"""
from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.core import TableExpression

if TYPE_CHECKING:  # pragma: no cover
    from ..dialect import SnowflakeDialect


class SnowflakeTableExpression(TableExpression):
    """A table reference that may also carry a database level.

    Attributes:
        database_name: The database the schema lives in, or None to leave the
            reference at one or two levels.
    """

    def __init__(
        self,
        dialect: "SnowflakeDialect",
        name: str,
        schema_name: Optional[str] = None,
        alias: Optional[str] = None,
        temporal_options: Optional[Dict[str, Any]] = None,
        name_need_quote: bool = True,
        alias_need_quote: bool = True,
        schema_need_quote: bool = True,
        database_name: Optional[str] = None,
        database_need_quote: bool = True,
    ):
        """
        Args:
            database_name: Database to qualify above the schema, e.g. ``RAW``.
                None leaves the name at the schema level. An empty string
                raises ValueError, and a dialect with no namespaces raises
                UnsupportedFeatureError.
        """
        super().__init__(
            dialect,
            name,
            schema_name=schema_name,
            alias=alias,
            temporal_options=temporal_options,
            name_need_quote=name_need_quote,
            alias_need_quote=alias_need_quote,
            schema_need_quote=schema_need_quote,
        )
        self.database_name = database_name
        self.database_need_quote = database_need_quote


__all__ = [
    "SnowflakeTableExpression",
]
