# src/rhosocial/activerecord/backend/impl/snowflake/mixins/dml.py
"""SnowflakeDMLMixin — Snowflake DML statement support (INSERT OVERWRITE)."""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        InsertExpression,
    )


class SnowflakeDMLMixin:
    """Mixin for Snowflake DML statement support.

    Adds ``INSERT OVERWRITE`` on top of the core ``DMLMixin``. The core
    ``InsertExpression`` carries the ``overwrite`` flag through its
    ``dialect_options`` so no core changes are required.
    """

    def supports_insert_overwrite(self) -> bool:
        """Snowflake supports the INSERT OVERWRITE statement."""
        return True

    def format_insert_statement(
        self, expr: "InsertExpression"
    ) -> Tuple[str, tuple]:
        """Format an INSERT statement, honouring the ``overwrite`` option.

        When ``expr.dialect_options["overwrite"]`` is truthy the statement is
        rendered as ``INSERT OVERWRITE INTO ...``.

        Args:
            expr: :class:`InsertExpression`.

        Returns:
            Tuple of (SQL string, params tuple).

        """
        if expr.dialect_options.get("overwrite"):
            return self.format_insert_overwrite_statement(expr)
        return super().format_insert_statement(expr)

    def format_insert_overwrite_statement(
        self, expr: "InsertExpression"
    ) -> Tuple[str, tuple]:
        """Format an INSERT OVERWRITE INTO statement.

        Snowflake's ``INSERT OVERWRITE`` truncates the target table inside the
        same transaction (avoiding the implicit commit of a separate TRUNCATE).

        Args:
            expr: :class:`InsertExpression`.

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
