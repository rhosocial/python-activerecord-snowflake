# src/rhosocial/activerecord/backend/impl/snowflake/mixins/ddl/alter_table_modifier.py
"""Snowflake ALTER TABLE column IF [NOT] EXISTS qualifier formatting."""

from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import ColumnConstraintType


class SnowflakeAlterColumnModifierMixin:
    """Snowflake column qualifiers for ALTER TABLE actions.

    Snowflake supports ``ADD COLUMN IF NOT EXISTS`` and
    ``DROP COLUMN IF EXISTS``, but **not** ``DROP CONSTRAINT IF EXISTS``.

    Restriction: ``ADD COLUMN IF NOT EXISTS`` cannot be combined with
    DEFAULT/AUTOINCREMENT/IDENTITY/UNIQUE/PRIMARY KEY/FOREIGN KEY on the
    same column (per Snowflake documentation). When ``if_not_exists`` is
    requested together with one of those constraints,
    ``UnsupportedFeatureError`` is raised.
    """

    def supports_add_column_if_not_exists(self) -> bool:
        """Snowflake supports ``ADD COLUMN IF NOT EXISTS``."""
        return True

    def supports_drop_column_if_exists(self) -> bool:
        """Snowflake supports ``DROP COLUMN IF EXISTS``."""
        return True

    def supports_drop_constraint_if_exists(self) -> bool:
        """Snowflake does **not** support ``DROP CONSTRAINT IF EXISTS``."""
        return False

    def format_add_column_action(self, action) -> Tuple[str, tuple]:
        if getattr(action, "if_not_exists", None) is True:
            forbidden = {
                ColumnConstraintType.DEFAULT,
                ColumnConstraintType.PRIMARY_KEY,
                ColumnConstraintType.FOREIGN_KEY,
                ColumnConstraintType.UNIQUE,
            }
            if any(c.constraint_type in forbidden for c in action.column.constraints):
                raise UnsupportedFeatureError(
                    self.name,
                    "ADD COLUMN IF NOT EXISTS with DEFAULT/IDENTITY/PK/FK/UNIQUE",
                    suggestion="Snowflake does not allow IF NOT EXISTS when the column "
                               "also specifies DEFAULT/AUTOINCREMENT/IDENTITY/UNIQUE/PK/FK. "
                               "Pre-check information_schema.COLUMNS instead.",
                )
            column_sql, column_params = self.format_column_definition(action.column)
            return f"ADD COLUMN IF NOT EXISTS {column_sql}", column_params
        column_sql, column_params = self.format_column_definition(action.column)
        return f"ADD COLUMN {column_sql}", column_params

    def format_drop_column_action(self, action) -> Tuple[str, tuple]:
        name = self.format_identifier(action.column_name)
        if getattr(action, "if_exists", None) is True:
            return f"DROP COLUMN IF EXISTS {name}", ()
        return f"DROP COLUMN {name}", ()

    def format_drop_table_constraint_action(self, action) -> Tuple[str, tuple]:
        if getattr(action, "if_exists", None) is True:
            raise UnsupportedFeatureError(
                self.name,
                "DROP CONSTRAINT IF EXISTS",
                suggestion="Snowflake does not support IF EXISTS on DROP CONSTRAINT. "
                           "Pre-check information_schema.TABLE_CONSTRAINTS.",
            )
        name = self.format_identifier(action.constraint_name)
        result = f"DROP CONSTRAINT {name}"
        if getattr(action, "cascade", None):
            result += " CASCADE"
        return result, ()