# src/rhosocial/activerecord/backend/impl/snowflake/mixins/table_index_change_suggestion.py
"""Snowflake's table-index-change change suggestion.

Snowflake has no plain ``CREATE INDEX`` / ``DROP INDEX`` for ordinary tables.
Its only index DDL belongs to hybrid tables::

    CREATE [ OR REPLACE ] INDEX [ IF NOT EXISTS ] <name> ON <table> ( <cols> )
    DROP INDEX [ IF EXISTS ] <table>.<index_name>

Hybrid tables are a different table kind that this backend does not model.
Every index probe answers ``False`` (``supports_create_index``,
``supports_drop_index``, ``supports_indexes``, ``supports_alter_table_index_actions``,
...), the plain index statements and ALTER TABLE index actions refuse by name,
and no hybrid-table node or formatter exists to reuse. A frozen old -> new
index declaration therefore has no existing node that can perform it, so the
explicit ``False`` state is returned.

Evidence: https://docs.snowflake.com/en/sql-reference/sql/create-index,
https://docs.snowflake.com/en/sql-reference/sql/drop-index and
https://docs.snowflake.com/en/sql-reference/sql/create-hybrid-table
(fetched 2026-11-25); pinned by
``tests/.../feature/backend/ddl/test_snowflake_index_capabilities.py``.
"""
from dataclasses import replace

from rhosocial.activerecord.backend.suggestion.definitions import (
    TableIndexChangeSuggestion,
)


class SnowflakeTableIndexChangeSuggestionMixin:
    """Answer the table-index-change decision point as unsupported."""

    def suggest_table_index_change(
        self, point: TableIndexChangeSuggestion
    ) -> TableIndexChangeSuggestion:
        """Return ``point`` with ``operations=False`` (unaddressable)."""
        return replace(point, operations=False)


__all__ = ["SnowflakeTableIndexChangeSuggestionMixin"]
