# src/rhosocial/activerecord/backend/impl/snowflake/expression/introspection.py
"""Account-object introspection statements for Snowflake.

Six statements live here, one per question this backend asks the catalog that
core's introspection expressions do not model:

* :class:`SnowflakeDatabaseListQueryStatement` -- which databases exist.
* :class:`SnowflakeSchemaListQueryStatement` -- which schemas a database holds.
* :class:`SnowflakeWarehouseListQueryStatement` -- which warehouses the role can
  see.
* :class:`SnowflakeTableStorageMetricsQueryStatement` -- what one table is
  billed for storage.
* :class:`SnowflakeTableStateQueryStatement` -- one table's kind, clustering
  and comment, as the neutral ``TableState`` wants them.
* :class:`SnowflakeObjectExistsQueryStatement` -- whether one named object of
  a :class:`~rhosocial.activerecord.backend.introspection.types.ItemKind`
  exists.

They are expressions, which is the point: each one is a *statement node* whose
``to_sql()`` renders through
:class:`~...mixins.introspection.SnowflakeIntrospectionMixin` like every other
node in the tree, so the SQL is assembled from ``Column`` /
``ComparisonPredicate`` / ``Literal`` / ``QueryStatement`` objects by the
dialect rather than written out as text in a builder function. What a query asks
is therefore a structure the rest of the framework can inspect, and the one
place that knows how Snowflake spells it is the dialect.

Why they are this backend's statements and not core's
=====================================================

Core's introspection expressions answer for the questions core models: which
tables, which columns, which views, which indexes. It has no expression for a
warehouse (no engine-neutral meaning: not every dialect has compute objects),
and none for the per-table storage breakdown, which is a Snowflake-specific
billing model rather than a catalog concept. Extending core to carry both would
put one backend's account model into every backend's surface, so the statements
are declared here and rendered by this backend's mixin -- the same arrangement
the ``SHOW`` and time-travel expressions use.

Documentation. **None of these statements was executed against a Snowflake
account** -- this repository has none, and no test here pretends otherwise. The
column lists and value domains were written from the pages linked on each class
and in the mixin's formatters; the tests pin the rendered statement text and the
row parsing, never an account's answer.
"""

from typing import Optional

from rhosocial.activerecord.backend.expression.introspection import (
    IntrospectionExpression,
)
from rhosocial.activerecord.backend.introspection.types import ItemKind

from .coercion import as_member

__all__ = [
    "SnowflakeDatabaseListQueryStatement",
    "SnowflakeFileFormatListQueryStatement",
    "SnowflakeFunctionListQueryStatement",
    "SnowflakeObjectExistsQueryStatement",
    "SnowflakePipeListQueryStatement",
    "SnowflakeProcedureListQueryStatement",
    "SnowflakeSchemaListQueryStatement",
    "SnowflakeSequenceListQueryStatement",
    "SnowflakeStageListQueryStatement",
    "SnowflakeStreamListQueryStatement",
    "SnowflakeTableStateQueryStatement",
    "SnowflakeTableStorageMetricsQueryStatement",
    "SnowflakeTaskListQueryStatement",
    "SnowflakeWarehouseListQueryStatement",
]


