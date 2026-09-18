# src/rhosocial/activerecord/backend/impl/snowflake/mixins/truncate.py
"""Snowflake TRUNCATE support mixin."""
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_truncate import (
        TruncateExpression,
    )


class SnowflakeTruncateMixin:
    """Snowflake TRUNCATE TABLE support.

    Snowflake's TRUNCATE has neither a RESTART IDENTITY nor a
    CASCADE option.
    """

    def format_truncate_statement(self, expr: "TruncateExpression") -> Tuple[str, tuple]:
        """Format Snowflake TRUNCATE TABLE <name>."""
        if expr.restart_identity:
            raise UnsupportedFeatureError(
                self.name,
                "TRUNCATE ... RESTART IDENTITY",
                suggestion="Snowflake TRUNCATE has no RESTART IDENTITY option.",
            )
        if expr.cascade:
            raise UnsupportedFeatureError(
                self.name,
                "TRUNCATE ... CASCADE",
                suggestion="Snowflake TRUNCATE has no CASCADE option.",
            )
        return f"TRUNCATE TABLE {self.format_identifier(expr.table_name)}", ()


__all__ = ['SnowflakeTruncateMixin']
