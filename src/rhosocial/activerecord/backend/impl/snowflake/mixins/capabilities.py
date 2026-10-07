# src/rhosocial/activerecord/backend/impl/snowflake/mixins/capabilities.py
"""Snowflake capability detection mixin."""
from typing import Tuple


class SnowflakeCapabilityMixin:
    """Snowflake capability detection.

    Aggregated capability checks for Snowflake features.
    """

    def supports_cte(self) -> bool:
        """Snowflake supports CTEs including recursive CTEs."""
        return True

    def supports_recursive_cte(self) -> bool:
        """Snowflake supports recursive CTEs."""
        return True

    def supports_materialized_cte(self) -> bool:
        """Snowflake has no ``MATERIALIZED`` / ``NOT MATERIALIZED`` CTE hint.

        The reference grammar for the WITH clause is
        ``<cte_name> [ ( <cte_column_list> ) ] AS ( SELECT ... )``, and the
        recursive form adds only ``[ RECURSIVE ]``; whether a CTE is
        materialised is the optimizer's decision, with no user-level hint.
        Core's shared CTE formatter reads this probe and refuses either
        spelling by name instead of rendering a hint the server rejects.

        https://docs.snowflake.com/en/sql-reference/constructs/with
        """
        return False

    def supports_window_functions(self) -> bool:
        """Snowflake supports window functions."""
        return True

    def supports_json_operations(self) -> bool:
        """Snowflake supports JSON via VARIANT type."""
        return True

    def supports_merge(self) -> bool:
        """Snowflake supports MERGE INTO with complex conditions."""
        return True

    def supports_qualify_clause(self) -> bool:
        """Snowflake supports QUALIFY clause for window function filtering."""
        return True

    def supports_upsert(self) -> bool:
        """Snowflake supports upsert via MERGE."""
        return True

    def supports_lateral_join(self) -> bool:
        """Snowflake supports LATERAL joins."""
        return True

    def supports_explain(self) -> bool:
        """Snowflake supports EXPLAIN."""
        return True

    def supports_advanced_grouping(self) -> bool:
        """Snowflake supports GROUPING SETS, ROLLUP, CUBE."""
        return True

    def supports_arrays(self) -> bool:
        """Snowflake supports ARRAY type natively."""
        return True

    def supports_views(self) -> bool:
        """Snowflake supports views."""
        return True

    def supports_create_or_replace_view(self) -> bool:
        """Snowflake supports CREATE OR REPLACE VIEW."""
        return True

    def supports_if_not_exists_view(self) -> bool:
        """Snowflake supports CREATE VIEW IF NOT EXISTS."""
        return True

    def supports_if_exists_view(self) -> bool:
        """Snowflake supports DROP VIEW IF EXISTS."""
        return True

    def supports_introspection(self) -> bool:
        """Snowflake supports introspection."""
        return True

    def supports_returning_insert(self) -> bool:
        """Snowflake supports RETURNING for INSERT from version 7.32.0+."""
        return self.version >= (7, 32, 0)

    def supports_returning_update(self) -> bool:
        """Snowflake supports RETURNING for UPDATE from version 7.32.0+."""
        return self.version >= (7, 32, 0)

    def supports_returning_delete(self) -> bool:
        """Snowflake supports RETURNING for DELETE from version 7.32.0+."""
        return self.version >= (7, 32, 0)

    def supports_filter_clause(self) -> bool:
        """Snowflake supports FILTER clause."""
        return True

    def supports_indexes(self) -> bool:
        """Snowflake supports indexes (clustering keys and search optimization)."""
        return True

    def supports_drop_index_on_table(self) -> bool:
        """Snowflake drops indexes/search-optimization by name (no ON <table>)."""
        return False

    def supports_constraints(self) -> bool:
        """Snowflake supports constraints (PK, FK, UNIQUE, NOT NULL, CHECK)."""
        return True

    def supports_sequence(self) -> bool:
        """Snowflake supports sequence objects.

        The master switch core's sequence formatters consult first. It is
        singular: core asks ``supports_sequence()``, and a probe spelled
        ``supports_sequences`` is never read, so the plural name this dialect
        used to carry left every sequence statement refusing for a spelling
        mismatch rather than a decision.
        """
        return True

    def supports_create_sequence(self) -> bool:
        """Snowflake supports ``CREATE SEQUENCE``."""
        return True

    def supports_drop_sequence(self) -> bool:
        """Snowflake supports ``DROP SEQUENCE``."""
        return True

    def supports_alter_sequence(self) -> bool:
        """Snowflake supports ``ALTER SEQUENCE``."""
        return True

    def supports_sequence_if_not_exists(self) -> bool:
        """Snowflake supports ``CREATE SEQUENCE IF NOT EXISTS``."""
        return True

    def supports_sequence_if_exists(self) -> bool:
        """Snowflake supports ``DROP SEQUENCE IF EXISTS``."""
        return True

    def supports_sequence_start(self) -> bool:
        """Snowflake supports the ``START WITH`` sequence option."""
        return True

    def supports_alter_sequence_start(self) -> bool:
        """Whether ``ALTER SEQUENCE`` accepts the ``START`` option.

        Snowflake does not. ``ALTER SEQUENCE`` cannot change a sequence's
        initial value after creation -- the reference's usage notes say so, and
        the command has neither a ``START`` nor a ``RESTART`` clause. The
        CREATE-side ``START`` is legal, so :meth:`supports_sequence_start`
        answers a different question and cannot stand in for this one.

        Stated explicitly rather than left to the shared default, because the
        direction of that default is what keeps the dialect honest: a probe
        answering ``True`` by default would let a formatter emit ``START`` on
        ``ALTER SEQUENCE`` and hand the server SQL it rejects. ``False`` fails
        closed.
        """
        return False

    def supports_sequence_increment(self) -> bool:
        """Snowflake supports the ``INCREMENT BY`` sequence option."""
        return True

    def supports_sequence_minvalue(self) -> bool:
        """Snowflake has no ``MINVALUE`` clause.

        Its own ``SEQUENCES`` metadata view reports ``MINIMUM_VALUE`` as "Not
        applicable for Snowflake".
        """
        return False

    def supports_sequence_maxvalue(self) -> bool:
        """Snowflake has no ``MAXVALUE`` clause.

        Its own ``SEQUENCES`` metadata view reports ``MAXIMUM_VALUE`` as "Not
        applicable for Snowflake".
        """
        return False

    def supports_sequence_cycle(self) -> bool:
        """Snowflake has no ``CYCLE`` clause.

        Its own ``SEQUENCES`` metadata view reports ``CYCLE_OPTION`` as "Not
        applicable for Snowflake".
        """
        return False

    def supports_sequence_cache(self) -> bool:
        """Snowflake has no ``CACHE`` clause on sequences."""
        return False

    def supports_sequence_order(self) -> bool:
        """Snowflake supports ``ORDER`` / ``NOORDER``."""
        return True

    def supports_sequence_owned_by(self) -> bool:
        """Snowflake sequences are not owned by a table column."""
        return False

    # --- Identity columns -------------------------------------------------
    #
    # Snowflake's column property is ``{ AUTOINCREMENT | IDENTITY }`` with an
    # optional ``( start_num , step_num )`` pair (or the ``START <num>
    # INCREMENT <num>`` spelling) and an optional ``ORDER | NOORDER`` tail; the
    # two keywords are synonyms. There is no ``GENERATED { ALWAYS | BY DEFAULT }
    # AS IDENTITY`` form, and no MINVALUE, MAXVALUE, CYCLE or CACHE. The
    # reference is the CREATE TABLE grammar:
    # https://docs.snowflake.com/en/sql-reference/sql/create-table

    def supports_identity_column(self) -> bool:
        """Snowflake accepts an ``IDENTITY(seed, step)`` column property.

        The reference grammar spells the property ``{ AUTOINCREMENT | IDENTITY }
        [ ( start_num , step_num ) | START <num> INCREMENT <num> ]``; this
        dialect renders the parenthesised ``IDENTITY`` spelling. The bare
        ``AUTOINCREMENT`` keyword is the same mechanism and is deliberately not
        answered by :meth:`supports_auto_increment_column`, which answers for
        core's separate parameterless marker.
        """
        return True

    def supports_identity_generation_always(self) -> bool:
        """Snowflake cannot express ``GENERATED ALWAYS``.

        Its column property is ``IDENTITY``, which permits manually inserted
        values -- the reference warns that a manual insert can collide with a
        generated value, which is ``BY DEFAULT`` semantics. ``ALWAYS``, where
        the server refuses user-supplied values, has no spelling at all, so the
        formatter refuses it rather than rendering a downgraded clause.
        """
        return False

    def supports_identity_start(self) -> bool:
        """Snowflake's ``IDENTITY`` accepts the start value.

        Both reference spellings carry it: ``IDENTITY( <start_num> , <step_num>
        )`` and ``IDENTITY START <num> INCREMENT <num>``. This dialect renders
        the parenthesised form.
        """
        return True

    def supports_identity_increment(self) -> bool:
        """Snowflake's ``IDENTITY`` accepts the step/increment value.

        See :meth:`supports_identity_start` for the two reference spellings.
        """
        return True

    def supports_identity_minvalue(self) -> bool:
        """Snowflake's ``IDENTITY`` has no ``MINVALUE`` option.

        The reference grammar gives the property exactly two parameter
        spellings -- the ``( start_num , step_num )`` pair and ``START <num>
        INCREMENT <num>`` -- plus ``ORDER | NOORDER``. There is no minimum-value
        clause to render, so a request is refused rather than dropped.
        """
        return False

    def supports_identity_maxvalue(self) -> bool:
        """Snowflake's ``IDENTITY`` has no ``MAXVALUE`` option.

        See :meth:`supports_identity_minvalue` for the reference grammar.
        """
        return False

    def supports_identity_cycle(self) -> bool:
        """Snowflake's ``IDENTITY`` has no ``CYCLE`` option.

        See :meth:`supports_identity_minvalue` for the reference grammar.
        """
        return False

    def supports_identity_order(self) -> bool:
        """Snowflake's ``IDENTITY`` accepts the ``ORDER`` / ``NOORDER`` tail.

        The column property's reference grammar ends with ``[ { ORDER | NOORDER
        } ]`` -- *after* the ``( start_num , step_num )`` / ``START <num>
        INCREMENT <num>`` group, not inside it -- and the negative spelling is
        one word:

            { AUTOINCREMENT | IDENTITY }
              [ { ( <start_num> , <step_num> ) | START <num> INCREMENT <num> } ]
              [ { ORDER | NOORDER } ]

        Two independent reference pages carry the tail: the column definition
        on the ``CREATE TABLE`` page, and ``tableColumnAction`` on the
        ``ALTER TABLE`` page. The renderer spells the negative form through
        :meth:`identity_order_keyword`, which this dialect overrides to
        ``NOORDER``; the keyword belongs after the parenthesis group.

        https://docs.snowflake.com/en/sql-reference/sql/create-table
        https://docs.snowflake.com/en/sql-reference/sql/alter-table
        """
        return True

    def supports_identity_cache(self) -> bool:
        """Snowflake's ``IDENTITY`` has no ``CACHE`` option.

        The reference grammar gives the property exactly two parameter
        spellings -- the ``( start_num , step_num )`` pair and ``START <num>
        INCREMENT <num>`` -- plus ``ORDER | NOORDER``. There is no cache clause
        to render, so a request is refused rather than dropped. See
        :meth:`supports_identity_order` for the two reference pages.
        """
        return False

    def supports_auto_increment_column(self) -> bool:
        """Snowflake has no bare ``AUTO_INCREMENT`` marker.

        Snowflake's keyword is ``AUTOINCREMENT`` -- one word, no underscore --
        and it is a *synonym of* ``IDENTITY``, so like ``IDENTITY`` it carries
        the ``( start_num , step_num )`` / ``START ... INCREMENT ...`` /
        ``ORDER`` tail. Core's parameterless ``AutoIncrementClause`` renders the
        two-word ``AUTO_INCREMENT`` spelling, which is not in Snowflake's
        grammar, so the probe answers ``False`` and the marker is refused.
        Parameterised key generation is carried by ``IdentityClause`` and
        rendered as ``IDENTITY(seed, step)``.
        """
        return False

    def supports_explicit_inner_join(self) -> bool:
        """Snowflake supports explicit INNER JOIN syntax."""
        return True

    def supports_modify_column(self) -> bool:
        """Snowflake supports ALTER TABLE MODIFY COLUMN."""
        return True

    def supports_if_exists_table(self) -> bool:
        """Snowflake supports DROP TABLE IF EXISTS."""
        return True

    def supports_drop_table_cascade(self) -> bool:
        """Snowflake does not support standard CASCADE for DROP TABLE."""
        return False

    def supports_alter_column_type(self) -> bool:
        """Snowflake changes a column type in place via MODIFY COLUMN."""
        return True

    def alter_column_type_action(self, old_col, new_col):
        """Build the in-place type-change action (MODIFY COLUMN)."""
        from rhosocial.activerecord.backend.expression.statements.ddl_alter import ModifyColumn

        return ModifyColumn(self, column=new_col)

    def format_modify_column_action(self, action) -> Tuple[str, tuple]:
        """Render Snowflake ALTER TABLE ... MODIFY COLUMN <col> <type>."""
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            ColumnConstraintType,
        )

        col = action.column
        type_sql, _ = self.format_data_type(col.data_type)
        parts = [type_sql]
        for c in col.constraints:
            if c.constraint_type == ColumnConstraintType.NOT_NULL:
                parts.append("NOT NULL")
            elif c.constraint_type == ColumnConstraintType.NULL:
                parts.append("NULL")
            elif c.constraint_type == ColumnConstraintType.DEFAULT and c.default_value is not None:
                from rhosocial.activerecord.backend.expression.core import Literal

                lit_sql, lit_params = Literal(self, c.default_value).to_sql()
                parts.append(f"DEFAULT {lit_sql}")
        spec = " ".join(parts)
        return f"MODIFY COLUMN {self.format_identifier(col.name)} {spec}", ()

    def supports_alter_column_properties(self) -> bool:
        """Snowflake has no independent ALTER COLUMN SET DEFAULT clause."""
        return False

    def supports_alter_table_index_actions(self) -> bool:
        """Snowflake has no traditional indexes."""
        return False


__all__ = ['SnowflakeCapabilityMixin']
