# src/rhosocial/activerecord/backend/impl/snowflake/mixins/json.py
"""Snowflake JSON/VARIANT expression support mixin.

Snowflake does not have a native JSON type; it uses VARIANT for
semi-structured data.  JSON arrow operators (->, ->>) are not supported.
Instead, Snowflake uses colon notation (:) for VARIANT path access.

- `column:path` returns the value as VARIANT
- `column:path::type` returns the value cast to a specific type
- `column:path::VARCHAR` is equivalent to the SQL standard ->> operator
"""
from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.advanced_functions import JSONExpression


class SnowflakeJSONMixin:
    """Mixin for Snowflake JSON/VARIANT expression support.

    Provides correct formatting for JSON path expressions on Snowflake's
    VARIANT type using colon notation instead of the ->/->> operators
    used by PostgreSQL/MySQL/MariaDB.
    """

    def format_json_function_expression(self, expr: "JSONExpression") -> Tuple[str, Tuple]:
        """Format JSON expression for Snowflake using VARIANT colon notation.

        Snowflake uses `:path` for accessing VARIANT fields and
        `::type` for casting.  The JSONPath prefix `$.` is stripped
        because Snowflake uses simple dot notation.
        """
        if isinstance(expr.column, bases.BaseExpression):
            col_sql, col_params = expr.column.to_sql()
        else:
            col_sql, col_params = self.format_identifier(str(expr.column)), ()

        path = expr.path
        if path.startswith("$."):
            path = path[2:]
        elif path.startswith("$"):
            path = path[1:]

        sql = f"{col_sql}:{path}"
        params = col_params

        if expr.operation == "->>":
            sql, params = self.format_cast_expression(sql, "VARCHAR", params, None)

        if expr.cast_types:
            for target_type in expr.cast_types:
                sql, params = self.format_cast_expression(sql, target_type, params, None)

        if expr.alias:
            sql = f"{sql} AS {self.format_identifier(expr.alias)}"

        return sql, params
