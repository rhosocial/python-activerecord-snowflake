# src/rhosocial/activerecord/backend/impl/snowflake/mixins/dml.py
"""SnowflakeDMLMixin — Snowflake DML statement support (INSERT OVERWRITE)."""

from typing import Tuple, TYPE_CHECKING

from ..expression.dml import SnowflakeInsertExpression

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        InsertStatement,
    )


class SnowflakeDMLMixin:
    """Mixin for Snowflake DML statement support.

    Adds ``INSERT OVERWRITE`` on top of the core ``DMLMixin``. The Snowflake
    ``SnowflakeInsertExpression`` carries the ``overwrite`` flag as a typed
    field so no core changes are required.
    """

    def supports_insert_overwrite(self) -> bool:
        """Snowflake supports the INSERT OVERWRITE statement."""
        return True

    def format_insert_statement(
        self, expr: "InsertStatement"
    ) -> Tuple[str, tuple]:
        """Format an INSERT statement, honouring the ``overwrite`` option.

        When the statement is a :class:`SnowflakeInsertExpression` whose
        ``overwrite`` field is truthy it is rendered as
        ``INSERT OVERWRITE INTO ...``; any other INSERT keeps the core
        rendering. The flag belongs to the Snowflake expression alone -- the
        core ``InsertStatement`` declares no such field -- so the subclass is
        asked by name rather than probed for the attribute.

        Args:
            expr: :class:`InsertStatement`.

        Returns:
            Tuple of (SQL string, params tuple).

        """
        if isinstance(expr, SnowflakeInsertExpression) and expr.overwrite:
            return self.format_insert_overwrite_statement(expr)
        return super().format_insert_statement(expr)

    def format_insert_overwrite_statement(
        self, expr: "InsertStatement"
    ) -> Tuple[str, tuple]:
        """Format an INSERT OVERWRITE INTO statement.

        Snowflake's ``INSERT OVERWRITE`` truncates the target table inside the
        same transaction (avoiding the implicit commit of a separate TRUNCATE).

        Args:
            expr: :class:`InsertStatement`.

        Returns:
            Tuple of (SQL string, params tuple).

        Raises:
            ValueError: when the underlying statement is not a plain
                ``INSERT INTO`` form.
        """
        sql, params = super().format_insert_statement(expr)
        if not sql.startswith("INSERT INTO"):
            raise ValueError(
                "INSERT OVERWRITE requires a plain INSERT INTO statement"
            )
        sql = "INSERT OVERWRITE" + sql[len("INSERT"):]
        return sql, params
