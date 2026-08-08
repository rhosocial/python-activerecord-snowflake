# src/rhosocial/activerecord/backend/impl/snowflake/mixins/dynamic_identifier.py
"""SnowflakeDynamicIdentifierMixin — IDENTIFIER() binding support."""


class SnowflakeDynamicIdentifierMixin:
    """Mixin for Snowflake dynamic identifier (IDENTIFIER()) support.

    Object names supplied at runtime must be wrapped in ``IDENTIFIER()``
    so Snowflake treats the bound parameter value as an identifier instead
    of a string literal. The placeholder is produced by the dialect and the
    actual value is bound as a parameter, preventing SQL injection.
    """

    def supports_dynamic_identifier(self) -> bool:
        """Snowflake supports IDENTIFIER() dynamic binding."""
        return True

    def format_identifier_dynamic(self, identifier: str) -> str:
        """Format an ``IDENTIFIER(placeholder)`` dynamic object reference.

        Args:
            identifier: The object name to bind dynamically (used only for
                the parameter value by the caller).

        Returns:
            The ``IDENTIFIER(?)`` SQL fragment using the dialect placeholder.

        """
        placeholder = self.get_parameter_placeholder()
        return f"IDENTIFIER({placeholder})"
