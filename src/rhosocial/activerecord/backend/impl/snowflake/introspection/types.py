# src/rhosocial/activerecord/backend/impl/snowflake/introspection/types.py
"""Snowflake account-object metadata, as typed immutable values.

These are *this backend's* answers, not core's: core has no scope for a
warehouse, and ``IntrospectionDatabaseInfo`` answers "which database am I
connected to?" rather than "which databases exist in the account?". Each
class here mirrors one documented Snowflake result set and says which
document it was written from.

Frozen because they are cache values: the cache hands the same object to
every caller, so an answer that a caller could mutate would let one caller
change what the next one sees. ``total_billed_bytes`` and friends are
properties rather than stored fields for the same reason -- derived values
cannot disagree with the columns they are derived from.

**Nothing here was run against a Snowflake account.** The column names and
value domains come from the documentation linked on each class; the test
suite asserts the row -> value mapping against fabricated rows, which pins
the parser and the SQL text but cannot pin the account's answer.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class SnowflakeDatabaseInfo:
    """One row of ``INFORMATION_SCHEMA.DATABASES``.

    Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/databases

    The columns read are the view's own: ``DATABASE_NAME``,
    ``DATABASE_OWNER``, ``IS_TRANSIENT`` (documented ``VARCHAR``, ``'YES'``
    or ``'NO'``), ``COMMENT``, ``CREATED`` and ``LAST_ALTERED``
    (``TIMESTAMP_LTZ``), ``RETENTION_TIME`` (``NUMBER``), ``TYPE`` and
    ``OWNER_ROLE_TYPE`` (``VARCHAR``). ``TYPE`` is documented as one of
    ``APPLICATION``, ``APPLICATION_PACKAGE``, ``STANDARD``,
    ``IMPORTED DATABASE`` and ``PERSONAL DATABASE``; it is stored under
    ``database_type`` so the field does not read as a Python type.
    """

    name: str
    owner: Optional[str] = None
    is_transient: bool = False
    comment: Optional[str] = None
    created: Optional[datetime] = None
    last_altered: Optional[datetime] = None
    retention_time: Optional[int] = None
    database_type: Optional[str] = None
    owner_role_type: Optional[str] = None


@dataclass(frozen=True)
class SnowflakeSchemaInfo:
    """One row of ``INFORMATION_SCHEMA.SCHEMATA`` in a chosen database.

    Documentation: https://docs.snowflake.com/en/sql-reference/info-schema/schemata

    Columns read: ``CATALOG_NAME`` (the database the schema belongs to),
    ``SCHEMA_NAME``, ``SCHEMA_OWNER``, ``IS_TRANSIENT`` and
    ``IS_MANAGED_ACCESS`` (both documented ``VARCHAR``), ``RETENTION_TIME``
    (``NUMBER``), ``CREATED`` / ``LAST_ALTERED`` (``TIMESTAMP_LTZ``) and
    ``COMMENT``.

    ``catalog_name`` is kept rather than assumed from the request: the view
    answers for the database it is qualified with, and keeping the reported
    catalog means a result cannot silently claim the wrong database when a
    caller passes ``database=None`` and the session's current database is
    something other than what they expected.
    """

    name: str
    catalog_name: Optional[str] = None
    owner: Optional[str] = None
    is_transient: bool = False
    is_managed_access: bool = False
    retention_time: Optional[int] = None
    created: Optional[datetime] = None
    last_altered: Optional[datetime] = None
    comment: Optional[str] = None


@dataclass(frozen=True)
class SnowflakeWarehouseInfo:
    """One row of ``SHOW WAREHOUSES``.

    Documentation: https://docs.snowflake.com/en/sql-reference/sql/show-warehouses

    ``SHOW`` output columns are documented in **lowercase** (the page's
    sample output header is ``name | state | type | ...``), which is why the
    parser normalizes row keys before reading them. ``state`` is documented
    as ``STARTED``, ``SUSPENDED`` or ``RESIZING``; ``type`` as ``STANDARD``
    or ``SNOWPARK-OPTIMIZED``; ``size`` as ``X-Small`` ... ``6X-Large``.

    ``is_default`` and ``is_current`` are documented as ``Y``/``N`` -- not
    the ``YES``/``NO`` that ``INFORMATION_SCHEMA`` uses -- so the flag
    parser accepts both. ``auto_suspend`` is documented as seconds with
    ``null`` meaning "never"; ``generation`` is a number in the page's
    sample output (1, 2, NULL) and is stored as an int.
    """

    name: str
    state: Optional[str] = None
    warehouse_type: Optional[str] = None
    size: Optional[str] = None
    min_cluster_count: Optional[int] = None
    max_cluster_count: Optional[int] = None
    started_clusters: Optional[int] = None
    running: Optional[int] = None
    queued: Optional[int] = None
    is_default: bool = False
    is_current: bool = False
    is_interactive: bool = False
    auto_suspend: Optional[int] = None
    auto_resume: Optional[bool] = None
    created_on: Optional[datetime] = None
    resumed_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None
    owner: Optional[str] = None
    comment: Optional[str] = None
    scaling_policy: Optional[str] = None
    resource_constraint: Optional[str] = None
    generation: Optional[int] = None
    enable_query_acceleration: Optional[bool] = None
    query_acceleration_max_scale_factor: Optional[int] = None
    resource_monitor: Optional[str] = None
    owner_role_type: Optional[str] = None


@dataclass(frozen=True)
class SnowflakeTableStorageMetrics:
    """Storage billed to one table, from ``TABLE_STORAGE_METRICS``.

    Documented columns and their meanings are on
    https://docs.snowflake.com/en/sql-reference/info-schema/table_storage_metrics:

    * ``TABLE_CATALOG``, ``TABLE_SCHEMA``, ``TABLE_NAME`` -- where the table
      is.
    * ``ID`` and ``CLONE_GROUP_ID`` -- ``NUMBER``. They are equal when the
      table is not a clone, and ``CLONE_GROUP_ID`` names the oldest clone
      ancestor.
    * ``IS_TRANSIENT`` -- ``'YES'`` if transient or temporary.
    * ``ACTIVE_BYTES``, ``TIME_TRAVEL_BYTES``, ``FAILSAFE_BYTES``,
      ``RETAINED_FOR_CLONE_BYTES`` -- the byte categories the page splits
      billed storage into.
    * ``TABLE_CREATED``, ``TABLE_DROPPED``, ``TABLE_ENTERED_FAILSAFE``,
      ``COMMENT`` -- lifecycle and comment.

    ``ROW_COUNT``, ``CLUSTERING_KEY``, ``AUTO_CLUSTERING_ON`` and
    ``TABLE_TYPE`` are **not** columns of this view; the page lists neither
    of them. They come from ``INFORMATION_SCHEMA.TABLES`` in the query that
    fills this object (https://docs.snowflake.com/en/sql-reference/info-schema/tables,
    which documents ``CLUSTERING_KEY`` as "Clustering key for the table",
    ``ROW_COUNT`` as "Number of rows in the table", ``AUTO_CLUSTERING_ON``
    as a ``BOOLEAN`` and ``TABLE_TYPE`` as one of ``BASE TABLE``,
    ``TEMPORARY TABLE``, ``EXTERNAL TABLE``, ``EVENT TABLE``, ``VIEW`` or
    ``MATERIALIZED VIEW``). They are optional because the storage view also
    keeps rows for **dropped** tables, which ``TABLES`` no longer lists;
    the query filters to the current version so a dropped row is not
    reported as if it had a live row count.

    Partition information is not a column of either view. Snowflake
    micro-partitions are not user-defined objects, and the documented
    clustering signal is ``CLUSTERING_KEY`` on ``TABLES``, which is what
    :attr:`is_clustered` reads. There is deliberately no invented
    ``partition_count`` field: the account does not report one here, and a
    fabricated number would be worse than an absent one.

    The view is documented as visible only to ``ACCOUNTADMIN``: "The view
    is visible to other views and can be queried, but the queries will
    return no rows." So an empty answer is not an error and the caller must
    read it as "no metrics for this role", not "no data in this table".
    """

    table_name: str
    table_catalog: Optional[str] = None
    table_schema: Optional[str] = None
    table_id: Optional[int] = None
    clone_group_id: Optional[int] = None
    is_transient: bool = False
    table_type: Optional[str] = None
    active_bytes: int = 0
    time_travel_bytes: int = 0
    failsafe_bytes: int = 0
    retained_for_clone_bytes: int = 0
    row_count: Optional[int] = None
    clustering_key: Optional[str] = None
    auto_clustering_on: bool = False
    table_created: Optional[datetime] = None
    table_dropped: Optional[datetime] = None
    table_entered_failsafe: Optional[datetime] = None
    comment: Optional[str] = None

    @property
    def total_billed_bytes(self) -> int:
        """All four byte categories added up.

        They are states of the same bytes, not overlapping slices: a byte is
        active, in Time Travel, in Fail-safe, or retained for a clone, and
        the page bills each category to this table. The sum is therefore the
        table's total billed storage -- and, per the page's usage notes, it
        is subject to the documented 1-2 hour delay in updating storage
        statistics.
        """
        return (
            self.active_bytes
            + self.time_travel_bytes
            + self.failsafe_bytes
            + self.retained_for_clone_bytes
        )

    @property
    def is_dropped(self) -> bool:
        """Whether ``TABLE_DROPPED`` carries a timestamp.

        Dropped tables stay in the view while they still incur storage
        costs, which is the documented reason the column exists. The
        introspector's query keeps only the current version, so this is
        ``False`` for every value it returns; it is defined here so a caller
        that builds the object from a wider query can still ask.
        """
        return self.table_dropped is not None

    @property
    def is_clustered(self) -> bool:
        """Whether ``TABLES.CLUSTERING_KEY`` names a clustering key."""
        return bool(self.clustering_key)
