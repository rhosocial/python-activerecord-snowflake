# src/rhosocial/activerecord/backend/impl/snowflake/mixins/generated_value_suggestion.py
"""SnowflakeGeneratedValueSuggestionMixin -- snowflake's generated-value suggestion.

The answer is the backend's own spelling, assembled from its capability
probes where it has one. It is placed first in the dialect bases so no core
mixin can shadow it, and it renders nothing itself -- the returned clause's
formatter owns the SQL spelling.
"""

from typing import TYPE_CHECKING

from ....expression.statements import IdentityClause
from ....suggestion import GeneratedValueSuggestion

if TYPE_CHECKING:  # pragma: no cover
    from ....expression.types import DataType


class SnowflakeGeneratedValueSuggestionMixin:
    """Suggest snowflake's declaration for a generated integer key.

    Deliberately a plain class, like the other Snowflake suggestion mixins: the
    dialect satisfies ``GeneratedValueSuggestionSupport`` structurally, so no
    protocol subclass intercepts ``super().__init__()`` and leaves the dialect's
    ``strict_validation`` unset.
    """

    def suggest_generated_value(self, default_type: "DataType") -> GeneratedValueSuggestion:
        return GeneratedValueSuggestion(
            state="generate",
            storage_type=default_type,
            clause=IdentityClause(self),
        )


__all__ = ["SnowflakeGeneratedValueSuggestionMixin"]
