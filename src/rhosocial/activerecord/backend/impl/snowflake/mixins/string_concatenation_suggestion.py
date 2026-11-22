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


class SnowflakeStringConcatenationSuggestionMixin:
    """Snowflake concatenates strings with ``||`` (no function form).

    Deliberately a plain class rather than a subclass of the runtime-checkable
    protocol: a protocol subclass placed ahead of ``SQLDialectBase`` can
    intercept ``super().__init__()`` and lose the dialect's version and
    validation state. The dialect still satisfies the protocol structurally,
    by declaring ``StringConcatenationSuggestionSupport`` among its bases.
    """

    def suggest_concatenation_function(self) -> ConcatenationFunctionSuggestion:
        return ConcatenationFunctionSuggestion(function=None)


__all__ = ["SnowflakeStringConcatenationSuggestionMixin"]
