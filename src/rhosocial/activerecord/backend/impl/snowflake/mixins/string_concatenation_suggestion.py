# src/rhosocial/activerecord/backend/impl/snowflake/mixins/string_concatenation_suggestion.py
"""Snowflake's string-concatenation spelling suggestion.

Core's ``format_concatenation_operation`` asks the dialect how it spells
concatenation through ``suggest_concatenation_function()``. Snowflake uses
the standard ``||`` operator, so the answer is a suggestion whose function
name is ``None``.
"""
from rhosocial.activerecord.backend.suggestion.definitions import (
    ConcatenationFunctionSuggestion,
)
from rhosocial.activerecord.backend.suggestion.protocols import (
    StringConcatenationSuggestionSupport,
)


class SnowflakeStringConcatenationSuggestionMixin(StringConcatenationSuggestionSupport):
    """Snowflake concatenates strings with ``||`` (no function form)."""

    def suggest_concatenation_function(self) -> ConcatenationFunctionSuggestion:
        return ConcatenationFunctionSuggestion(function=None)


__all__ = ["SnowflakeStringConcatenationSuggestionMixin"]
