# src/rhosocial/activerecord/backend/impl/snowflake/mixins/create_table_layout_suggestion.py
"""Snowflake's CREATE TABLE layout suggestion.

Snowflake renders a table comment inline in ``CREATE TABLE`` (``COMMENT =
'text'``) but has no inline index definitions -- indexes are standalone
``CREATE INDEX`` statements. A single statement therefore cannot carry both
optional clauses, so the layout is ``"split"`` with ``inline_index=False`` and
``inline_comment=True``. The answer is assembled from the dialect's own
capability probes rather than hardcoded, so it stays honest if a probe changes.
"""

from rhosocial.activerecord.backend.suggestion.definitions import (
    CreateTableLayoutSuggestion,
)


class SnowflakeCreateTableLayoutSuggestionMixin:
    """Assemble Snowflake's CREATE TABLE layout from its capability probes.

    Deliberately a plain class, like the other Snowflake suggestion mixins: the
    dialect declares ``CreateTableLayoutSuggestionSupport`` among its bases so
    the protocol's ``isinstance`` check succeeds without a protocol subclass
    intercepting ``super().__init__()``.
    """

    def suggest_create_table_layout(self) -> CreateTableLayoutSuggestion:
        inline_index = self.supports_inline_index()
        inline_comment = self.supports_table_comment()
        return CreateTableLayoutSuggestion(
            strategy="single" if inline_index and inline_comment else "split",
            inline_index=inline_index,
            inline_comment=inline_comment,
            state="actions",
        )


__all__ = ["SnowflakeCreateTableLayoutSuggestionMixin"]
