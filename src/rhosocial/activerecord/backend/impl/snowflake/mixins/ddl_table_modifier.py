# src/rhosocial/activerecord/backend/impl/snowflake/mixins/ddl_table_modifier.py
"""SnowflakeTableModifierMixin — table DDL modifier support.

Snowflake table DDL differs from the SQL standard in several ways:
- ``CREATE [OR REPLACE] [TRANSIENT | TEMPORARY] TABLE`` header modifiers.
- ``DATA_RETENTION_TIME_IN_DAYS`` / ``CHANGE_TRACKING`` create options.
- ``CLUSTER BY (...)`` and ``DROP CLUSTERING KEY`` instead of indexes.
- ``ADD SEARCH OPTIMIZATION`` for fast equality/pruning lookups.

These formatters are independently callable; the generic core
``TableMixin`` CREATE TABLE renderer is not modified.
"""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ..expression.partition import (
        SnowflakeAlterTableClusteringStatement,
        SnowflakeClusterByClause,
    )


class SnowflakeTableModifierMixin:
    """Mixin for Snowflake table DDL modifier support."""

    def supports_create_or_replace_table(self) -> bool:
        """Snowflake supports CREATE OR REPLACE TABLE."""
        return True

    def supports_if_not_exists_table(self) -> bool:
        """Snowflake accepts ``CREATE TABLE IF NOT EXISTS``.

        The reference grammar is ``CREATE [ OR REPLACE ] [ ... ] TABLE
        [ IF NOT EXISTS ] <name>``. There is no version floor: the clause is
        part of the statement on every server this dialect targets. It is
        declared here rather than left to core's ``CreateTableMixin``, whose
        default answers ``False``.

        ``OR REPLACE`` and ``IF NOT EXISTS`` are mutually exclusive -- the
        reference's usage notes say they "can't both be used in the same
        statement" -- so the formatter refuses the pair by name rather than
        emitting SQL the server rejects.

        https://docs.snowflake.com/en/sql-reference/sql/create-table
        """
        return True

    def format_create_table_statement(self, expr) -> Tuple[str, tuple]:
        """Refuse ``CREATE OR REPLACE TABLE IF NOT EXISTS`` by name.

        Snowflake accepts either header qualifier alone and never both; see
        :meth:`supports_if_not_exists_table`. Only the pairing is checked here,
        so every other CREATE TABLE form keeps the shared rendering.
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )

        options = getattr(expr, "table_options", None)
        if getattr(expr, "if_not_exists", False) and getattr(
            options, "or_replace", False
        ):
            raise UnsupportedFeatureError(
                self.name,
                "CREATE OR REPLACE TABLE IF NOT EXISTS",
                suggestion=(
                    "Snowflake's OR REPLACE and IF NOT EXISTS clauses are "
                    "mutually exclusive; request one of them, not both."
                ),
            )
        return super().format_create_table_statement(expr)

    def format_cluster_by_clause(self, expr: "SnowflakeClusterByClause") -> Tuple[str, tuple]:
        """Format ``CLUSTER BY ( <expr> [, ...] )`` clustering keys.

        Args:
            expr: SnowflakeClusterByClause carrying the clustering key expressions.

        Returns:
            Tuple of (SQL string, parameters tuple).

        Raises:
            ValueError: if no clustering key was collected, or a key is not an
                expression instance.
        """
        from rhosocial.activerecord.backend.expression.bases import BaseExpression

        if not expr.keys:
            raise ValueError("CLUSTER BY requires at least one clustering key")
        parts = []
        params = []
        for key in expr.keys:
            if not isinstance(key, BaseExpression):
                raise TypeError(
                    "clustering keys must be BaseExpression instances, "
                    f"got {type(key).__name__}"
                )
            key_sql, key_params = key.to_sql()
            parts.append(key_sql)
            params.extend(key_params)
        return f" CLUSTER BY ({', '.join(parts)})", tuple(params)

    def format_alter_table_clustering_statement(
        self, expr: "SnowflakeAlterTableClusteringStatement"
    ) -> Tuple[str, tuple]:
        """Format ``ALTER TABLE ... CLUSTER BY (...)`` / ``DROP CLUSTERING KEY``.

        Args:
            expr: the statement carrying the table and an optional
                ``SnowflakeClusterByClause``.

        Returns:
            Tuple of (SQL string, parameters tuple).
        """
        table_sql, table_params = expr.table.to_sql()
        params = list(table_params)
        if expr.cluster_by is None:
            return f"ALTER TABLE {table_sql} DROP CLUSTERING KEY", tuple(params)
        clause_sql, clause_params = expr.cluster_by.to_sql()
        params.extend(clause_params)
        return f"ALTER TABLE {table_sql}{clause_sql}", tuple(params)

    def supports_transient_table(self) -> bool:
        """Snowflake supports TRANSIENT tables."""
        return True

    def supports_cluster_by(self) -> bool:
        """Snowflake supports CLUSTER BY clustering keys."""
        return True

    def format_create_table_options(self, expr) -> Tuple[str, tuple]:
        """Format the CREATE header modifiers for Snowflake.

        Accepts both the generic ``CreateTableOptions`` (renders ``OR REPLACE``)
        and the Snowflake ``SnowflakeCreateTableOptions`` (adds ``TRANSIENT``).
        """
        from rhosocial.activerecord.backend.dialect.exceptions import (
            UnsupportedFeatureError,
        )
        from ..expression.table_options import SnowflakeCreateTableOptions

        base_sql, params = super().format_create_table_options(expr)
        parts = [base_sql] if base_sql else []
        if isinstance(expr, SnowflakeCreateTableOptions) and expr.transient:
            if not self.supports_transient_table():
                raise UnsupportedFeatureError(self.name, "CREATE TRANSIENT TABLE")
            parts.append("TRANSIENT")
        return " ".join(parts), params

    def supports_search_optimization(self) -> bool:
        """Snowflake supports SEARCH OPTIMIZATION."""
        return True

    def supports_table_comment(self) -> bool:
        """Whether inline comments on ``CREATE TABLE`` are supported.

        Snowflake natively supports both the inline ``COMMENT = 'text'`` table
        option and the standalone ``COMMENT ON`` statement; the inline path is
        the rendering path, so the capability advertises True.
        """
        return True

    def supports_comment_on(self) -> bool:
        """Whether standalone ``COMMENT ON`` statements are supported.

        Snowflake natively supports ``COMMENT [IF EXISTS] ON <object> IS
        'text'`` for tables, columns, views, and other objects; the generic
        :class:`CommentMixin` rendering is used as-is.
        """
        return True

    def format_table_comment(self, expr: str) -> Tuple[str, tuple]:
        """Render a table-level ``COMMENT = 'text'`` option.

        Snowflake's table-level comment form carries the ``=`` sign (unlike
        the bare ``COMMENT 'text'`` of MySQL/MariaDB/ClickHouse, which the
        generic core rendering emits); the column-level form stays bare and
        is rendered by the generic ``format_column_definition``.
        """
        escaped = self.escape_sql_string(expr)
        return f"COMMENT = '{escaped}'", ()

    def supports_create_table_like(self) -> bool:
        """Snowflake supports CREATE TABLE ... LIKE (empty copy)."""
        return True

    def supports_create_table_clone(self) -> bool:
        """Snowflake supports CREATE TABLE ... CLONE (zero-copy copy)."""
        return True

    def supports_create_table_using_template(self) -> bool:
        """Snowflake supports CREATE TABLE ... USING TEMPLATE."""
        return True
