# src/rhosocial/activerecord/backend/impl/snowflake/mixins/introspection.py
"""SnowflakeIntrospectionMixin — schema introspection via INFORMATION_SCHEMA."""

from typing import TYPE_CHECKING, List, Optional, Tuple

from rhosocial.activerecord.backend.expression import (
    CaseExpression,
    Column,
    ComparisonPredicate,
    CountFunction,
    FunctionCall,
    GroupByHavingClause,
    InPredicate,
    IsNullPredicate,
    LikeOperator,
    LikePredicate,
    LimitOffsetClause,
    Literal,
    LogicalPredicate,
    OrderByClause,
    QueryStatement,
    RowCountWildcard,
    SelectModifier,
    Subquery,
    SumFunction,
    WhereClause,
)
from rhosocial.activerecord.backend.expression.core import CastExpression
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.query_parts import JoinClause, JoinType
from rhosocial.activerecord.backend.expression.sources.derived import DerivedTableSource
from rhosocial.activerecord.backend.expression.sources.relation import NamedRelationRef
from rhosocial.activerecord.backend.expression.types.string import VarCharType
from rhosocial.activerecord.backend.introspection.types import ProfileSource

from ..expression.introspection import (
    SnowflakeDatabaseListQueryStatement,
    SnowflakeFileFormatListQueryStatement,
    SnowflakeFunctionListQueryStatement,
    SnowflakePipeListQueryStatement,
    SnowflakeProcedureListQueryStatement,
    SnowflakeSchemaListQueryStatement,
    SnowflakeSequenceListQueryStatement,
    SnowflakeStageListQueryStatement,
    SnowflakeStreamListQueryStatement,
    SnowflakeTableStorageMetricsQueryStatement,
    SnowflakeTaskListQueryStatement,
    SnowflakeWarehouseListQueryStatement,
)
from ..expression.show import SnowflakeShowObjectType, SnowflakeShowStatement

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.introspection import (
        ColumnDataProfileQueryStatement,
        ColumnInfoQueryStatement,
        ColumnValueSampleQueryStatement,
        DatabaseInfoQueryStatement,
        ForeignKeyQueryStatement,
        IndexInfoQueryStatement,
        JoinCoverageQueryStatement,
        TableListQueryStatement,
        TriggerListQueryStatement,
        ViewInfoQueryStatement,
        ViewListQueryStatement,
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

    def supports_table_storage_metrics(self) -> bool:
        """Snowflake answers for one table's billed storage.

        The capability for the ``introspect table-storage-metrics`` family.
        The answer is a join of ``TABLE_STORAGE_METRICS`` with ``TABLES``,
        not a column of the ``tables`` listing, which is why it is a family
        of its own; see
        :meth:`format_table_storage_metrics_query_statement` for the columns
        and the ``ACCOUNTADMIN`` caveat that makes an absent row distinct
        from an absent table."""
        return True

    def supports_table_storage_introspection(self) -> bool:
        """The same billed storage answers the common minimum's total slot.

        The capability for the per-table storage family, which is what the
        ``table-storage-metrics`` family above feeds: the four tiers
        (active, time travel, failsafe, clone-retained) sum to a table's
        total footprint, and that sum lands on ``IntrospectionTableInfo``
        ``size_bytes`` for a single-table read -- see
        :meth:`~...introspection.introspector.SnowflakeIntrospector.get_table_info`.

        The listing deliberately stays unjoined, and the CLI README records
        why: the metrics statement joins two views, so folding it into
        ``list_tables`` would charge every list for the join, and the view
        answers only for ``ACCOUNTADMIN``, so a column there would read as
        "no storage" where the truth is "this role may not see it".

        The split slots stay ``None``: Snowflake's storage is managed
        micro-partition bytes with no index side to separate, so there is
        nothing to attribute ``data_size_bytes`` or ``index_size_bytes`` to
        -- the engine's shape, not a gap
        (``.claude/rules/introspection.md`` §5).
        """
        return True

    # ------------------------------------------------------------------
    # Schema-object families core does not model yet
    # ------------------------------------------------------------------
    # Core's ``IntrospectionSupport`` protocol names the families every
    # backend shares; routines and the Snowflake catalog objects below have
    # no core member, so these switches are declared here, beside the
    # formatters that answer for them. The CLI's ``_TYPE_CAPABILITIES``
    # names each switch, and the tests refuse a type whose switch the
    # dialect does not have -- so a family cannot be offered without a
    # documented answer behind it.

    def supports_routine_introspection(self) -> bool:
        """Snowflake answers for stored procedures and user-defined functions.

        The answer is a read of ``INFORMATION_SCHEMA.PROCEDURES`` and
        ``INFORMATION_SCHEMA.FUNCTIONS``, joined in the introspector into one
        ``routines`` family so a caller asking "what executes here" does not
        have to know which of the two objects it is asking about.
        """
        return True

    def supports_sequence_introspection(self) -> bool:
        """Snowflake answers for standalone sequences.

        ``INFORMATION_SCHEMA.SEQUENCES`` lists them with their type, start
        value, increment, next value and owner. This is not the identity
        family: a column declared ``AUTOINCREMENT`` is reported by
        ``COLUMNS.IS_IDENTITY``, while a standalone sequence is an object of
        its own and can also be used as a column default.
        """
        return True

    def supports_stage_introspection(self) -> bool:
        """Snowflake answers for named stages from ``INFORMATION_SCHEMA.STAGES``."""
        return True

    def supports_file_format_introspection(self) -> bool:
        """Snowflake answers for named file formats from ``INFORMATION_SCHEMA.FILE_FORMATS``."""
        return True

    def supports_pipe_introspection(self) -> bool:
        """Snowflake answers for pipes from ``INFORMATION_SCHEMA.PIPES``."""
        return True

    def supports_task_introspection(self) -> bool:
        """Snowflake answers for tasks, from ``SHOW TASKS``.

        No Information Schema view exists for tasks, so the documented route
        is the ``SHOW`` command. Its rows are lowercase and it accepts an
        ``IN SCHEMA`` scope, both of which the statement and parser handle.
        """
        return True

    def supports_stream_introspection(self) -> bool:
        """Snowflake answers for streams, from ``SHOW STREAMS``.

        As with tasks, there is no Information Schema view; ``SHOW STREAMS``
        is the documented route, scoped to the configured schema when one is
        known.
        """
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
            IntrospectionScope.SEQUENCE,
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
            statement.where = WhereClause(self, LogicalPredicate(self, "AND", *conditions))
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

    def _no_table_type_predicate(self) -> "ComparisonPredicate":
        """A comparison that cannot hold, for a kind the catalogue never names.

        A core ``TableType`` such as ``FOREIGN_TABLE`` or ``PARTITIONED_TABLE``
        has no Snowflake spelling.  Dropping the condition would answer with
        every table, which claims rows the catalogue never reported as that
        kind; the honest answer is "none" (``1 = 2``), the idiom the trigger
        formatter uses for a family this engine does not have.
        """
        return ComparisonPredicate(
            self,
            "eq",
            Literal(self, 1, inline=True),
            Literal(self, 2, inline=True),
        )

    def format_table_list_query_statement(
        self, expr: "TableListQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format table list query using INFORMATION_SCHEMA.TABLES.

        ``include_views=False`` removes the two view spellings and nothing
        else.  It used to require ``TABLE_TYPE = 'BASE TABLE'``, which also
        hid every other table kind the catalogue reports -- managed, event,
        Iceberg, hybrid and dynamic tables are tables, not views, and a
        "no views" listing must not answer as if they did not exist.

        An explicit ``table_type`` is read in both vocabularies: an exact
        catalogue spelling selects that spelling, a core ``TableType`` name
        expands onto the spellings mapped to it, and an unknown spelling is a
        catalogue value this backend has not learned yet.  See
        :func:`..introspection.table_types.catalogue_spellings`.
        """
        from ..introspection.table_types import (
            SNOWFLAKE_VIEW_TYPES,
            catalogue_spellings,
        )

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
                    Literal(self, ["information_schema", "PUBLIC"], inline=True),
                )
            )
        if not include_views:
            conditions.append(
                ~InPredicate(
                    self,
                    self._catalog_column("TABLE_TYPE"),
                    Literal(self, list(SNOWFLAKE_VIEW_TYPES), inline=True),
                )
            )
        if table_type:
            spellings = catalogue_spellings(table_type)
            if spellings:
                conditions.append(
                    InPredicate(
                        self,
                        self._catalog_column("TABLE_TYPE"),
                        Literal(self, list(spellings)),
                    )
                )
            else:
                conditions.append(self._no_table_type_predicate())

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
        """Format column information query using INFORMATION_SCHEMA.COLUMNS.

        The identity columns are selected because they answer a real question
        this backend reports on: whether a column's value is generated by the
        database. Snowflake documents ``IS_IDENTITY`` as "Whether this column
        is an identity column", ``IDENTITY_GENERATION`` as always ``BY DEFAULT``,
        ``IDENTITY_START``/``IDENTITY_INCREMENT`` as the declared numbers, and
        ``IDENTITY_ORDERED`` as the sequence-order property. ``KIND`` and
        ``EXPRESSION`` describe a virtual column, which is a generated column
        in this engine's vocabulary.
        https://docs.snowflake.com/en/sql-reference/info-schema/columns
        """
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
                self._catalog_column("DATA_TYPE_ALIAS"),
                self._catalog_column("CHARACTER_MAXIMUM_LENGTH"),
                self._catalog_column("NUMERIC_PRECISION"),
                self._catalog_column("NUMERIC_SCALE"),
                self._catalog_column("COLLATION_NAME"),
                self._catalog_column("COMMENT"),
                self._catalog_column("IS_IDENTITY"),
                self._catalog_column("IDENTITY_GENERATION"),
                self._catalog_column("IDENTITY_START"),
                self._catalog_column("IDENTITY_INCREMENT"),
                self._catalog_column("IDENTITY_ORDERED"),
                self._catalog_column("KIND"),
                self._catalog_column("EXPRESSION"),
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
                    Literal(self, ["PRIMARY KEY", "UNIQUE"], inline=True),
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
        source = (
            JoinClause(
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
            )
            .join(
                right_table=self._information_schema_view("TABLE_CONSTRAINTS", "utc"),
                join_type="JOIN",
                condition=LogicalPredicate(
                    self,
                    "AND",
                    _same("UNIQUE_CONSTRAINT_NAME", "CONSTRAINT_NAME", "rc", "utc"),
                    _same("UNIQUE_CONSTRAINT_SCHEMA", "CONSTRAINT_SCHEMA", "rc", "utc"),
                ),
            )
            .join(
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
        )
        return self._catalog_query(
            [
                self._catalog_column("CONSTRAINT_NAME", "rc"),
                self._catalog_column("UPDATE_RULE", "rc"),
                self._catalog_column("DELETE_RULE", "rc"),
                self._catalog_column("COLUMN_NAME", "kcu"),
                self._catalog_column("ORDINAL_POSITION", "kcu"),
                self._catalog_column("TABLE_NAME", "utc", alias="REFERENCED_TABLE_NAME"),
                self._catalog_column("COLUMN_NAME", "ukcu", alias="REFERENCED_COLUMN_NAME"),
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

    def format_view_list_query_statement(self, expr: "ViewListQueryStatement") -> Tuple[str, tuple]:
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

    def format_view_info_query_statement(self, expr: "ViewInfoQueryStatement") -> Tuple[str, tuple]:
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

    def format_trigger_info_query_statement(self, expr) -> Tuple[str, tuple]:
        """Snowflake does not support triggers; return empty result."""
        return self.format_trigger_list_query_statement(expr)

    # ========== Data profiles: the rows, because no catalogue holds them ==========

    def supports_column_data_profile(self) -> bool:
        """Snowflake answers a column profile by aggregating the rows.

        Nothing in the account keeps a per-column distribution to read.
        ``INFORMATION_SCHEMA.COLUMNS`` describes what a column *declares* --
        type, nullability, default, comment -- and ``ACCOUNT_USAGE`` describes
        objects and how often they were used, not what they hold. There is no
        ``pg_stats`` here and no equivalent: Snowflake's micro-partition
        metadata records value ranges for pruning, and those ranges are
        published nowhere a session can query. So the answer is computed from
        the rows, exact, and paid for in time -- one arm per column, each a scan
        of the table.

        ``COUNT(DISTINCT ...)`` rather than ``APPROX_COUNT_DISTINCT``, and the
        reason is provenance rather than speed. The approximation is cheaper and
        is the right tool for a cardinality *estimate*, but this family has no
        word for what it produces: an ``aggregate`` says every row was counted
        and the answer is exact, a ``sample`` says a subset of rows was read and
        ``row_count`` says how many, and a HyperLogLog estimate over the whole
        table is neither. Labelling it ``aggregate`` would be a false claim
        about precision, and labelling it ``sample`` would be a false claim
        about which rows were read. The exactness also carries a signal an
        estimate would destroy: ``distinct_count == row_count`` is how a caller
        recognises a unique column, and that comparison has no tolerance. A
        table big enough for the exact count to hurt is one whose owner should
        decide to pay for it, which is why this is a probe and not a pass.
        """
        return True

    def supports_column_value_sample(self) -> bool:
        """Snowflake answers a value listing with a grouped scan and a limit.

        Nothing is precomputed, so this costs a ``GROUP BY`` over the column
        plus a sort of the groups. Kept a separate probe from the profile for
        the reason the protocol gives: the listing is priced differently on
        every engine, and one probe for both would charge the cheap question at
        the expensive answer's rate.
        """
        return True

    def supports_join_coverage(self) -> bool:
        """Snowflake answers overlap by counting distinct values on both sides.

        Exact, and paid for with a scan of each column twice: once for the
        intersection, once for the denominator. Answering ``True`` says the
        engine *can* answer, not that it answers cheaply -- the cost belongs in
        this docstring, not in a ``False`` that would claim Snowflake cannot
        read its own rows. Nulls are excluded on both sides; collations are the
        columns' own, so two columns comparing differently make the fractions a
        lower bound.
        """
        return True

    def _user_relation(
        self, table_name: str, alias: Optional[str] = None, schema: Optional[str] = None
    ) -> NamedRelationRef:
        """A user table as a ``FROM`` source, quoted by the dialect.

        The opposite of :meth:`_information_schema_view`: a user table is
        whatever its owner declared, so name and schema are left to the
        dialect's identifier renderer. Quoting is case-sensitive in Snowflake,
        which is why the name must arrive in the catalogue's own spelling --
        the column list a profile is built from comes from
        ``INFORMATION_SCHEMA``, so it does.
        """
        return NamedRelationRef(
            self,
            Table(self, table_name, schema_name=schema or None),
            alias=alias,
        )

    def _profile_label(self, text: Optional[str], alias: str) -> CastExpression:
        """A constant label as a named select-list entry.

        ``Literal`` is deliberately unaliasable -- a value has nothing to name
        -- so the constant is cast to text, which is the smallest node that
        produces a named result. The cast is not there for its type: it is
        there so the label can be called ``COLUMN_NAME`` or ``SOURCE``, which
        is what the parser reads. ``None`` is the same node carrying SQL NULL,
        which is how the empty profile says "the column name is absent" without
        inventing one.

        The cast target is ``VARCHAR`` at the dialect's own maximum width
        (16,777,216) because a label has no width to declare, and any narrower
        choice would silently truncate the name it carries.
        """
        return CastExpression(
            self, Literal(self, text, inline=True), VarCharType(self), alias=alias
        )

    def _profile_arm(self, table_name: str, schema: Optional[str], column_name: str):
        """One column's arm of the profile, as a node.

        The seven entries are the family's contract: the column's own name, the
        null count, the distinct count, the two endpoints, the row count the
        parser divides by, and the provenance. The null count is a ``SUM`` over
        a ``CASE`` so an empty table answers NULL rather than a fabricated zero
        (``SUM`` over no rows is NULL in Snowflake, which is what this relies
        on); the distinct count is the exact ``COUNT(DISTINCT ...)``, for the
        reason the probe records; the endpoints are the engine's own
        ``MIN``/``MAX``; and ``COUNT(*)`` rides the same scan as the divisor.

        Empty is answered by the caller, not here: an arm over no columns does
        not exist.
        """
        return QueryStatement(
            self,
            select=[
                self._profile_label(column_name, "COLUMN_NAME"),
                SumFunction(
                    self,
                    CaseExpression(
                        self,
                        cases=[
                            (
                                IsNullPredicate(self, Column(self, column_name)),
                                Literal(self, 1, inline=True),
                            )
                        ],
                        else_result=Literal(self, 0, inline=True),
                    ),
                ).as_("NULL_COUNT"),
                CountFunction(self, Column(self, column_name), distinct=True).as_("DISTINCT_COUNT"),
                FunctionCall(self, "MIN", Column(self, column_name)).as_("MIN_VALUE"),
                FunctionCall(self, "MAX", Column(self, column_name)).as_("MAX_VALUE"),
                CountFunction(self, RowCountWildcard(self)).as_("ROW_COUNT"),
                self._profile_label(ProfileSource.AGGREGATE.value, "SOURCE"),
            ],
            from_=self._user_relation(table_name, schema=schema),
        )

    def format_column_data_profile_query_statement(
        self, expr: "ColumnDataProfileQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format a per-column profile by aggregating the rows themselves.

        One arm per column, over the column list the expression carries: SQL
        cannot pivot ``SUM(CASE WHEN col IS NULL ...)`` across columns it was
        never told about, so an aggregating backend genuinely needs that list
        where a catalogue-based one does not.

        The one place in this module where a set operator is written as text.
        Every arm is a real :class:`~...statements.dql.QueryStatement` -- it
        owns its projection, its identifiers and its relation -- because a
        ``UNION ALL`` over a column list known only at run time has no node to
        represent it: the list is a tuple on the expression, not an operand in
        the tree. So each arm renders on its own, its parameters are
        concatenated in arm order, and the rendered arms are joined by the set
        operator's word.

        An empty column list answers with no rows. That cannot arise from a real
        table -- Snowflake requires at least one column -- but the branch has to
        render, so it is a statement selecting no rows rather than a
        special-case string.

        Two consequences of the union are worth reading before the figures are.
        Snowflake resolves one result type per column position across every arm,
        so ``MIN_VALUE`` -- which carries ``code``'s text in one arm and
        ``amount``'s number in another -- may arrive coerced to text, and the
        test reads the numeric endpoints through ``Decimal`` for that reason.
        And a column type ``MIN``/``MAX``/``COUNT(DISTINCT ...)`` refuse --
        ``VARIANT``, ``OBJECT``, ``ARRAY`` -- fails the whole statement rather
        than dropping that column's arm: a silently missing column would be a
        profile that claims a table has fewer columns than it does.
        """
        params = expr.get_params()
        schema = params.get("schema")

        arms = []
        parameters: list = []
        for name in expr.columns:
            sql, arm_parameters = self._profile_arm(params.get("table_name"), schema, name).to_sql()
            arms.append(sql)
            parameters.extend(arm_parameters)

        if not arms:
            return QueryStatement(
                self,
                select=[self._profile_label(None, "COLUMN_NAME")],
                where=WhereClause(
                    self,
                    ComparisonPredicate(
                        self,
                        "eq",
                        Literal(self, 0, inline=True),
                        Literal(self, 1, inline=True),
                    ),
                ),
            ).to_sql()

        return " UNION ALL ".join(arms), tuple(parameters)

    def format_column_value_sample_query_statement(
        self, expr: "ColumnValueSampleQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format a most-frequent-values listing with a grouped scan.

        Nothing is precomputed, so this costs a ``GROUP BY`` over the column
        plus a sort of the groups -- the same order as the profile, which is why
        the two are separate probes rather than one call that would make the
        cheap half pay for the dear one.

        ``ORDER BY COUNT(*) DESC`` is what makes the answer "the most frequent
        values" rather than "the first values"; ties break by the value so two
        runs of the same query agree. Snowflake groups NULLs into a real row, so
        a column holding NULLs has a NULL entry in its listing -- usually the
        most frequent one -- which is a shape the parser accepts and the test
        pins, rather than a value this formatter filters out.

        The ``LIMIT`` is a bind parameter, as it is everywhere else in this
        dialect: the caller's integer is never spliced into statement text.
        """
        column = Column(self, expr.column_name)
        rows = CountFunction(self, RowCountWildcard(self))

        return QueryStatement(
            self,
            select=[column.as_("VALUE"), rows.as_("COUNT")],
            from_=self._user_relation(expr.table_name, schema=expr.schema),
            group_by_having=GroupByHavingClause(self, group_by=[column]),
            order_by=OrderByClause(
                self,
                expressions=[
                    (CountFunction(self, RowCountWildcard(self)), "DESC"),
                    (Column(self, expr.column_name), "ASC"),
                ],
            ),
            limit_offset=LimitOffsetClause(self, limit=int(expr.limit)),
        ).to_sql()

    def _coverage_fraction(self, column, source, other_column, other_source):
        """One side of the overlap: the share of *column* the other side holds.

        The numerator counts the *distinct* values of *column* that also occur
        in *other_column*, as a ``COUNT(*)`` over a derived table of those
        distinct values; the denominator counts *column*'s distinct non-NULL
        values. Distinct on both sides is what makes the figure a coverage of
        values rather than of rows -- a key repeated a thousand times that
        matches once would otherwise read as well covered.

        ``IS NOT NULL`` is written on both halves rather than relied upon. In
        the numerator it is load-bearing: a DISTINCT treats a NULL as one
        value, so counting it would credit the tested side with a match it does
        not have. In the divisor ``COUNT(DISTINCT ...)`` skips NULLs on its
        own, but the statement says so explicitly, because the share is of the
        values that could join and that is the fact being measured.
        ``NULLIF(..., 0)`` then makes a column with no value at all answer NULL
        rather than 0, which the parser reads as "no fraction": the difference
        between "nothing matched" and "nothing to match" survives to the caller.

        No ``* 1.0`` here: Snowflake's ``/`` over two integers already answers a
        fractional ``NUMBER``, so multiplying first would only add noise.
        """
        overlap = QueryStatement(
            self,
            select=[column],
            from_=source,
            where=WhereClause(
                self,
                LogicalPredicate(
                    self,
                    "AND",
                    column.is_not_null(),
                    InPredicate(
                        self,
                        column,
                        Subquery(
                            self,
                            QueryStatement(
                                self,
                                select=[other_column],
                                from_=other_source,
                                where=WhereClause(self, other_column.is_not_null()),
                            ),
                        ),
                    ),
                ),
            ),
            select_modifier=SelectModifier.DISTINCT,
        )
        covered = Subquery(
            self,
            QueryStatement(
                self,
                select=[CountFunction(self, RowCountWildcard(self))],
                from_=DerivedTableSource(self, overlap, alias="covered"),
            ),
        )
        total = Subquery(
            self,
            QueryStatement(
                self,
                select=[
                    FunctionCall(
                        self,
                        "NULLIF",
                        CountFunction(self, column, distinct=True),
                        Literal(self, 0, inline=True),
                    )
                ],
                from_=source,
                where=WhereClause(self, column.is_not_null()),
            ),
        )
        return covered / total

    def format_join_coverage_query_statement(
        self, expr: "JoinCoverageQueryStatement"
    ) -> Tuple[str, tuple]:
        """Format a two-sided measurement of two columns' value domains.

        Unlike every other statement in this module, this one names two user
        tables rather than one catalogue relation: the question is a relation
        between two objects, so both sides are carried explicitly and their
        identifiers are the dialect's to quote (see :meth:`_user_relation`).
        The aliases ``l`` and ``r`` are what keep the two columns apart.

        The row carries both fractions because neither is meaningful alone: a
        left share of 1.0 beside a right share of 0.2 says every tested value
        exists on the other side while most of that other domain is
        unaccounted for, and a single similarity score would average the two
        and describe neither.

        Both figures are counted over distinct values with NULLs excluded from
        the numerators and denominators alike -- a NULL is not a value that
        could ever join -- and the denominators are ``NULLIF``-guarded so a
        column with nothing to match answers NULL, which the parser reports as
        "no measurement" instead of a zero overlap that would read as a real
        answer.

        The cost is each side read for its distinct domain plus the
        intersection of the two, which is why the probe is an explicit call and
        belongs in no automatic pass. Collations are not reconciled: the two
        columns compare under their own, so the fractions are a lower bound
        across mismatched ones.
        """
        params = expr.get_params()
        schema = params.get("schema")

        left_source = self._user_relation(params.get("left_table"), "l", schema)
        right_source = self._user_relation(params.get("right_table"), "r", schema)
        left_column = Column(self, params.get("left_column"), table="l")
        right_column = Column(self, params.get("right_column"), table="r")

        return QueryStatement(
            self,
            select=[
                self._coverage_fraction(left_column, left_source, right_column, right_source).as_(
                    "LEFT_COVERAGE"
                ),
                self._coverage_fraction(right_column, right_source, left_column, left_source).as_(
                    "RIGHT_COVERAGE"
                ),
            ],
        ).to_sql()

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
            self._information_schema_view("SCHEMATA", catalog=expr.database or None),
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
        return SnowflakeShowStatement(self, SnowflakeShowObjectType.WAREHOUSES).to_sql()

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

    # ------------------------------------------------------------------ #
    # Routines, sequences and Snowflake's own catalog objects
    #
    # Each formatter below selects the columns documented on the linked page
    # and filters on the schema the caller configured. The schema is a bind
    # value, not an identifier: it is compared to a catalog column, and an
    # unquoted object is stored uppercase, so a caller passes the catalog's
    # spelling. None of these statements selects ``*``: the Snowflake
    # Information Schema topic asks readers not to ("The Snowflake-specific
    # views are subject to change... select the columns that you want").
    # ------------------------------------------------------------------ #

    def format_function_list_query_statement(
        self, expr: SnowflakeFunctionListQueryStatement
    ) -> Tuple[str, tuple]:
        """``INFORMATION_SCHEMA.FUNCTIONS``, one row per user-defined function.

        Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/functions

        The view lists UDFs, external functions and data metric functions -- it
        does **not** list Snowflake's built-in system functions, which are not
        schema objects with an owner or a comment. The columns selected are the
        documented ones that answer the routine family's stable shape plus the
        engine-specific remainder stored in ``extra``:

        * ``FUNCTION_NAME``, ``FUNCTION_SCHEMA``, ``FUNCTION_CATALOG`` --
          identity and place.
        * ``FUNCTION_OWNER``, ``OWNER_ROLE_TYPE`` -- ownership.
        * ``ARGUMENT_SIGNATURE`` -- the view's own signature, which is how
          overloads are distinguished.
        * ``DATA_TYPE`` -- the return type.
        * ``FUNCTION_LANGUAGE``, ``RUNTIME_VERSION``, ``HANDLER`` --
          what runs the body.
        * ``VOLATILITY``, ``IS_NULL_CALL``, ``IS_SECURE``, ``IS_MEMOIZABLE``,
          ``IS_EXTERNAL``, ``IS_DATA_METRIC``, ``IS_AGGREGATE`` -- declared
          behaviour.
        * ``PACKAGES``, ``INSTALLED_PACKAGES``, ``ARTIFACT_REPOSITORY``,
          ``EXTERNAL_ACCESS_INTEGRATIONS``, ``SECRETS`` -- runtime
          dependencies.
        * ``CREATED``, ``LAST_ALTERED``, ``COMMENT``, ``FUNCTION_DEFINITION``.

        The view is a database-level one, so the filter is on
        ``FUNCTION_SCHEMA``; ``ORDER BY FUNCTION_NAME, ARGUMENT_SIGNATURE``
        makes overloads deterministic.
        """
        return self._catalog_query(
            [
                self._catalog_column("FUNCTION_CATALOG"),
                self._catalog_column("FUNCTION_SCHEMA"),
                self._catalog_column("FUNCTION_NAME"),
                self._catalog_column("FUNCTION_OWNER"),
                self._catalog_column("ARGUMENT_SIGNATURE"),
                self._catalog_column("DATA_TYPE"),
                self._catalog_column("CHARACTER_MAXIMUM_LENGTH"),
                self._catalog_column("CHARACTER_OCTET_LENGTH"),
                self._catalog_column("NUMERIC_PRECISION"),
                self._catalog_column("NUMERIC_PRECISION_RADIX"),
                self._catalog_column("NUMERIC_SCALE"),
                self._catalog_column("FUNCTION_LANGUAGE"),
                self._catalog_column("FUNCTION_DEFINITION"),
                self._catalog_column("VOLATILITY"),
                self._catalog_column("IS_NULL_CALL"),
                self._catalog_column("IS_SECURE"),
                self._catalog_column("IS_MEMOIZABLE"),
                self._catalog_column("IS_EXTERNAL"),
                self._catalog_column("IS_DATA_METRIC"),
                self._catalog_column("IS_AGGREGATE"),
                self._catalog_column("RUNTIME_VERSION"),
                self._catalog_column("HANDLER"),
                self._catalog_column("PACKAGES"),
                self._catalog_column("INSTALLED_PACKAGES"),
                self._catalog_column("ARTIFACT_REPOSITORY"),
                self._catalog_column("EXTERNAL_ACCESS_INTEGRATIONS"),
                self._catalog_column("SECRETS"),
                self._catalog_column("CREATED"),
                self._catalog_column("LAST_ALTERED"),
                self._catalog_column("COMMENT"),
                self._catalog_column("OWNER_ROLE_TYPE"),
            ],
            self._information_schema_view("FUNCTIONS"),
            [
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("FUNCTION_SCHEMA"),
                    Literal(self, expr.schema or ""),
                )
            ],
            [
                self._catalog_column("FUNCTION_NAME"),
                self._catalog_column("ARGUMENT_SIGNATURE"),
            ],
        )

    def format_procedure_list_query_statement(
        self, expr: SnowflakeProcedureListQueryStatement
    ) -> Tuple[str, tuple]:
        """``INFORMATION_SCHEMA.PROCEDURES``, one row per stored procedure.

        Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/procedures

        The procedure view differs from the function view in its column prefix
        and in the runtime facts it documents: ``PROCEDURES`` has no
        ``VOLATILITY``, ``IS_MEMOIZABLE``, ``IS_AGGREGATE`` or ``HANDLER``
        column, and it adds ``EXTERNAL_ACCESS_INTEGRATIONS``, ``SECRETS``,
        ``RUNTIME_VERSION``, ``PACKAGES``, ``INSTALLED_PACKAGES`` and
        ``ARTIFACT_REPOSITORY``. Selecting the union of both views would
        claim columns the view does not have, so each formatter names its
        own page's columns.
        """
        return self._catalog_query(
            [
                self._catalog_column("PROCEDURE_CATALOG"),
                self._catalog_column("PROCEDURE_SCHEMA"),
                self._catalog_column("PROCEDURE_NAME"),
                self._catalog_column("PROCEDURE_OWNER"),
                self._catalog_column("ARGUMENT_SIGNATURE"),
                self._catalog_column("DATA_TYPE"),
                self._catalog_column("CHARACTER_MAXIMUM_LENGTH"),
                self._catalog_column("CHARACTER_OCTET_LENGTH"),
                self._catalog_column("NUMERIC_PRECISION"),
                self._catalog_column("NUMERIC_PRECISION_RADIX"),
                self._catalog_column("NUMERIC_SCALE"),
                self._catalog_column("PROCEDURE_LANGUAGE"),
                self._catalog_column("PROCEDURE_DEFINITION"),
                self._catalog_column("RUNTIME_VERSION"),
                self._catalog_column("PACKAGES"),
                self._catalog_column("INSTALLED_PACKAGES"),
                self._catalog_column("ARTIFACT_REPOSITORY"),
                self._catalog_column("EXTERNAL_ACCESS_INTEGRATIONS"),
                self._catalog_column("SECRETS"),
                self._catalog_column("CREATED"),
                self._catalog_column("LAST_ALTERED"),
                self._catalog_column("COMMENT"),
                self._catalog_column("OWNER_ROLE_TYPE"),
            ],
            self._information_schema_view("PROCEDURES"),
            [
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("PROCEDURE_SCHEMA"),
                    Literal(self, expr.schema or ""),
                )
            ],
            [
                self._catalog_column("PROCEDURE_NAME"),
                self._catalog_column("ARGUMENT_SIGNATURE"),
            ],
        )

    def format_sequence_list_query_statement(
        self, expr: SnowflakeSequenceListQueryStatement
    ) -> Tuple[str, tuple]:
        """``INFORMATION_SCHEMA.SEQUENCES``, one row per standalone sequence.

        Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/sequences

        ``MINIMUM_VALUE``, ``MAXIMUM_VALUE`` and ``CYCLE_OPTION`` are documented
        "Not applicable for Snowflake", and ``START_VALUE`` / ``INCREMENT`` /
        ``NEXT_VALUE`` are ``VARCHAR`` rather than numbers. The parser reads
        those three as absent and converts the string-valued numbers; the
        projection keeps what the catalog reports rather than substituting
        invented limits.

        The view has no "last value produced" column: ``NEXT_VALUE`` is the
        value the sequence will produce next, which is a different fact and
        is stored under that name in ``extra`` instead of being mislabelled
        ``last_value``.
        """
        return self._catalog_query(
            [
                self._catalog_column("SEQUENCE_CATALOG"),
                self._catalog_column("SEQUENCE_SCHEMA"),
                self._catalog_column("SEQUENCE_NAME"),
                self._catalog_column("SEQUENCE_OWNER"),
                self._catalog_column("DATA_TYPE"),
                self._catalog_column("NUMERIC_PRECISION"),
                self._catalog_column("NUMERIC_PRECISION_RADIX"),
                self._catalog_column("NUMERIC_SCALE"),
                self._catalog_column("START_VALUE"),
                self._catalog_column("MINIMUM_VALUE"),
                self._catalog_column("MAXIMUM_VALUE"),
                self._catalog_column("NEXT_VALUE"),
                self._catalog_column("INCREMENT"),
                self._catalog_column("CYCLE_OPTION"),
                self._catalog_column("CREATED"),
                self._catalog_column("LAST_ALTERED"),
                self._catalog_column("ORDERED"),
                self._catalog_column("COMMENT"),
            ],
            self._information_schema_view("SEQUENCES"),
            [
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("SEQUENCE_SCHEMA"),
                    Literal(self, expr.schema or ""),
                )
            ],
            [self._catalog_column("SEQUENCE_NAME")],
        )

    def format_stage_list_query_statement(
        self, expr: SnowflakeStageListQueryStatement
    ) -> Tuple[str, tuple]:
        """``INFORMATION_SCHEMA.STAGES``, one row per named stage.

        Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/stages

        Only named stages appear in this view; the user stage ``~`` and table
        stages are addressed by their table and are not objects with an owner
        or a catalog row.
        """
        return self._catalog_query(
            [
                self._catalog_column("STAGE_CATALOG"),
                self._catalog_column("STAGE_SCHEMA"),
                self._catalog_column("STAGE_NAME"),
                self._catalog_column("STAGE_URL"),
                self._catalog_column("STAGE_REGION"),
                self._catalog_column("STAGE_TYPE"),
                self._catalog_column("STAGE_OWNER"),
                self._catalog_column("COMMENT"),
                self._catalog_column("CREATED"),
                self._catalog_column("LAST_ALTERED"),
            ],
            self._information_schema_view("STAGES"),
            [
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("STAGE_SCHEMA"),
                    Literal(self, expr.schema or ""),
                )
            ],
            [self._catalog_column("STAGE_NAME")],
        )

    def format_file_format_list_query_statement(
        self, expr: SnowflakeFileFormatListQueryStatement
    ) -> Tuple[str, tuple]:
        """``INFORMATION_SCHEMA.FILE_FORMATS``, one row per named file format.

        Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/file_formats

        The view documents the delimiter, encoding and compression options
        explicitly, so all of them are selected: they are the facts a caller
        asking "what does this format declare" wants. The two boolean
        spellings in this view are catalog text (``TRUE``/``FALSE`` and
        ``YES``/``NO`` depending on the column), so the parser reads them
        through the shared flag reader rather than assuming one spelling.
        """
        return self._catalog_query(
            [
                self._catalog_column("FILE_FORMAT_CATALOG"),
                self._catalog_column("FILE_FORMAT_SCHEMA"),
                self._catalog_column("FILE_FORMAT_NAME"),
                self._catalog_column("FILE_FORMAT_OWNER"),
                self._catalog_column("FILE_FORMAT_TYPE"),
                self._catalog_column("RECORD_DELIMITER"),
                self._catalog_column("FIELD_DELIMITER"),
                self._catalog_column("SKIP_HEADER"),
                self._catalog_column("DATE_FORMAT"),
                self._catalog_column("TIME_FORMAT"),
                self._catalog_column("TIMESTAMP_FORMAT"),
                self._catalog_column("BINARY_FORMAT"),
                self._catalog_column("ESCAPE"),
                self._catalog_column("ESCAPE_UNENCLOSED_FIELD"),
                self._catalog_column("TRIM_SPACE"),
                self._catalog_column("FIELD_OPTIONALLY_ENCLOSED_BY"),
                self._catalog_column("NULL_IF"),
                self._catalog_column("COMPRESSION"),
                self._catalog_column("ERROR_ON_COLUMN_COUNT_MISMATCH"),
                self._catalog_column("CREATED"),
                self._catalog_column("LAST_ALTERED"),
                self._catalog_column("COMMENT"),
            ],
            self._information_schema_view("FILE_FORMATS"),
            [
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("FILE_FORMAT_SCHEMA"),
                    Literal(self, expr.schema or ""),
                )
            ],
            [self._catalog_column("FILE_FORMAT_NAME")],
        )

    def format_pipe_list_query_statement(
        self, expr: SnowflakePipeListQueryStatement
    ) -> Tuple[str, tuple]:
        """``INFORMATION_SCHEMA.PIPES``, one row per pipe.

        Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/pipes

        The view's ``DEFINITION`` is the COPY statement the pipe runs, not
        DDL; ``PATTERN`` is the copy option from that statement. Current
        pipe status is deliberately not a column here: the page points at
        ``SYSTEM$PIPE_STATUS`` for it, and a pipe that has never run would
        otherwise read as a pipe that is stopped.
        """
        return self._catalog_query(
            [
                self._catalog_column("PIPE_CATALOG"),
                self._catalog_column("PIPE_SCHEMA"),
                self._catalog_column("PIPE_NAME"),
                self._catalog_column("PIPE_OWNER"),
                self._catalog_column("DEFINITION"),
                self._catalog_column("IS_AUTOINGEST_ENABLED"),
                self._catalog_column("NOTIFICATION_CHANNEL_NAME"),
                self._catalog_column("CREATED"),
                self._catalog_column("LAST_ALTERED"),
                self._catalog_column("COMMENT"),
                self._catalog_column("PATTERN"),
            ],
            self._information_schema_view("PIPES"),
            [
                ComparisonPredicate(
                    self,
                    "eq",
                    self._catalog_column("PIPE_SCHEMA"),
                    Literal(self, expr.schema or ""),
                )
            ],
            [self._catalog_column("PIPE_NAME")],
        )

    def format_task_list_query_statement(
        self, expr: SnowflakeTaskListQueryStatement
    ) -> Tuple[str, tuple]:
        """``SHOW TASKS``, scoped to the configured schema when there is one.

        Documentation: https://docs.snowflake.com/en/sql-reference/sql/show-tasks

        The Information Schema view index lists no ``TASKS`` view, so this is
        the documented route. The ``SHOW`` statement renders the scope through
        :class:`~...expression.show.SnowflakeShowStatement`; with no
        configured schema it emits the bare command, whose documented default
        is the current database. With a schema it emits ``IN SCHEMA`` so the
        listing matches the schema the other families read.

        The rows are documented lowercase and the `SHOW` output is
        privilege-filtered, both of which are recorded where the parser reads
        the rows.
        """
        from ..expression.show import SnowflakeShowObjectType, SnowflakeShowScope

        return SnowflakeShowStatement(
            self,
            SnowflakeShowObjectType.TASKS,
            in_scope=SnowflakeShowScope.SCHEMA if expr.schema else None,
            in_name=expr.schema or None,
        ).to_sql()

    def format_stream_list_query_statement(
        self, expr: SnowflakeStreamListQueryStatement
    ) -> Tuple[str, tuple]:
        """``SHOW STREAMS``, scoped to the configured schema when there is one.

        Documentation: https://docs.snowflake.com/en/sql-reference/sql/show-streams

        Same route and scope rule as :meth:`format_task_list_query_statement`
        and for the same reason: no Information Schema view exists. The rows
        are lowercase, and ``STALE`` / ``STALE_AFTER`` are the columns a caller
        watches to know whether the stream can still be read.
        """
        from ..expression.show import SnowflakeShowObjectType, SnowflakeShowScope

        return SnowflakeShowStatement(
            self,
            SnowflakeShowObjectType.STREAMS,
            in_scope=SnowflakeShowScope.SCHEMA if expr.schema else None,
            in_name=expr.schema or None,
        ).to_sql()
