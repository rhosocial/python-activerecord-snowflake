# src/rhosocial/activerecord/backend/impl/snowflake/schema/differ.py
"""Snowflake schema differ — type-name-based column comparison."""

from rhosocial.activerecord.backend.schema.differ import SchemaDiffer


class SnowflakeSchemaDiffer(SchemaDiffer):
    """Snowflake schema differ.

    Snowflake uses VARCHAR/NUMBER type names and supports ALTER TABLE
    ADD COLUMN which always appends. Ordinal position comparison is
    not required.
    """

    def _columns_equivalent(self, old_col, new_col) -> bool:
        return old_col.data_type == new_col.data_type