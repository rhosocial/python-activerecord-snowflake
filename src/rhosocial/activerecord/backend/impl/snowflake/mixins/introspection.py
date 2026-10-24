# src/rhosocial/activerecord/backend/impl/snowflake/mixins/introspection.py
"""SnowflakeIntrospectionMixin — schema introspection via INFORMATION_SCHEMA."""
from typing import List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import (
    Column,
    ComparisonPredicate,
    FunctionCall,
    InPredicate,
    IsNullPredicate,
    LikeOperator,
    LikePredicate,
    Literal,
    LogicalPredicate,
    OrderByClause,
    QueryStatement,
    WhereClause,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.query_parts import JoinClause, JoinType
from rhosocial.activerecord.backend.expression.sources.relation import NamedRelationRef

from ..expression.introspection import (
    SnowflakeDatabaseListQueryStatement,
    SnowflakeSchemaListQueryStatement,
    SnowflakeTableStorageMetricsQueryStatement,
    SnowflakeWarehouseListQueryStatement,
)
from ..expression.show import SnowflakeShowObjectType, SnowflakeShowStatement

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.introspection import (
        DatabaseInfoQueryStatement,
        TableListQueryStatement,
        ColumnInfoQueryStatement,
        IndexInfoQueryStatement,
        ForeignKeyQueryStatement,
        ViewListQueryStatement,
        ViewInfoQueryStatement,
        TriggerListQueryStatement,
    )
    from rhosocial.activerecord.backend.introspection.types import IntrospectionScope


class SnowflakeIntrospectionMixin:
    """Snowflake introspection capability declaration and query formatting.

    This mixin implements the IntrospectionSupport protocol by:
    1. Declaring which introspection features Snowflake supports (supports_* methods)
    2. Formatting SQL queries for introspection (format_*_query methods)

    The format_*_query methods are called by Expression.to_sql() to generate
    database-specific SQL using INFORMATION_SCHEMA.

    Architecture flow:
        Introspector._build_*_sql() [base class]
            -> Expression(Dialect).to_sql()
                -> Dialect.format_*_query() [this mixin]
                    -> Returns SQL and parameters

    Snowflake supports introspection via INFORMATION_SCHEMA views.
    Snowflake does not support traditional indexes or triggers.

    Every formatter here builds a **tree**, not text. The projection is a list
    of :class:`~rhosocial.activerecord.backend.expression.core.Column` nodes,
    the filtering a conjunction of predicate nodes, and the whole question a
    :class:`~rhosocial.activerecord.backend.expression.statements.QueryStatement`
    that renders itself through the dialect. Nothing in this file writes a
    ``SELECT`` keyword, a comma or a placeholder: the statements below used to
    be assembled one string fragment at a time, and the fragmentation was the
    defect -- a clause added in one branch and forgotten in another is
    invisible in a concatenation and obvious in a tree.
    """

    def supports_warehouse_introspection(self) -> bool:
        """Snowflake answers for its warehouses from ``SHOW WAREHOUSES``.

        The capability for the ``introspect warehouses`` family. There
        is no INFORMATION_SCHEMA view for them, which is why the
        statement is a SHOW rather than a SELECT."""
        return True

    def supports_schema_introspection(self) -> bool:
        """Snowflake answers for its schemas from ``INFORMATION_SCHEMA.SCHEMATA``.

        The capability for the ``introspect schemas`` family; a schema
        here is a level below a database, which is why it is not the
        same switch as the database one."""
        return True

    def supports_database_introspection(self) -> bool:
        """Snowflake answers for its databases from ``INFORMATION_SCHEMA.DATABASES``.

        The capability for the ``introspect databases`` family -- an
        account-level question the other engines do not have."""
        return True

    # ========== Capability Detection ==========

    def supports_introspection(self) -> bool:
        """Snowflake supports introspection via INFORMATION_SCHEMA."""
        return True

    def supports_database_info(self) -> bool:
        """Snowflake supports database info via context functions."""
        return True

    def supports_table_introspection(self) -> bool:
        """Snowflake supports table introspection via INFORMATION_SCHEMA.TABLES."""
        return True

    def supports_column_introspection(self) -> bool:
        """Snowflake supports column introspection via INFORMATION_SCHEMA.COLUMNS."""
        return True

    def supports_index_introspection(self) -> bool:
        """Snowflake does not have traditional indexes; uses constraints instead."""
        return True

    def supports_foreign_key_introspection(self) -> bool:
        """Snowflake supports foreign key introspection via INFORMATION_SCHEMA."""
        return True

    def supports_view_introspection(self) -> bool:
        """Snowflake supports view introspection via INFORMATION_SCHEMA.VIEWS."""
        return True

    def supports_trigger_introspection(self) -> bool:
        """Snowflake does not support triggers."""
        return False

    def get_supported_introspection_scopes(self) -> List["IntrospectionScope"]:
        """Get list of supported introspection scopes."""
        from rhosocial.activerecord.backend.introspection.types import IntrospectionScope
        return [
            IntrospectionScope.DATABASE,
            IntrospectionScope.TABLE,
            IntrospectionScope.COLUMN,
            IntrospectionScope.INDEX,
            IntrospectionScope.FOREIGN_KEY,
            IntrospectionScope.VIEW,
        ]

    # ========== The catalog read, expressed once ==========

    # ------------------------------------------------------------------
    # Why the catalog objects are spelled unquoted
    # ------------------------------------------------------------------
    # Every Information Schema view and column this mixin names is written
    # with ``*_need_quote=False``, so the rendered SQL reads
    # ``INFORMATION_SCHEMA.TABLES`` and ``TABLE_SCHEMA`` the way the manual
    # spells them. That is not carelessness about quoting, it is the rule the
    # manual states: "Snowflake automatically converts unquoted,
    # case-insensitive identifiers to uppercase internally, so unquoted object
    # names must be queried in uppercase in the Information Schema views"
    # (https://docs.snowflake.com/en/sql-reference/info-schema). The catalog
    # stores these names uppercase, so an unquoted reference resolves to
    # exactly the object the manual documents, and quoting each one -- which
    # this dialect does by default, for the case-sensitive names users create
    # -- would only make the statement harder to read against its source page.
    # The one exception is a *database* named by the caller, which is quoted:
    # it may have been created with quotes and then carries its case.

    def _catalog_column(
        self,
        name: str,
        table: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> Column:
        """One Information Schema column reference, in the manual's spelling.

        Args:
            name: The column name as the manual writes it, uppercase.
            table: Optional alias of the view it is read from (``m``, ``t``,
                ``tc``, ...), unquoted for the same reason as the column.
            alias: Optional result alias, used where a projection combines two
                views' columns under one documented name.

        Returns:
            The column node, ready to be selected, compared or ordered by.
        """
        return Column(
            self,
            name,
            table=table,
            alias=alias,
            table_need_quote=False,
            name_need_quote=False,
            alias_need_quote=False,
        )

    def _information_schema_view(
        self,
        name: str,
        alias: Optional[str] = None,
        catalog: Optional[str] = None,
        catalog_need_quote: bool = True,
    ) -> NamedRelationRef:
        """One view of the ``INFORMATION_SCHEMA`` schema, as a row source.

        The schema name itself is never quoted and never omitted: the manual
        says a view must be named either fully qualified,
        ``database.INFORMATION_SCHEMA.name``, or as
        ``INFORMATION_SCHEMA.name`` with that schema in use
        (https://docs.snowflake.com/en/sql-reference/info-schema), and this
        backend always writes the second form or the first -- never a bare
        ``TABLES``, which would silently read a user's object of that name.

        Args:
            name: The view's name, uppercase.
            alias: Optional short alias for a query that reads two views.
            catalog: The database to qualify the view with, or ``None`` to
                leave it to the session's current database.
            catalog_need_quote: Whether to quote *catalog*. ``True`` (the
                default) for a name a caller supplied, which may be
                case-sensitive; ``False`` for this backend's own ``SNOWFLAKE``
                qualifier, which is a fixed word.

        Returns:
            The row source, ready to be handed to a statement's ``from_``.
        """
        return NamedRelationRef(
            self,
            Table(
                self,
                name,
                catalog_name=catalog,
                schema_name="INFORMATION_SCHEMA",
                catalog_need_quote=catalog_need_quote,
                schema_need_quote=False,
                name_need_quote=False,
            ),
            alias=alias,
            alias_need_quote=False,
        )

    def _catalog_query(
        self,
        projections: List[Column],
        source,
        conditions: Optional[List] = None,
        order_by: Optional[List[Column]] = None,
    ) -> Tuple[str, tuple]:
        """Build one ``SELECT`` over a catalog source as an expression tree.

        Every question this mixin asks the catalog has the same shape -- a
        projection, a conjunction of conditions and an optional ordering -- so
        the shape lives here and each formatter supplies only what varies.

        Args:
            projections: The select list, in order.
            source: The row source: one view, or a
                :class:`~rhosocial.activerecord.backend.expression.query_parts.JoinClause`
                over two of them.
            conditions: Conditions to AND together, or ``None`` for no
                ``WHERE`` clause.
            order_by: The ordering expressions, or ``None`` for no ``ORDER BY``.

        Returns:
            Tuple of (SQL string, parameters tuple).
        """
        statement = QueryStatement(self, select=projections, from_=source)
        if conditions:
            statement.where = WhereClause(
                self, LogicalPredicate(self, "AND", *conditions)
            )
        if order_by is not None:
            statement.order_by = OrderByClause(self, order_by)
        return statement.to_sql()

    # ========== Query Formatting ==========

    def format_database_info_query_statement(
        self, expr: "DatabaseInfoQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format database information query using context functions."""
        # No FROM: this query reads no table, it asks the engine a question.
        return QueryStatement(
            self,
            select=[
                FunctionCall(self, "CURRENT_DATABASE", alias="CATALOG_NAME"),
                FunctionCall(self, "CURRENT_VERSION", alias="SERVER_VERSION"),
            ],
        ).to_sql()

    def format_table_list_query_statement(
        self, expr: "TableListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format table list query using INFORMATION_SCHEMA.TABLES."""
        params = expr.get_params()
        schema = params.get("schema", "")
        include_views = params.get("include_views", True)
        include_system = params.get("include_system", False)
        table_type = params.get("table_type")

        conditions = [
            ComparisonPredicate(
                self, "eq", self._catalog_column("TABLE_SCHEMA"), Literal(self, schema)
            )
        ]

        # The two system schemas Snowflake creates in every database. They are
        # inline values, not bind parameters: the string is part of the
        # statement's own meaning and never came from a caller.
        if not include_system:
            conditions.append(
                ~InPredicate(
                    self,
                    self._catalog_column("TABLE_SCHEMA"),
                    Literal(
                        self, ["information_schema", "PUBLIC"], inline=True
                    ),
                )
            )
        if not include_views:
            conditions.append(
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_TYPE"),
                    Literal(self, "BASE TABLE", inline=True),
                )
            )
        if table_type:
            conditions.append(
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_TYPE"),
                    Literal(self, table_type),
                )
            )

        return self._catalog_query(
            [
                self._catalog_column("TABLE_NAME"),
                self._catalog_column("TABLE_TYPE"),
                self._catalog_column("COMMENT"),
            ],
            self._information_schema_view("TABLES"),
            conditions,
            [self._catalog_column("TABLE_NAME")],
        )

    def format_column_info_query_statement(
        self, expr: "ColumnInfoQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format column information query using INFORMATION_SCHEMA.COLUMNS."""
        params = expr.get_params()
        table_name = params.get("table", params.get("table_name", ""))
        schema = params.get("schema", "")

        return self._catalog_query(
            [
                self._catalog_column("COLUMN_NAME"),
                self._catalog_column("ORDINAL_POSITION"),
                self._catalog_column("COLUMN_DEFAULT"),
                self._catalog_column("IS_NULLABLE"),
                self._catalog_column("DATA_TYPE"),
                self._catalog_column("CHARACTER_MAXIMUM_LENGTH"),
                self._catalog_column("NUMERIC_PRECISION"),
                self._catalog_column("NUMERIC_SCALE"),
                self._catalog_column("COLLATION_NAME"),
                self._catalog_column("COMMENT"),
            ],
            self._information_schema_view("COLUMNS"),
            [
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_SCHEMA"),
                    Literal(self, schema),
                ),
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_NAME"),
                    Literal(self, table_name),
                ),
            ],
            [self._catalog_column("ORDINAL_POSITION")],
        )

    def format_index_info_query_statement(
        self, expr: "IndexInfoQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format index information query using constraints.

        Snowflake does not have traditional indexes. This queries
        TABLE_CONSTRAINTS + KEY_COLUMN_USAGE for PRIMARY KEY and UNIQUE
        constraints, which serve as the closest analog.
        """
        params = expr.get_params()
        table_name = params.get("table", params.get("table_name", ""))
        schema = params.get("schema", "")

        join = JoinClause(
            self,
            left_table=self._information_schema_view("TABLE_CONSTRAINTS", "tc"),
            right_table=self._information_schema_view("KEY_COLUMN_USAGE", "kcu"),
            join_type=JoinType.INNER,
            condition=LogicalPredicate(
                self,
                "AND",
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("CONSTRAINT_NAME", "tc"),
                    self._catalog_column("CONSTRAINT_NAME", "kcu"),
                ),
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_SCHEMA", "tc"),
                    self._catalog_column("TABLE_SCHEMA", "kcu"),
                ),
            ),
        )
        return self._catalog_query(
            [
                self._catalog_column("CONSTRAINT_NAME", "tc"),
                self._catalog_column("CONSTRAINT_TYPE", "tc"),
                self._catalog_column("COLUMN_NAME", "kcu"),
                self._catalog_column("ORDINAL_POSITION", "kcu"),
            ],
            join,
            [
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_SCHEMA", "tc"),
                    Literal(self, schema),
                ),
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_NAME", "tc"),
                    Literal(self, table_name),
                ),
                # Inline: the two constraint names are the statement's own
                # vocabulary, not a caller's value.
                InPredicate(
                    self,
                    self._catalog_column("CONSTRAINT_TYPE", "tc"),
                    Literal(
                        self, ["PRIMARY KEY", "UNIQUE"], inline=True
                    ),
                ),
            ],
            [
                self._catalog_column("CONSTRAINT_NAME", "tc"),
                self._catalog_column("ORDINAL_POSITION", "kcu"),
            ],
        )

    def format_foreign_key_query_statement(
        self, expr: "ForeignKeyQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format foreign key information query.

        Joins REFERENTIAL_CONSTRAINTS, KEY_COLUMN_USAGE, and
        TABLE_CONSTRAINTS to resolve referenced table and columns.

        Chained joins nest rather than flattening: the rendered ``FROM`` reads
        ``((rc JOIN kcu ...) JOIN utc ...) JOIN ukcu ...`` where the old
        concatenated text read ``rc JOIN kcu ... JOIN utc ... JOIN ukcu ...``.
        The two are the same four-way read -- the parentheses only make
        explicit the grouping the framework already knows -- and the tree is
        kept because writing the flat spelling by hand would put the clause
        text back in this file.
        """
        params = expr.get_params()
        table_name = params.get("table", params.get("table_name", ""))
        schema = params.get("schema", "")

        def _same(left: str, right: str, table: str, other: str) -> ComparisonPredicate:
            """One equality of two views' identically-named columns."""
            return ComparisonPredicate(
                self,
                "eq",
                self._catalog_column(left, table),
                self._catalog_column(right, other),
            )

        # Named per view, then joined in the order the original statement
        # joined them: the constraint, its columns, the constraint it points
        # at, and that constraint's columns.
        source = JoinClause(
            self,
            left_table=self._information_schema_view("REFERENTIAL_CONSTRAINTS", "rc"),
            right_table=self._information_schema_view("KEY_COLUMN_USAGE", "kcu"),
            join_type=JoinType.INNER,
            condition=LogicalPredicate(
                self,
                "AND",
                _same("CONSTRAINT_NAME", "CONSTRAINT_NAME", "rc", "kcu"),
                _same("CONSTRAINT_SCHEMA", "CONSTRAINT_SCHEMA", "rc", "kcu"),
            ),
        ).join(
            right_table=self._information_schema_view("TABLE_CONSTRAINTS", "utc"),
            join_type="JOIN",
            condition=LogicalPredicate(
                self,
                "AND",
                _same("UNIQUE_CONSTRAINT_NAME", "CONSTRAINT_NAME", "rc", "utc"),
                _same("UNIQUE_CONSTRAINT_SCHEMA", "CONSTRAINT_SCHEMA", "rc", "utc"),
            ),
        ).join(
            right_table=self._information_schema_view("KEY_COLUMN_USAGE", "ukcu"),
            join_type="JOIN",
            condition=LogicalPredicate(
                self,
                "AND",
                _same("UNIQUE_CONSTRAINT_NAME", "CONSTRAINT_NAME", "rc", "ukcu"),
                _same("UNIQUE_CONSTRAINT_SCHEMA", "CONSTRAINT_SCHEMA", "rc", "ukcu"),
                _same("POSITION_IN_UNIQUE_CONSTRAINT", "ORDINAL_POSITION", "kcu", "ukcu"),
            ),
        )
        return self._catalog_query(
            [
                self._catalog_column("CONSTRAINT_NAME", "rc"),
                self._catalog_column("UPDATE_RULE", "rc"),
                self._catalog_column("DELETE_RULE", "rc"),
                self._catalog_column("COLUMN_NAME", "kcu"),
                self._catalog_column("ORDINAL_POSITION", "kcu"),
                self._catalog_column("TABLE_NAME", "utc", alias="REFERENCED_TABLE_NAME"),
                self._catalog_column(
                    "COLUMN_NAME", "ukcu", alias="REFERENCED_COLUMN_NAME"
                ),
            ],
            source,
            [
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("CONSTRAINT_SCHEMA", "rc"),
                    Literal(self, schema),
                ),
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_NAME", "kcu"),
                    Literal(self, table_name),
                ),
            ],
            [
                self._catalog_column("CONSTRAINT_NAME", "rc"),
                self._catalog_column("ORDINAL_POSITION", "kcu"),
            ],
        )

    def format_view_list_query_statement(
        self, expr: "ViewListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format view list query using INFORMATION_SCHEMA.VIEWS."""
        params = expr.get_params()
        schema = params.get("schema", "")
        include_system = params.get("include_system", False)

        conditions = [
            ComparisonPredicate(
                self,
                "eq",
                self._catalog_column("TABLE_SCHEMA"),
                Literal(self, schema),
            )
        ]
        if not include_system:
            conditions.append(
                LikePredicate(
                    self,
                    LikeOperator.NOT_LIKE,
                    self._catalog_column("TABLE_SCHEMA"),
                    Literal(self, "information_schema", inline=True),
                )
            )

        return self._catalog_query(
            [
                self._catalog_column("TABLE_NAME"),
                self._catalog_column("VIEW_DEFINITION"),
                self._catalog_column("CHECK_OPTION"),
                self._catalog_column("IS_UPDATABLE"),
            ],
            self._information_schema_view("VIEWS"),
            conditions,
            [self._catalog_column("TABLE_NAME")],
        )

    def format_view_info_query_statement(
        self, expr: "ViewInfoQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format single view information query."""
        params = expr.get_params()
        view_name = params.get("view_name", "")
        schema = params.get("schema", "")

        return self._catalog_query(
            [
                self._catalog_column("TABLE_NAME"),
                self._catalog_column("VIEW_DEFINITION"),
                self._catalog_column("CHECK_OPTION"),
                self._catalog_column("IS_UPDATABLE"),
            ],
            self._information_schema_view("VIEWS"),
            [
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_SCHEMA"),
                    Literal(self, schema),
                ),
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_NAME"),
                    Literal(self, view_name),
                ),
            ],
        )

    def format_trigger_list_query_statement(
        self, expr: "TriggerListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Snowflake does not support triggers; return empty result."""
        # The predicate is a node like any other, so "always false" is stated
        # rather than typed out, and the statement renders the same empty
        # read the concatenated form produced.
        return QueryStatement(
            self,
            select=[Literal(self, 1, inline=True)],
            where=WhereClause(
                self,
                ComparisonPredicate(
                    self,
                    "eq",
                    Literal(self, 1, inline=True),
                    Literal(self, 0, inline=True),
                ),
            ),
        ).to_sql()

    def format_trigger_info_query_statement(
        self, expr
    ) -> Tuple[str, tuple]:
        """Snowflake does not support triggers; return empty result."""
        return self.format_trigger_list_query_statement(expr)

    # ------------------------------------------------------------------ #
    # Account-level objects: databases, schemas, warehouses, storage
    #
    # Each formatter names the official page its columns were read from. None
    # of them ran against an account: this repository has no Snowflake
    # instance, so what the tests pin is the statement and the parser, never
    # the answer.
    # ------------------------------------------------------------------ #

    def format_database_list_query_statement(
        self, expr: SnowflakeDatabaseListQueryStatement
    ) -> Tuple[str, tuple]:
        """``INFORMATION_SCHEMA.DATABASES``, one row per database in the account.

        Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/databases

        Columns selected, and why each is read:

        * ``DATABASE_NAME`` -- the name; the view uses "database" where every
          other Information Schema view says "catalog".
        * ``DATABASE_OWNER``, ``OWNER_ROLE_TYPE`` -- ownership, including the
          documented ``APPLICATION`` case for native apps.
        * ``IS_TRANSIENT`` -- documented ``VARCHAR``; ``'YES'`` for transient.
        * ``COMMENT``, ``CREATED``, ``LAST_ALTERED``, ``RETENTION_TIME``,
          ``TYPE`` -- the view's remaining columns, all documented on that page.

        Qualified with ``SNOWFLAKE`` on purpose. The page states the view
        "contains all of the databases in the account (regardless of the
        database's INFORMATION_SCHEMA used to query the view)", so the
        qualification chooses nothing about the answer; it only gives the
        statement a database to resolve ``INFORMATION_SCHEMA`` against when the
        session has no current database, which is exactly the state the CLI is
        in when it is given ``--account`` but no ``--database``. The manual's
        own example writes ``SNOWFLAKE.ACCOUNT_USAGE.DATABASES`` in the same
        unquoted spelling (https://docs.snowflake.com/en/sql-reference/account-usage).

        ``SELECT *`` is avoided per the Information Schema topic's own note that
        "The Snowflake-specific views are subject to change. Avoid selecting
        all columns from these views. Instead, select the columns that you want"
        (https://docs.snowflake.com/en/sql-reference/info-schema).

        The view "only displays objects for which the current role for the
        session has been granted access privileges" and "does not honor the
        MANAGE GRANTS privilege", so this is the privilege-filtered answer, not
        a claim of omniscience.
        """
        return self._catalog_query(
            [
                self._catalog_column("DATABASE_NAME"),
                self._catalog_column("DATABASE_OWNER"),
                self._catalog_column("IS_TRANSIENT"),
                self._catalog_column("COMMENT"),
                self._catalog_column("CREATED"),
                self._catalog_column("LAST_ALTERED"),
                self._catalog_column("RETENTION_TIME"),
                self._catalog_column("TYPE"),
                self._catalog_column("OWNER_ROLE_TYPE"),
            ],
            self._information_schema_view(
                "DATABASES", catalog="SNOWFLAKE", catalog_need_quote=False
            ),
            order_by=[self._catalog_column("DATABASE_NAME")],
        )

    def format_schema_list_query_statement(
        self, expr: SnowflakeSchemaListQueryStatement
    ) -> Tuple[str, tuple]:
        """``INFORMATION_SCHEMA.SCHEMATA`` for one database, or the current one.

        Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/schemata

        Columns selected: ``CATALOG_NAME`` (the database), ``SCHEMA_NAME``,
        ``SCHEMA_OWNER``, ``IS_TRANSIENT``, ``IS_MANAGED_ACCESS``,
        ``RETENTION_TIME``, ``CREATED``, ``LAST_ALTERED``, ``COMMENT`` -- every
        column of this view the manual does not mark "Not applicable for
        Snowflake" (``DEFAULT_CHARACTER_SET_*``, ``SQL_PATH``).

        The view is a **database-level** one: the page says it "displays a row
        for each schema in the specified (or current) database, including the
        INFORMATION_SCHEMA schema itself". So listing another database requires
        qualifying the view with it; there is no account-wide ``SCHEMATA``.
        ``database=None`` therefore means "whatever database the session is
        in", and is a legitimate request rather than a missing argument.

        A database name cannot be a bind parameter -- it is part of the object
        name, not a value -- so it is rendered by the dialect as a quoted
        identifier. Quoting is case-sensitive in Snowflake, so a caller passes
        the catalog's own spelling; an unquoted object is stored uppercase and a
        lower-case name that was never created with quotes will not match a
        quoted one.
        """
        return self._catalog_query(
            [
                self._catalog_column("CATALOG_NAME"),
                self._catalog_column("SCHEMA_NAME"),
                self._catalog_column("SCHEMA_OWNER"),
                self._catalog_column("IS_TRANSIENT"),
                self._catalog_column("IS_MANAGED_ACCESS"),
                self._catalog_column("RETENTION_TIME"),
                self._catalog_column("CREATED"),
                self._catalog_column("LAST_ALTERED"),
                self._catalog_column("COMMENT"),
            ],
            self._information_schema_view(
                "SCHEMATA", catalog=expr.database or None
            ),
            order_by=[self._catalog_column("SCHEMA_NAME")],
        )

    def format_warehouse_list_query_statement(
        self, expr: SnowflakeWarehouseListQueryStatement
    ) -> Tuple[str, tuple]:
        """``SHOW WAREHOUSES`` -- there is no Information Schema view for them.

        Documentation: https://docs.snowflake.com/en/sql-reference/sql/show-warehouses

        Checked against the Information Schema view index, which lists no
        ``WAREHOUSES`` view (https://docs.snowflake.com/en/sql-reference/info-schema;
        the direct ``/info-schema/warehouses`` URL answers 404), and against the
        Account Usage view list, which carries only ``WAREHOUSE_LOAD_HISTORY``,
        ``WAREHOUSE_METERING_HISTORY`` and ``WAREHOUSE_EVENTS_HISTORY``
        (https://docs.snowflake.com/en/sql-reference/account-usage) -- no object
        view for a warehouse in either schema. The documented access path is
        therefore the ``SHOW`` command, and
        :class:`~...expression.show.SnowflakeShowStatement` renders it so the
        ``SHOW`` spelling stays in one place.

        **Row shape.** ``SHOW`` is not a ``SELECT``: its output columns are
        documented in *lowercase* -- the page says so outright, "You must use
        double-quoted identifiers because the output column names for SHOW
        commands are in lowercase" -- unlike Information Schema columns, which
        are uppercase. The parser normalizes keys before reading them, so both
        shapes work. Values also differ from the views: the page's own sample
        output shows ``is_default`` / ``is_current`` as ``Y``/``N`` and
        ``auto_resume`` as ``true``, while Information Schema flags are
        ``'YES'``/``'NO'``.

        Two more documented facts bound what this answer is:

        * "The command only returns objects for which the current user's
          current role has been granted at least one access privilege" -- it is
          the privilege-filtered list, like the views.
        * "The command returns a maximum of ten thousand records for the
          specified object type" -- the page points at the corresponding view
          "if one exists" past that limit, and for warehouses none does, so a
          10,000-warehouse account cannot be fully listed this way. The list is
          not truncated here; there is nothing to truncate it with.

        **Why not ``RESULT_SCAN``.** ``RESULT_SCAN(LAST_QUERY_ID())`` is the
        documented way to post-process ``SHOW`` output inside SQL, and it is
        *not* used here. The function scans "the most recent SQL command",
        which is session-global state rather than this call's result. Any
        statement executed between the ``SHOW`` and the scan -- including a
        cache miss elsewhere in the same backend -- makes ``RESULT_SCAN`` read
        the wrong query, and it fails silently rather than erroring. The driver
        already exposes a ``SHOW`` result set through ``cursor.description``,
        which is per-cursor and cannot be displaced, so this backend reads that.
        """
        return SnowflakeShowStatement(
            self, SnowflakeShowObjectType.WAREHOUSES
        ).to_sql()

    def format_table_storage_metrics_query_statement(
        self, expr: SnowflakeTableStorageMetricsQueryStatement
    ) -> Tuple[str, tuple]:
        """Billed storage for one table, joined to its row count and clustering.

        Documentation for the primary view:
        https://docs.snowflake.com/en/sql-reference/info-schema/table_storage_metrics
        Documentation for the joined view:
        https://docs.snowflake.com/en/sql-reference/info-schema/tables

        ``TABLE_STORAGE_METRICS`` documents these columns, all selected from
        ``m``: ``TABLE_CATALOG``, ``TABLE_SCHEMA``, ``TABLE_NAME``, ``ID``,
        ``CLONE_GROUP_ID``, ``IS_TRANSIENT``, ``ACTIVE_BYTES``,
        ``TIME_TRAVEL_BYTES``, ``FAILSAFE_BYTES``, ``RETAINED_FOR_CLONE_BYTES``,
        ``TABLE_CREATED``, ``TABLE_DROPPED``, ``TABLE_ENTERED_FAILSAFE`` and
        ``COMMENT``. It does **not** document a row count, a table type or a
        clustering key -- the page's column table has none of them -- so those
        come from ``TABLES``, which documents ``ROW_COUNT`` ("Number of rows in
        the table"), ``CLUSTERING_KEY`` ("Clustering key for the table"),
        ``AUTO_CLUSTERING_ON`` (``BOOLEAN``) and ``TABLE_TYPE``. The join is on
        the three-part name because both views carry the catalog, schema and
        table name; it is a ``LEFT`` join because the storage view keeps rows
        for dropped tables that ``TABLES`` no longer lists.

        The statement is rendered from a tree, so the two short aliases the
        manual's examples use are carried by the row sources and the ``ON``
        condition is a conjunction of three equalities rather than one string.
        Both come out as the same query the concatenated form produced.

        **Current version only.** The storage page documents that multiple rows
        can share a ``TABLE_NAME``: "A version is created each time a table is
        dropped and a new table with the same name is created ... the current
        version will have a NULL value for the TABLE_DROPPED column; all other
        versions will have a timestamp value." Filtering to the current version
        keeps the join honest -- ``TABLES`` no longer lists dropped tables, so
        joining a dropped version would attach the live table's row count to a
        dead one -- and it is the version "storage metrics for this table"
        means. Dropped versions remain queryable by the view itself; this method
        deliberately answers for the live table.

        ``TABLES.BYTES`` is deliberately not selected. The page documents it as
        "Number of bytes accessed by a scan of the table" and warns that
        ``SUM(bytes)`` "does not represent the total storage usage"; the billed
        categories above are the authoritative byte numbers, and selecting a
        second, differently-meaning byte column would invite them to be
        confused.

        **Role requirement.** The storage page states the view "is visible to
        other views and can be queried, but the queries will return no rows"
        for roles other than ``ACCOUNTADMIN``. An empty result is therefore
        indistinguishable from a missing table, and the introspector method's
        docstring says so rather than reporting a spurious "not found".

        ``table_name`` and ``schema`` are bound values (``dialect.p()``), not
        identifiers: they are compared to catalog columns, not interpolated into
        an object name. Information Schema values are uppercase for unquoted
        objects (the Information Schema topic says so explicitly), so callers
        pass the catalog spelling.
        """
        metrics = self._information_schema_view("TABLE_STORAGE_METRICS", "m")
        tables = self._information_schema_view("TABLES", "t")
        conditions = [
            ComparisonPredicate(
                self,
                "eq",
                self._catalog_column("TABLE_NAME", "m"),
                Literal(self, expr.table_name),
            ),
            IsNullPredicate(self, self._catalog_column("TABLE_DROPPED", "m")),
        ]
        if expr.schema:
            conditions.append(
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_SCHEMA", "m"),
                    Literal(self, expr.schema),
                )
            )
        source = JoinClause(
            self,
            left_table=metrics,
            right_table=tables,
            join_type=JoinType.LEFT,
            condition=LogicalPredicate(
                self,
                "AND",
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_CATALOG", "t"),
                    self._catalog_column("TABLE_CATALOG", "m"),
                ),
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_SCHEMA", "t"),
                    self._catalog_column("TABLE_SCHEMA", "m"),
                ),
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("TABLE_NAME", "t"),
                    self._catalog_column("TABLE_NAME", "m"),
                ),
            ),
        )
        return self._catalog_query(
            [
                self._catalog_column("TABLE_CATALOG", "m"),
                self._catalog_column("TABLE_SCHEMA", "m"),
                self._catalog_column("TABLE_NAME", "m"),
                self._catalog_column("ID", "m"),
                self._catalog_column("CLONE_GROUP_ID", "m"),
                self._catalog_column("IS_TRANSIENT", "m"),
                self._catalog_column("ACTIVE_BYTES", "m"),
                self._catalog_column("TIME_TRAVEL_BYTES", "m"),
                self._catalog_column("FAILSAFE_BYTES", "m"),
                self._catalog_column("RETAINED_FOR_CLONE_BYTES", "m"),
                self._catalog_column("TABLE_CREATED", "m"),
                self._catalog_column("TABLE_DROPPED", "m"),
                self._catalog_column("TABLE_ENTERED_FAILSAFE", "m"),
                self._catalog_column("COMMENT", "m"),
                self._catalog_column("TABLE_TYPE", "t"),
                self._catalog_column("ROW_COUNT", "t"),
                self._catalog_column("CLUSTERING_KEY", "t"),
                self._catalog_column("AUTO_CLUSTERING_ON", "t"),
            ],
            source,
            conditions,
            # Newest version first, so the row a caller would want -- the one
            # this query filters for -- is the first one returned even if the
            # current-version filter is ever widened.
            [(self._catalog_column("TABLE_CREATED", "m"), "DESC")],
        )
