# src/rhosocial/activerecord/backend/impl/snowflake/mixins/index.py
"""Snowflake index DDL capability.

Snowflake has **no plain ``CREATE INDEX`` / ``DROP INDEX`` statement for
ordinary tables**. Its only index DDL belongs to a different table kind:

* ``CREATE [ OR REPLACE ] INDEX [ IF NOT EXISTS ] <index_name>
  ON <table_name> ( <col_name> [ , ... ] )
  [ INCLUDE ( <col_name> [ , ... ] ) ]``
* ``DROP INDEX [ IF EXISTS ] <table_name>.<index_name>``

Both create and drop a *secondary index* on a **hybrid table** and nothing
else: the reference says the statement "creates a new secondary index in an
existing hybrid table", and ``table_name`` names "an existing hybrid table".
An ordinary Snowflake table has no index DDL at all; data layout is controlled
by ``CLUSTER BY`` clustering keys (a separate feature this backend models
through ``SnowflakeClusterByClause``), not by indexes.

Two structural facts keep core's plain-index expressions from rendering here:

* core's ``CreateIndexStatement`` spells ``CREATE [UNIQUE] INDEX <index>
  ON <table> (...)`` against an ordinary table, and a ``UNIQUE`` qualifier is
  not in Snowflake's ``CREATE INDEX`` grammar at all (uniqueness is a
  constraint, not an index kind);
* core's ``DropIndexStatement`` spells ``DROP INDEX <index> [ON <table>]``
  with an unqualified index name, while Snowflake's grammar requires the
  *table-qualified* ``<table_name>.<index_name>`` and has no ``ON`` suffix.

Neither hybrid tables nor their inline ``INDEX <name> (...)`` /
``INCLUDE (...)`` definition are modelled by this backend: the statement
``CREATE HYBRID TABLE`` is not one of its statements. This module therefore
invents no hybrid-table index support. Every plain-index probe answers
``False`` and both statement formatters refuse by name rather than emit SQL the
service rejects. A caller that needs a hybrid-table secondary index must issue
raw SQL until a dedicated expression node exists for that family.

References (fetched 2026-11-25):
https://docs.snowflake.com/en/sql-reference/sql/create-index
https://docs.snowflake.com/en/sql-reference/sql/drop-index
https://docs.snowflake.com/en/sql-reference/sql/create-hybrid-table
"""

from typing import TYPE_CHECKING, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.expression.statements import (
        CreateIndexStatement,
        DropIndexStatement,
    )


