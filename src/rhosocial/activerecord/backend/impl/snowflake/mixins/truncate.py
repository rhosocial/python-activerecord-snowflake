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

    Snowflake's TRUNCATE has neither an identity clause (``RESTART`` /
    ``CONTINUE IDENTITY``) nor a dependency behaviour (``CASCADE`` /
    ``RESTRICT``): the reference grammar is
    ``TRUNCATE [ TABLE ] [ IF EXISTS ] <name>``. Each spelling of each pair is
    refused by name rather than silently dropped.
    https://docs.snowflake.com/en/sql-reference/sql/truncate-table
    """

    def supports_truncate(self) -> bool:
        """Snowflake renders ``TRUNCATE [ TABLE ] [ IF EXISTS ] <name>``.

        The statement itself is in the reference synopsis; the options are
        what this dialect declines (see the refusals below).
        https://docs.snowflake.com/en/sql-reference/sql/truncate-table
        """
        return True

    def format_truncate_statement(self, expr: "TruncateExpression") -> Tuple[str, tuple]:
        """Format Snowflake TRUNCATE TABLE <name>.

        Raises:
            TypeError: ``expr.table`` is not a Table. Any other object kind would
                have rendered its own name after TRUNCATE, which reads as valid
                SQL and silently deletes from -- or names -- the wrong thing.
            UnsupportedFeatureError: If TRUNCATE itself is declined (the probe
                answers ``True``; the guard is the fail-closed shape every
                formatter carries), or Snowflake TRUNCATE has no identity clause
                (``RESTART`` or ``CONTINUE IDENTITY``) and no dependency
                behaviour (``CASCADE`` or ``RESTRICT``). Every requested
                spelling raises, naming itself, so a parameter added to the
                expression can never be dropped silently.
        """
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"{type(expr).__name__}.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        if not self.supports_truncate():
            raise UnsupportedFeatureError(
                self.name,
                "TRUNCATE",
                suggestion=(
                    "This dialect does not render TRUNCATE; Snowflake's "
                    "grammar is TRUNCATE [ TABLE ] [ IF EXISTS ] <name>."
                ),
            )
        if expr.restart_identity or expr.continue_identity:
            feature = (
                "TRUNCATE ... RESTART IDENTITY"
                if expr.restart_identity
                else "TRUNCATE ... CONTINUE IDENTITY"
            )
            raise UnsupportedFeatureError(
                self.name,
                feature,
                suggestion=(
                    "Snowflake TRUNCATE has no RESTART IDENTITY / "
                    "CONTINUE IDENTITY option."
                ),
            )
        if expr.cascade or expr.restrict:
            feature = (
                "TRUNCATE ... CASCADE" if expr.cascade else "TRUNCATE ... RESTRICT"
            )
            raise UnsupportedFeatureError(
                self.name,
                feature,
                suggestion="Snowflake TRUNCATE has no CASCADE / RESTRICT option.",
            )
        return f"TRUNCATE TABLE {expr.table.to_sql()[0]}", ()


__all__ = ['SnowflakeTruncateMixin']
