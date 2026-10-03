# src/rhosocial/activerecord/backend/impl/snowflake/mixins/table.py
"""Snowflake table-reference formatting.

Snowflake is the one dialect here whose table references can be three levels
deep, so it renders ``format_table`` itself rather than taking core's
schema-only version. The database level is declared on
:class:`~...expression.table.SnowflakeTableExpression`; the branch is on that
type, not on attribute presence, so a plain core table reference renders at the
level it was built with.
"""
from __future__ import annotations

from typing import Any, Tuple

from rhosocial.activerecord.backend.dialect.protocols import SchemaSupport
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from ..expression.table import SnowflakeTableExpression


class SnowflakeTableMixin:
    """Rendering for Snowflake's ``database.schema.table`` references."""

    def format_table(self, expr: BaseExpression) -> Tuple[str, tuple]:
        """Render a table reference with as many namespace levels as it carries.

        Args:
            expr: A core or Snowflake table reference.

        Returns:
            Tuple of (SQL string, parameters tuple).

        Raises:
            ValueError: A namespace was given but is not usable.
            UnsupportedFeatureError: This dialect cannot qualify a namespace.
        """
        if isinstance(self, SchemaSupport):
            self.validate_schema_name(expr)

        parts = []
        if isinstance(expr, SnowflakeTableExpression) and expr.database_name:
            parts.append(self.format_identifier(expr.database_name, expr.database_need_quote))
        if isinstance(self, SchemaSupport) and expr.schema_name:
            parts.append(self.format_identifier(expr.schema_name, expr.schema_need_quote))
        parts.append(self.format_identifier(expr.name, expr.name_need_quote))
        table_sql = ".".join(parts)

        params: Tuple[Any, ...] = ()
        if expr.alias:
            table_sql = f"{table_sql} AS {self.format_identifier(expr.alias, expr.alias_need_quote)}"
        if expr.temporal_options:
            from rhosocial.activerecord.backend.expression.datetime import (
                TemporalOptionsExpression,
            )
            temporal = TemporalOptionsExpression(self, expr.temporal_options)
            result = self.format_temporal_options(temporal)
            if result is not None:
                temporal_sql, temporal_params = result
                table_sql = f"{table_sql} {temporal_sql}"
                params += temporal_params
        return table_sql, params


__all__ = ["SnowflakeTableMixin"]
