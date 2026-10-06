# src/rhosocial/activerecord/backend/impl/snowflake/mixins/ilike.py
"""Snowflake ILIKE support mixin."""
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.predicates import ILIKEExpression


class SnowflakeILIKEMixin:
    """Snowflake native ILIKE operator support."""

    def supports_ilike(self) -> bool:
        """Snowflake supports the native ILIKE operator."""
        return True

    def format_ilike_expression(
        self, expr: "ILIKEExpression"
    ) -> Tuple[str, tuple]:
        """Format a native Snowflake [NOT] ILIKE expression.

        Takes the node and reads ``column``, ``pattern`` and ``negate`` off it,
        which is the shape ``ILIKESupport`` declares and the shape
        ``ILIKEExpression.to_sql()`` dispatches: the node carries its own data,
        so the formatter is called with the node alone.

        The three-argument form ``(column, pattern, negate)`` this used to have
        cannot be reached by dispatch at all -- ``to_sql()`` passes one argument
        -- so it raised ``TypeError: format_ilike_expression() missing 1
        required positional argument: 'pattern'`` on every ILIKE, and Snowflake
        ILIKE was unreachable. Nothing caught it: the conformance tests check
        that a method of the right *name* exists, not that it can be called the
        way the protocol calls it, and no test rendered an ``ILIKEExpression``.
        The round-trip matrix found it by constructing one and rendering it.

        The pattern is passed through unchanged, not lowercased as the shared
        ``LOWER(...) LIKE LOWER(...)`` default does. Case-insensitivity is the
        operator's job here, so folding the pattern would change what matches.
        """
        column = expr.column
        if isinstance(column, str):
            col_sql = self.format_identifier(column)
            column_params: tuple = ()
        else:
            col_sql, column_params = column.to_sql()
        operator = "NOT ILIKE" if expr.negate else "ILIKE"
        return f"{col_sql} {operator} {self.p()}", column_params + (expr.pattern,)


__all__ = ["SnowflakeILIKEMixin"]