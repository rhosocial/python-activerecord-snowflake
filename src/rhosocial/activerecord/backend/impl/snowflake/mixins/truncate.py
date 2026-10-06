# src/rhosocial/activerecord/backend/impl/snowflake/mixins/truncate.py
"""Snowflake TRUNCATE support mixin."""
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Table

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
        """Format Snowflake TRUNCATE TABLE <name>.

        Raises:
            TypeError: ``expr.table`` is not a Table. Any other object kind would
                have rendered its own name after TRUNCATE, which reads as valid
                SQL and silently deletes from -- or names -- the wrong thing.
            UnsupportedFeatureError: Snowflake TRUNCATE has neither RESTART
                IDENTITY nor CASCADE.
        """
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"{type(expr).__name__}.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
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
        return f"TRUNCATE TABLE {expr.table.to_sql()[0]}", ()


__all__ = ['SnowflakeTruncateMixin']
