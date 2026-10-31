# src/rhosocial/activerecord/backend/impl/snowflake/expression/introspection.py
"""Account-object introspection statements for Snowflake.

Four statements live here, one per question this backend asks the catalog that
core's introspection expressions do not model:

* :class:`SnowflakeDatabaseListQueryStatement` -- which databases exist.
* :class:`SnowflakeSchemaListQueryStatement` -- which schemas a database holds.
* :class:`SnowflakeWarehouseListQueryStatement` -- which warehouses the role can
  see.
* :class:`SnowflakeTableStorageMetricsQueryStatement` -- what one table is
  billed for storage.

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

__all__ = [
    "SnowflakeDatabaseListQueryStatement",
    "SnowflakeSchemaListQueryStatement",
    "SnowflakeWarehouseListQueryStatement",
    "SnowflakeTableStorageMetricsQueryStatement",
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