class SnowflakeIndexMixin:
    """Plain-index answers for a dialect whose index DDL is hybrid-table only."""

    def supports_indexes(self) -> bool:
        """Whether ordinary tables have indexes.

        ``False``: an ordinary Snowflake table has no secondary indexes. The
        reference restricts ``CREATE INDEX`` to hybrid tables, and data layout
        for standard tables is controlled by clustering keys, which are table
        metadata rather than index objects. Hybrid-table secondary indexes are
        a different table kind this backend does not model.
        """
        return False

    def supports_create_index(self) -> bool:
        """Whether plain ``CREATE INDEX`` on an ordinary table is supported.

        ``False``: the reference's ``CREATE INDEX`` "creates a new secondary
        index in an existing hybrid table" and its ``table_name`` parameter
        names "an existing hybrid table". There is no plain index statement for
        an ordinary table, and this backend models no hybrid table. The
        formatter refuses by name.

        Reference (fetched 2026-11-25):
        https://docs.snowflake.com/en/sql-reference/sql/create-index
        """
        return False

    def supports_unique_index(self) -> bool:
        """Whether ``UNIQUE`` is an index qualifier.

        ``False``: Snowflake's ``CREATE INDEX`` grammar has no ``UNIQUE``
        qualifier. Uniqueness is expressed by a ``UNIQUE`` constraint, and the
        reference's usage notes say ``CREATE INDEX`` "cannot be used to add a
        foreign, primary, or unique key constraint".
        """
        return False

    def supports_index_if_not_exists(self) -> bool:
        """Whether ``CREATE INDEX IF NOT EXISTS`` is supported.

        ``False``: the clause exists in the hybrid-table ``CREATE INDEX``
        grammar, but this backend renders no statement of that family, so there
        is no index on which the qualifier would be accepted. The answer is
        fail-closed about the modelled statements, not a claim that the word is
        absent from Snowflake's grammar.

        Reference (fetched 2026-11-25):
        https://docs.snowflake.com/en/sql-reference/sql/create-index
        """
        return False

    def supports_index_type(self) -> bool:
        """Whether ``CREATE INDEX ... USING <type>`` is supported.

        ``False``: Snowflake's ``CREATE INDEX`` grammar has no ``USING``
        clause, and an ordinary table has no index statement at all.
        """
        return False

    def supports_partial_index(self) -> bool:
        """Whether ``CREATE INDEX ... WHERE`` (partial index) is supported.

        ``False``: the hybrid-table ``CREATE INDEX`` grammar ends at the
        column list and optional ``INCLUDE``; no ``WHERE`` clause exists.
        """
        return False

    def supports_functional_index(self) -> bool:
        """Whether an index over an expression is supported.

        ``False``: ``CREATE INDEX`` lists existing column names only; there is
        no expression position in the grammar.
        """
        return False

    def supports_index_include(self) -> bool:
        """Whether ``CREATE INDEX ... INCLUDE (...)`` is supported.

        ``False``: the clause exists in the hybrid-table grammar, but this
        backend renders no hybrid-table index statement, so it has no position
        to emit it into. The answer is fail-closed about the modelled
        statements, not a denial that the clause exists.

        Reference (fetched 2026-11-25):
        https://docs.snowflake.com/en/sql-reference/sql/create-index
        """
        return False

    def supports_index_tablespace(self) -> bool:
        """Whether ``CREATE INDEX ... TABLESPACE`` is supported.

        ``False``: Snowflake has no tablespaces, and its index grammar has no
        tablespace clause.
        """
        return False

    def supports_concurrent_index(self) -> bool:
        """Whether ``CREATE INDEX CONCURRENTLY`` is supported.

        ``False``: ``CONCURRENTLY`` is a PostgreSQL keyword. Snowflake's
        hybrid-table index build is online by default and has no such word.
        """
        return False

    def supports_drop_index(self) -> bool:
        """Whether plain ``DROP INDEX`` is supported.

        ``False``: the reference grammar is ``DROP INDEX [ IF EXISTS ]
        <table_name>.<index_name>``, which drops a secondary index on a hybrid
        table. It is table-qualified, has no ``ON`` suffix, and has no form for
        an ordinary table; this backend models no hybrid table. The formatter
        refuses by name.

        Reference (fetched 2026-11-25):
        https://docs.snowflake.com/en/sql-reference/sql/drop-index
        """
        return False

    def supports_index_if_exists(self) -> bool:
        """Whether ``DROP INDEX IF EXISTS`` is supported.

        ``False``: the qualifier exists in the hybrid-table ``DROP INDEX``
        grammar, but this backend renders no statement of that family, so there
        is nothing to decorate. The answer is fail-closed about the modelled
        statements, not a claim that the word is absent.

        Reference (fetched 2026-11-25):
        https://docs.snowflake.com/en/sql-reference/sql/drop-index
        """
        return False

    def supports_drop_index_on_table(self) -> bool:
        """Whether ``DROP INDEX`` takes an ``ON <table>`` suffix.

        ``False``: Snowflake qualifies the index name itself
        (``<table_name>.<index_name>``) and has no ``ON`` suffix. Core's shared
        formatter appends ``ON <table>`` when this probe is True, which would
        spell a statement Snowflake does not accept.
        """
        return False

    def supports_fulltext_index(self) -> bool:
        """Whether a ``FULLTEXT INDEX`` clause exists.

        ``False``: Snowflake has no ``FULLTEXT`` index. Full-text search is
        served by search optimization, which is table metadata configured with
        ``ALTER TABLE ... ADD SEARCH OPTIMIZATION``, not an index clause.
        """
        return False

    def supports_inline_index(self) -> bool:
        """Whether ordinary ``CREATE TABLE`` accepts inline index definitions.

        ``False``: the standard-table ``CREATE TABLE`` grammar has no index
        branch. Hybrid tables accept an out-of-line ``INDEX <name> (...)`` /
        ``INCLUDE (...)`` definition, but ``CREATE HYBRID TABLE`` is a different
        statement this backend does not model.
        """
        return False

    def supports_alter_table_index_actions(self) -> bool:
        """Whether ``ALTER TABLE`` has ``ADD INDEX`` / ``DROP INDEX`` actions.

        ``False``: ``ALTER TABLE``'s action list has no index action. Indexes
        are created with ``CREATE INDEX`` and dropped with ``DROP INDEX``, both
        hybrid-table only, so the alter-table actions have no spelling here.
        """
        return False

    def format_create_index_statement(
        self, expr: "CreateIndexStatement"
    ) -> Tuple[str, tuple]:
        """Refuse the plain ``CREATE INDEX`` statement by name.

        Raises:
            UnsupportedFeatureError: always on this dialect. No hybrid-table
                index statement is being emitted here.
        """
        if not self.supports_create_index():
            raise UnsupportedFeatureError(
                self.name,
                "CREATE INDEX",
                "Snowflake has no CREATE INDEX for ordinary tables. Its only "
                "index DDL is CREATE [ OR REPLACE ] INDEX [ IF NOT EXISTS ] "
                "<index_name> ON <hybrid_table> ( <col_name> [ , ... ] ) "
                "[ INCLUDE (...) ], which targets a hybrid table; this backend "
                "does not model hybrid tables. Issue raw SQL for a hybrid-table "
                "index.",
            )
        return super().format_create_index_statement(expr)

    def format_drop_index_statement(
        self, expr: "DropIndexStatement"
    ) -> Tuple[str, tuple]:
        """Refuse the plain ``DROP INDEX`` statement by name.

        Raises:
            UnsupportedFeatureError: always on this dialect. No hybrid-table
                index statement is being emitted here.
        """
        if not self.supports_drop_index():
            raise UnsupportedFeatureError(
                self.name,
                "DROP INDEX",
                "Snowflake has no DROP INDEX for ordinary tables. Its only "
                "index DDL is DROP INDEX [ IF EXISTS ] <table_name>.<index_name>, "
                "which drops a secondary index on a hybrid table; this backend "
                "does not model hybrid tables. Issue raw SQL for a hybrid-table "
                "index.",
            )
        return super().format_drop_index_statement(expr)


__all__ = ["SnowflakeIndexMixin"]
