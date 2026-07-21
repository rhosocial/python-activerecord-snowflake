# src/rhosocial/activerecord/backend/impl/snowflake/schema/differ.py
"""Snowflake schema differ — type-name-based column comparison.

Snowflake uses VARCHAR/NUMBER type names and supports ALTER TABLE
ADD COLUMN which always appends. Ordinal position comparison is
not required.
"""

from rhosocial.activerecord.backend.schema.differ import SchemaDiffer


class SnowflakeSchemaDiffer(SchemaDiffer):
    """Snowflake schema differ.

    Delegates core checks (nullable, default value) to the base
    implementation. Snowflake always appends columns, so ordinal
    position comparison is skipped.
    """

    def _columns_equivalent(self, old_col, new_col) -> bool:
        if not super()._columns_equivalent(old_col, new_col):
            return False
        return True
