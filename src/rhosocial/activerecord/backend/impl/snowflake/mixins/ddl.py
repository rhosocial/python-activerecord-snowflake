# src/rhosocial/activerecord/backend/impl/snowflake/mixins/ddl.py
"""Snowflake ALTER TABLE column IF [NOT] EXISTS qualifier formatting."""

from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import (
    AutoIncrementClause,
    ColumnDefaultConstraint,
    ColumnForeignKeyConstraint,
    ColumnPrimaryKeyConstraint,
    ColumnUniqueConstraint,
    IdentityClause,
)


class SnowflakeAlterColumnModifierMixin:
    """Snowflake column qualifiers for ALTER TABLE actions.

    Snowflake supports ``ADD COLUMN IF NOT EXISTS`` and
    ``DROP COLUMN IF EXISTS``, but **not** ``DROP CONSTRAINT IF EXISTS``.

    Restriction: ``ADD COLUMN IF NOT EXISTS`` cannot be combined with
    DEFAULT/AUTOINCREMENT/IDENTITY/UNIQUE/PRIMARY KEY/FOREIGN KEY on the
    same column (per Snowflake documentation). When ``if_not_exists`` is
    requested together with one of those, ``UnsupportedFeatureError`` is
    raised. IDENTITY and AUTOINCREMENT are column *clauses* carried in
    ``ColumnDefinition.attributes``, not constraints, so they are checked
    separately.

    https://docs.snowflake.com/en/sql-reference/sql/alter-table
    """

    def supports_add_column_if_not_exists(self) -> bool:
        """Snowflake supports ``ADD COLUMN IF NOT EXISTS``."""
        return True

    def supports_drop_column_if_exists(self) -> bool:
        """Snowflake supports ``DROP COLUMN IF EXISTS``."""
        return True

    def supports_drop_constraint_if_exists(self) -> bool:
        """Snowflake does **not** support ``DROP CONSTRAINT IF EXISTS``.

        The ``constraintAction`` grammar is ``DROP { CONSTRAINT
        <constraint_name> | PRIMARY KEY | UNIQUE | FOREIGN KEY ( <col_name>
        ... ) } [ CASCADE | RESTRICT ]`` -- there is no ``IF EXISTS``
        qualifier on any branch, so the formatter refuses the request by
        name instead of dropping it.

        https://docs.snowflake.com/en/sql-reference/sql/alter-table
        """
        return False

    def supports_column_comment(self) -> bool:
        """Whether inline ``COMMENT 'text'`` in a column definition is
        supported.

        Snowflake renders column comments natively (the column-level
        ``COMMENT 'text'`` form), so the capability advertises True and the
        inline path is the rendering path. Declared on this mixin, which is
        composed before the generic ``DDLColumnMixin`` in the MRO.
        """
        return True

    def format_add_column_action(self, expr) -> Tuple[str, tuple]:
        if getattr(expr, "if_not_exists", None) is True:
            # The kinds Snowflake's documented restriction names: DEFAULT,
            # IDENTITY (which ``AUTO_INCREMENT`` is a spelling of here), PRIMARY
            # KEY, FOREIGN KEY and UNIQUE.  The constraint kinds are the
            # *branch classes* now -- ``ColumnConstraintType`` is gone -- so the
            # set is a set of classes.  IDENTITY/AUTOINCREMENT are column
            # clauses in ``ColumnDefinition.attributes``, not constraints, so
            # they are tested separately.
            forbidden = {
                ColumnDefaultConstraint,
                ColumnPrimaryKeyConstraint,
                ColumnForeignKeyConstraint,
                ColumnUniqueConstraint,
            }
            identity_clauses = (IdentityClause, AutoIncrementClause)
            if any(
                type(c.branch) in forbidden for c in expr.column.constraints
            ) or any(
                isinstance(attribute, identity_clauses)
                for attribute in expr.column.attributes
            ):
                raise UnsupportedFeatureError(
                    self.name,
                    "ADD COLUMN IF NOT EXISTS with DEFAULT/IDENTITY/PK/FK/UNIQUE",
                    suggestion="Snowflake does not allow IF NOT EXISTS when the column "
                               "also specifies DEFAULT/AUTOINCREMENT/IDENTITY/UNIQUE/PK/FK. "
                               "Pre-check information_schema.COLUMNS instead.",
                )
            column_sql, column_params = self.format_column_definition(expr.column)
            return f"ADD COLUMN IF NOT EXISTS {column_sql}", column_params
        column_sql, column_params = self.format_column_definition(expr.column)
        return f"ADD COLUMN {column_sql}", column_params

    def format_drop_column_action(self, expr) -> Tuple[str, tuple]:
        name = self.format_identifier(expr.column_name)
        if getattr(expr, "if_exists", None) is True:
            return f"DROP COLUMN IF EXISTS {name}", ()
        return f"DROP COLUMN {name}", ()

    #: The ``ALTER COLUMN`` property actions this action class carries.
    _ALTER_COLUMN_ACTIONS = (
        "DROP DEFAULT",
        "SET DEFAULT",
        "SET NOT NULL",
        "DROP NOT NULL",
        "SET DATA TYPE",
    )

    def format_alter_column_action(self, expr) -> Tuple[str, tuple]:
        """Render (or refuse) Snowflake's ``ALTER COLUMN`` action.

        The reference grammar is::

            ALTER TABLE <name> { ALTER | MODIFY } [ ( ]
                  [ COLUMN ] <col> DROP DEFAULT
                , [ COLUMN ] <col> SET DEFAULT <seq_name>.NEXTVAL
                , [ COLUMN ] <col> { [ SET ] NOT NULL | DROP NOT NULL }
                , [ COLUMN ] <col> [ [ SET DATA ] TYPE ] <type>
                , [ COLUMN ] <col> COMMENT '<string>'
                , [ COLUMN ] <col> UNSET COMMENT
                [ , ... ]
                [ ) ]

        ``DROP DEFAULT``, ``SET NOT NULL`` and ``DROP NOT NULL`` go through the
        shared formatter: its spelling is exactly the clause above. ``SET
        DEFAULT`` is narrowed to the one value the grammar accepts, a sequence's
        ``NEXTVAL``. Adding a default or replacing a non-sequence default is not
        an ``ALTER COLUMN`` action at all -- it needs the full column
        re-specification ``MODIFY COLUMN <col> <type> DEFAULT <value>``, which
        carries the column type this action does not -- so that request is
        refused by name rather than rendered as SQL the server rejects.

        A raw operation word this action does not carry -- a masking or
        projection policy clause, a tag clause, or a word the grammar does not
        define -- is refused by name instead of being emitted verbatim.
        ``CASCADE`` is refused for the same reason: no ``ALTER COLUMN`` action
        in the grammar carries it.

        https://docs.snowflake.com/en/sql-reference/sql/alter-table-column
        """
        from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
            operation_spelling,
        )

        from ..expression.sequence import SnowflakeNextvalExpression

        operation = operation_spelling(expr.operation)
        if operation == "SET DEFAULT":
            value = expr.new_value
            # Only a bare ``<seq_name>.NEXTVAL`` reference is a default here.
            # The node can carry an alias for its SELECT use; an alias in a
            # DEFAULT position is not part of the grammar, so it is refused
            # rather than stripped or emitted.
            if not isinstance(value, SnowflakeNextvalExpression) or value.alias is not None:
                raise UnsupportedFeatureError(
                    self.name,
                    "ALTER COLUMN SET DEFAULT",
                    suggestion=(
                        "Snowflake changes only an existing sequence default, spelled "
                        "SET DEFAULT <seq_name>.NEXTVAL. Setting a non-sequence default "
                        "requires a full column re-specification through ALTER TABLE ... "
                        "MODIFY COLUMN <col> <type> DEFAULT <value>, because the ALTER "
                        "COLUMN action does not carry the column type."
                    ),
                )
        if operation not in self._ALTER_COLUMN_ACTIONS:
            raise UnsupportedFeatureError(
                self.name,
                f"ALTER COLUMN {operation}",
                suggestion=(
                    "This ALTER COLUMN action carries Snowflake's DROP DEFAULT, "
                    "SET DEFAULT <seq_name>.NEXTVAL, SET NOT NULL, DROP NOT NULL "
                    "and [ SET DATA ] TYPE property actions. COMMENT / UNSET "
                    "COMMENT, masking and projection policies, and tags are "
                    "separate clauses with their own actions."
                ),
            )
        if getattr(expr, "cascade", False):
            raise UnsupportedFeatureError(
                self.name,
                "ALTER COLUMN CASCADE",
                suggestion="Snowflake's ALTER COLUMN actions carry no CASCADE.",
            )
        return super().format_alter_column_action(expr)

    def format_drop_table_constraint_action(self, expr) -> Tuple[str, tuple]:
        if getattr(expr, "if_exists", None) is True:
            raise UnsupportedFeatureError(
                self.name,
                "DROP CONSTRAINT IF EXISTS",
                suggestion="Snowflake does not support IF EXISTS on DROP CONSTRAINT. "
                           "Pre-check information_schema.TABLE_CONSTRAINTS.",
            )
        name = self.format_identifier(expr.constraint_name)
        result = f"DROP CONSTRAINT {name}"
        if getattr(expr, "cascade", None):
            result += " CASCADE"
        return result, ()
