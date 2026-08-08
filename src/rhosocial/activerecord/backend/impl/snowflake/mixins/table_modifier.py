# src/rhosocial/activerecord/backend/impl/snowflake/mixins/table_modifier.py
"""SnowflakeTableModifierMixin — table DDL modifier formatting.

Snowflake table DDL differs from the SQL standard in several ways:
- ``CREATE [OR REPLACE] [TRANSIENT | TEMPORARY] TABLE`` header modifiers.
- ``DATA_RETENTION_TIME_IN_DAYS`` / ``CHANGE_TRACKING`` create options.
- ``CLUSTER BY (...)`` and ``DROP CLUSTERING KEY`` instead of indexes.
- ``ADD SEARCH OPTIMIZATION`` for fast equality/pruning lookups.

These formatters are independently callable; the generic core
``TableMixin`` CREATE TABLE renderer is not modified.
"""

from typing import Iterable, Optional


class SnowflakeTableModifierMixin:
    """Mixin for Snowflake table DDL modifier formatting."""

    def supports_create_or_replace_table(self) -> bool:
        """Snowflake supports CREATE OR REPLACE TABLE."""
        return True

    def supports_transient_table(self) -> bool:
        """Snowflake supports TRANSIENT tables."""
        return True

    def supports_cluster_by(self) -> bool:
        """Snowflake supports CLUSTER BY clustering keys."""
        return True

    def supports_search_optimization(self) -> bool:
        """Snowflake supports SEARCH OPTIMIZATION."""
        return True

    def format_create_table_modifier(
        self,
        *,
        or_replace: bool = False,
        transient: bool = False,
        temporary: bool = False,
    ) -> str:
        """Format CREATE TABLE header modifier tokens.

        Returns a space-joined token string (e.g. ``"OR REPLACE TRANSIENT"``)
        suitable for composing ``CREATE <modifier> TABLE ...``.

        Args:
            or_replace: Emit ``OR REPLACE``.
            transient: Emit ``TRANSIENT``.
            temporary: Emit ``TEMPORARY``.

        Returns:
            The modifier token string, empty when none requested.

        Raises:
            ValueError: when both ``transient`` and ``temporary`` are set.
        """
        if transient and temporary:
            raise ValueError("TRANSIENT and TEMPORARY are mutually exclusive")
        tokens = []
        if or_replace:
            tokens.append("OR REPLACE")
        if transient:
            tokens.append("TRANSIENT")
        if temporary:
            tokens.append("TEMPORARY")
        return " ".join(tokens)

    def format_create_table_options(
        self,
        *,
        data_retention_time_in_days: Optional[int] = None,
        change_tracking: Optional[bool] = None,
        comment: Optional[str] = None,
    ) -> str:
        """Format trailing CREATE TABLE options.

        Returns a space-joined token string suitable for appending after the
        column definition list.

        Args:
            data_retention_time_in_days: ``DATA_RETENTION_TIME_IN_DAYS``.
            change_tracking: ``CHANGE_TRACKING`` bool.
            comment: ``COMMENT`` string literal.

        Returns:
            The options token string, empty when none requested.
        """
        options = []
        if data_retention_time_in_days is not None:
            options.append(
                f"DATA_RETENTION_TIME_IN_DAYS = {int(data_retention_time_in_days)}"
            )
        if change_tracking is not None:
            options.append(
                f"CHANGE_TRACKING = {str(bool(change_tracking)).upper()}"
            )
        if comment is not None:
            options.append(
                f"COMMENT = '{self._escape_sql_string(comment)}'"
            )
        return " ".join(options)

    def format_alter_table_cluster_by(
        self, table: str, columns: Iterable[str]
    ) -> str:
        """Format ALTER TABLE ... CLUSTER BY statement."""
        cols = ", ".join(self.format_identifier(c) for c in columns)
        return (
            f"ALTER TABLE {self.format_identifier(table)} CLUSTER BY ({cols})"
        )

    def format_drop_clustering_key(self, table: str) -> str:
        """Format ALTER TABLE ... DROP CLUSTERING KEY statement."""
        return (
            f"ALTER TABLE {self.format_identifier(table)} "
            "DROP CLUSTERING KEY"
        )

    def format_add_search_optimization(
        self,
        table: str,
        on: Optional[Iterable[str]] = None,
        method: str = "EQUALITY",
    ) -> str:
        """Format ALTER TABLE ... ADD SEARCH OPTIMIZATION statement.

        Args:
            table: Table name.
            on: Optional column list for ``ON <method>(<cols>)``.
            method: Search optimization method (default ``EQUALITY``).

        Returns:
            The formatted ALTER TABLE SQL string.
        """
        parts = [
            f"ALTER TABLE {self.format_identifier(table)} ADD SEARCH OPTIMIZATION"
        ]
        columns = list(on) if on else []
        if columns:
            cols = ", ".join(self.format_identifier(c) for c in columns)
            parts.append(f"ON {method}({cols})")
        return " ".join(parts)