class SnowflakeDatabaseListQueryStatement(IntrospectionExpression):
    """``SELECT`` over ``INFORMATION_SCHEMA.DATABASES``.

    Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/databases

    The view "displays a row for each database defined in your account" and
    "contains all of the databases in the account (regardless of the database's
    INFORMATION_SCHEMA used to query the view)". It is therefore the answer to
    "which databases exist here", which
    :class:`~rhosocial.activerecord.backend.expression.introspection.DatabaseInfoQueryStatement`
    is not: that one answers "which database am I connected to".

    Args:
        dialect: The dialect that renders this statement.
        schema: Unused -- the view is account-level and takes no schema
            filter. Present because every introspection expression carries one,
            and a caller building these generically passes a schema without
            knowing which statements read it.

    Example:
        >>> expr = SnowflakeDatabaseListQueryStatement(dialect)
        >>> sql, params = expr.to_sql()
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_database_list_query_statement"


class SnowflakeSchemaListQueryStatement(IntrospectionExpression):
    """``SELECT`` over one database's ``INFORMATION_SCHEMA.SCHEMATA``.

    Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/schemata

    The view "displays a row for each schema in the specified (or current)
    database", so it is a **database-level** view: another database is reached
    by qualifying the view with it, and ``database=None`` is a real request for
    "the database this session is in" rather than a missing argument.

    Args:
        dialect: The dialect that renders this statement.
        schema: Unused, as on the other list statement; the database is the
            container being enumerated here.
        database: The database whose schemas to list, or ``None`` for the
            session's current one. Rendered as an identifier -- it is part of
            the view's name, not a value compared to a column -- and quoted, so
            a database created with a case-sensitive name is reachable.

    Example:
        >>> expr = SnowflakeSchemaListQueryStatement(dialect, database="ANALYTICS")
        >>> sql, params = expr.to_sql()
    """

    def __init__(
        self,
        dialect,
        schema: Optional[str] = None,
        database: Optional[str] = None,
    ):
        super().__init__(dialect, schema)
        self.database = database

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_schema_list_query_statement"


class SnowflakeWarehouseListQueryStatement(IntrospectionExpression):
    """``SHOW WAREHOUSES`` -- there is no Information Schema view for warehouses.

    Documentation: https://docs.snowflake.com/en/sql-reference/sql/show-warehouses

    The view index at https://docs.snowflake.com/en/sql-reference/info-schema
    lists no ``WAREHOUSES`` view (the direct
    ``/sql-reference/info-schema/warehouses`` URL answers 404), so the ``SHOW``
    command is the documented route, and the existing
    :class:`~...expression.show.SnowflakeShowStatement` renders it.

    Two more facts from that page shape what the parser can expect, and both
    are reasons to read the rows as they are documented rather than as
    Information Schema rows:

    * "You must use double-quoted identifiers because the output column names
      for SHOW commands are in lowercase" -- the row keys are lowercase where
      every Information Schema column is uppercase.
    * "The command doesn't require a running warehouse to execute", where an
      Information Schema view needs one ("Warehouse must be running and
      currently in use to query the views",
      https://docs.snowflake.com/en/sql-reference/info-schema). Listing
      warehouses therefore works in a session that has none.

    Args:
        dialect: The dialect that renders this statement.
        schema: Unused -- warehouses are account-level, not schema objects.

    Example:
        >>> expr = SnowflakeWarehouseListQueryStatement(dialect)
        >>> sql, params = expr.to_sql()
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_warehouse_list_query_statement"


class SnowflakeTableStorageMetricsQueryStatement(IntrospectionExpression):
    """Storage billed to one table, joined to its row count and clustering.

    Primary view: https://docs.snowflake.com/en/sql-reference/info-schema/table_storage_metrics
    Joined view: https://docs.snowflake.com/en/sql-reference/info-schema/tables

    The storage view "displays table-level storage utilization information,
    which is used to calculate the storage billing for each table in the
    account, including tables that have been dropped, but are still incurring
    storage costs", and it splits the bytes into Active / Time Travel /
    Fail-safe / retained-for-clone. It documents no row count, no table type
    and no clustering key, so those come from ``TABLES`` -- which documents
    ``ROW_COUNT`` ("Number of rows in the table"), ``CLUSTERING_KEY``
    ("Clustering key for the table"), ``AUTO_CLUSTERING_ON`` (``BOOLEAN``) and
    ``TABLE_TYPE``. The join is on the three-part name, which both views carry.

    ``table_name`` and ``schema`` are **bind values**, not identifiers: they
    are compared to the catalog's columns, not interpolated into an object
    name. Unquoted object names are stored uppercase, so a caller passes the
    catalog's own spelling.

    Args:
        dialect: The dialect that renders this statement.
        table_name: The table to measure.
        schema: Schema to filter by, or ``None`` to ask for any schema. There
            is no ``database`` parameter because the view has none: it belongs
            to the session's current database, so the schema is the only
            narrowing filter this statement can express and omitting it is a
            legitimate request.

    Example:
        >>> expr = SnowflakeTableStorageMetricsQueryStatement(
        ...     dialect, "ORDERS", schema="PUBLIC"
        ... )
        >>> sql, params = expr.to_sql()
    """

    def __init__(
        self,
        dialect,
        table_name: str,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema)
        self.table_name = table_name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_table_storage_metrics_query_statement"


class SnowflakeFunctionListQueryStatement(IntrospectionExpression):
    """``SELECT`` over ``INFORMATION_SCHEMA.FUNCTIONS``.

    Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/functions

    The view lists user-defined functions, external functions and data metric
    functions in the current (or specified) database. It does not list the
    built-in system functions; those are served by ``SHOW FUNCTIONS`` and are
    not schema objects with an owner or a comment.
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_function_list_query_statement"


class SnowflakeProcedureListQueryStatement(IntrospectionExpression):
    """``SELECT`` over ``INFORMATION_SCHEMA.PROCEDURES``.

    Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/procedures

    Procedures are a separate catalog view from functions: the columns are
    prefixed ``PROCEDURE_`` and the return-value columns differ. Keeping a
    separate statement is what lets each formatter select the documented
    columns instead of projecting a union of two views.
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_procedure_list_query_statement"


class SnowflakeSequenceListQueryStatement(IntrospectionExpression):
    """``SELECT`` over ``INFORMATION_SCHEMA.SEQUENCES``.

    Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/sequences

    Snowflake sequences are standalone schema objects, like PostgreSQL's and
    MariaDB's; they are not a synonym for a table's identity column, which is
    answered by ``COLUMNS.IS_IDENTITY`` instead.
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_sequence_list_query_statement"


class SnowflakeStageListQueryStatement(IntrospectionExpression):
    """``SELECT`` over ``INFORMATION_SCHEMA.STAGES``.

    Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/stages

    The view lists named stages; the user and table stages are not named
    objects and do not appear here.
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_stage_list_query_statement"


class SnowflakeFileFormatListQueryStatement(IntrospectionExpression):
    """``SELECT`` over ``INFORMATION_SCHEMA.FILE_FORMATS``.

    Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/file_formats

    The view lists named file formats, with the delimiter, encoding and
    compression options each declares.
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_file_format_list_query_statement"


class SnowflakePipeListQueryStatement(IntrospectionExpression):
    """``SELECT`` over ``INFORMATION_SCHEMA.PIPES``.

    Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/pipes

    The view lists pipes, with the COPY statement each runs and the pattern it
    accepts. Current pipe status is not a catalog column; it is answered by
    ``SYSTEM$PIPE_STATUS``, which is left to the caller.
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_pipe_list_query_statement"


class SnowflakeTaskListQueryStatement(IntrospectionExpression):
    """``SHOW TASKS`` -- there is no ``INFORMATION_SCHEMA.TASKS`` view.

    Documentation: https://docs.snowflake.com/en/sql-reference/sql/show-tasks

    The Information Schema view index lists no ``TASKS`` view, so the
    documented route is the ``SHOW`` command, rendered by
    :class:`~...expression.show.SnowflakeShowStatement`. When a schema is
    given the statement is scoped to it with ``IN SCHEMA``; without one it
    keeps Snowflake's own default (the current database).
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_task_list_query_statement"


class SnowflakeStreamListQueryStatement(IntrospectionExpression):
    """``SHOW STREAMS`` -- there is no ``INFORMATION_SCHEMA.STREAMS`` view.

    Documentation: https://docs.snowflake.com/en/sql-reference/sql/show-streams

    As with tasks, the documented access path is ``SHOW``. Stream rows are
    documented in lowercase, and the introspector normalizes their keys before
    reading them.
    """

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_stream_list_query_statement"


class SnowflakeTableStateQueryStatement(IntrospectionExpression):
    """One table's kind, clustering and comment, from ``INFORMATION_SCHEMA.TABLES``.

    Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/tables

    Core's ``TableState`` asks for four things this backend can read from a
    single row of the table catalogue: the table's *kind* (regular, transient
    or temporary), any *compound traits* (clustering), the table's *comment*,
    and (through the manager's own partition answer) whether a partition
    scheme exists. The ``TABLES`` page documents the columns this statement
    selects:

    * ``IS_TRANSIENT`` -- "Indicates whether this is a transient table" (``VARCHAR``).
    * ``IS_TEMPORARY`` -- the same, for temporary tables, with ``YES``/``NO`` values.
    * ``CLUSTERING_KEY`` -- "Clustering key for the table".
    * ``AUTO_CLUSTERING_ON`` -- a real ``BOOLEAN`` for automatic clustering.
    * ``TABLE_TYPE`` -- the catalogue's own kind spelling, kept in the state's
      ``raw`` so a vendor kind (``HYBRID TABLE``, ``DYNAMIC TABLE``) is not
      folded away.
    * ``COMMENT`` -- "Comment for this table".

    Deliberately not selected: the storage parameters ``DATA_RETENTION_TIME_IN_DAYS``,
    ``DEFAULT_DDL_COLLATION`` and the ``STAGE_*`` properties. Those are reported
    by ``SHOW TABLES``, not by this view, and ``StorageOptionsState`` is left at
    its defaults rather than filled with a guess -- see the introspector's
    ``get_table_state``.

    The view's two view spellings are excluded by the dialect formatter: this
    statement asks a question about a table, and a view has no neutral table
    kind.

    Args:
        dialect: The dialect that renders this statement.
        table_name: The table to read. A bind value, compared to ``TABLE_NAME``.
        schema: Schema to filter by, or ``None`` for any schema.

    Example:
        >>> expr = SnowflakeTableStateQueryStatement(dialect, "ORDERS", schema="PUBLIC")
        >>> sql, params = expr.to_sql()
    """

    def __init__(
        self,
        dialect,
        table_name: str,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema)
        self.table_name = table_name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_table_state_query_statement"


class SnowflakeObjectExistsQueryStatement(IntrospectionExpression):
    """A one-row read that answers whether one named catalogue object exists.

    The question is core's ``item_exists(kind, name, schema)``: does a shared
    object of this kind exist. A listing answers the same fact only by
    returning every object in the schema, so this statement filters the one
    name and asks for a single row.

    The kinds this backend can answer are named by the dialect formatter
    (``format_object_exists_query_statement``), together with the view and
    column each one is read from. A kind with no Snowflake catalogue there is
    refused at render time with the same protocol error the manager's own
    refusal raises, so an unanswerable kind cannot render a query that claims
    to answer it. ``ItemKind.SCHEMA`` is account-structure rather than a
    schema object, so it reads ``SCHEMATA`` and takes no schema filter.

    Args:
        dialect: The dialect that renders this statement.
        kind: The core :class:`ItemKind` to ask about, or the word it carries.
            Stored as that word rather than as the member: this backend's own
            enums define ``__str__ = str.__str__`` so an artifact carries their
            value, but a core ``str`` enum does not, and its wire form is
            ``"ItemKind.SEQUENCE"`` -- unreadable by the member's own lookup.
            The formatter turns the word back into the member.
        name: The object's name, compared to the view's own name column.
        schema: Schema to filter by where the kind is schema-scoped, or ``None``
            for any schema.

    Example:
        >>> expr = SnowflakeObjectExistsQueryStatement(
        ...     dialect, ItemKind.SEQUENCE, "ORDER_SEQ", schema="PUBLIC"
        ... )
        >>> sql, params = expr.to_sql()
    """

    def __init__(
        self,
        dialect,
        kind: "ItemKind",
        name: str,
        schema: Optional[str] = None,
    ):
        super().__init__(dialect, schema)
        self.kind = as_member(ItemKind, kind, parameter="kind").value
        self.name = name

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_object_exists_query_statement"
