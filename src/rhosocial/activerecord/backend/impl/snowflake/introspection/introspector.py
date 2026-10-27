# src/rhosocial/activerecord/backend/impl/snowflake/introspection/introspector.py
"""
Snowflake concrete introspectors.

Implements SyncAbstractIntrospector and AsyncAbstractIntrospector for Snowflake
databases using the INFORMATION_SCHEMA system views for metadata queries.

The introspectors are exposed via ``backend.introspector``.

Architecture:
  - SQL generation: Delegated to SnowflakeIntrospectionMixin.format_*_query()
    methods in the Dialect layer via Expression.to_sql()
  - Query execution: Handled by IntrospectorExecutor
  - Result parsing: parse_* methods in this module (pure Python, no I/O)

Key behaviours:
  - Queries INFORMATION_SCHEMA.TABLES, COLUMNS, TABLE_CONSTRAINTS,
    KEY_COLUMN_USAGE, REFERENTIAL_CONSTRAINTS, VIEWS
  - parse_* methods are pure Python -- shared by sync and async introspectors
  - Snowflake does not support triggers; parse_triggers returns empty list
  - Snowflake does not have traditional indexes; constraints are used instead

Design principle: Sync and Async are separate and cannot coexist.
- SyncSnowflakeIntrospector: for synchronous backends
- AsyncSnowflakeIntrospector: for asynchronous backends
"""

import asyncio
import copy
import warnings
from typing import Any, Dict, List, Optional

from rhosocial.activerecord.backend.introspection.base import (
    IntrospectorMixin,
    SyncAbstractIntrospector,
    AsyncAbstractIntrospector,
)
from rhosocial.activerecord.backend.introspection.cache import (
    IntrospectionCache,
)
from rhosocial.activerecord.backend.introspection.executor import (
    SyncIntrospectorExecutor,
)
from rhosocial.activerecord.backend.introspection.types import (
    IntrospectionDatabaseInfo,
    IntrospectionTableInfo,
    TableType,
    IntrospectionColumnInfo,
    ColumnNullable,
    IndexInfo,
    IndexColumnInfo,
    IndexType,
    IntrospectionForeignKeyInfo,
    ReferentialAction,
    IntrospectionViewInfo,
    IntrospectionTriggerInfo,
    IntrospectionScope,
)

from ..expression.introspection import (
    SnowflakeDatabaseListQueryStatement,
    SnowflakeSchemaListQueryStatement,
    SnowflakeTableStorageMetricsQueryStatement,
    SnowflakeWarehouseListQueryStatement,
)
from .types import (
    SnowflakeDatabaseInfo,
    SnowflakeSchemaInfo,
    SnowflakeTableStorageMetrics,
    SnowflakeWarehouseInfo,
)


class SnowflakeIntrospectorMixin(IntrospectorMixin):
    """Mixin providing shared Snowflake-specific introspection logic.

    Both SyncSnowflakeIntrospector and AsyncSnowflakeIntrospector inherit
    from this mixin to share:
    - Default schema handling
    - Snowflake version detection
    - parse_* implementations

    SQL generation is delegated to the Dialect layer via Expression.to_sql()
    which calls SnowflakeIntrospectionMixin.format_*_query() methods.
    """

    @property
    def default_schema(self) -> str:
        """Return the Snowflake schema name from the backend config.

        Snowflake uses a three-level namespace: database.schema.table.
        The schema is configured in the connection config.
        """
        if hasattr(self._backend, 'config') and self._backend.config:
            schema = (
                getattr(self._backend.config, 'schema', None)
                or getattr(self._backend.config, 'schema_name', None)
            )
            return schema or ""
        return ""

    # ------------------------------------------------------------------ #
    # Parse methods — pure Python, no I/O
    # ------------------------------------------------------------------ #

    def parse_database_info(self, rows: List[Dict[str, Any]]) -> IntrospectionDatabaseInfo:
        """Parse database info, reporting the version without raising.

        ``self.server_version`` reads the dialect, then the backend's cached
        server version, and never opens a connection. A version nothing knows
        yet is reported as ``"unknown"`` with the all-zero tuple, per the
        introspection contract.
        """
        version = self.server_version
        version_tuple = version if version is not None else (0, 0, 0)
        version_str = (
            "unknown" if version is None else ".".join(str(v) for v in version)
        )
        db_name = self.default_schema

        db_row = rows[0] if rows else {}

        return IntrospectionDatabaseInfo(
            name=db_row.get("CATALOG_NAME", db_name),
            version=version_str,
            version_tuple=version_tuple,
            vendor="Snowflake",
        )

    # ------------------------------------------------------------------ #
    # Account-object parsing -- Snowflake's own views, not core's scopes
    # ------------------------------------------------------------------ #

    @staticmethod
    def _upper_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """One result row with its keys upper-cased.

        ``INFORMATION_SCHEMA`` columns are documented uppercase, but
        ``SHOW`` output is documented lowercase (the ``SHOW WAREHOUSES``
        page's sample header is ``name | state | type | ...``). The driver
        reproduces whichever spelling the statement produces, so the parser
        normalizes before reading and does not have to care which kind of
        statement answered. Values are untouched: only the keys are casing.
        """
        return {str(key).upper(): value for key, value in row.items()}

    @staticmethod
    def _as_flag(value: Any) -> bool:
        """Read one of Snowflake's several spellings of a boolean flag.

        The catalog is not consistent, and the difference is documented
        rather than incidental: Information Schema columns such as
        ``IS_TRANSIENT`` are ``VARCHAR`` holding ``'YES'``/``'NO'``
        (https://docs.snowflake.com/en/sql-reference/info-schema/databases),
        while ``SHOW WAREHOUSES`` documents ``is_current`` and friends as
        ``Y``/``N`` (https://docs.snowflake.com/en/sql-reference/sql/show-warehouses).
        ``TABLES.AUTO_CLUSTERING_ON`` is a real ``BOOLEAN``. Treating an
        unreadable value as false matches the "no" default all three
        spellings share; treating it as true would invent a capability.
        """
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return value != 0
        return str(value).strip().upper() in ("Y", "YES", "TRUE", "1")

    @classmethod
    def _as_optional_flag(cls, value: Any) -> Optional[bool]:
        """A flag that distinguishes "not reported" from "reported false".

        ``SHOW WAREHOUSES`` documents ``auto_resume`` as a boolean but says
        nothing about NULL, and a missing optional property is not the same
        answer as "false" -- so the ``None`` is preserved for the fields
        where the docs describe a possibly-absent property.
        """
        if value is None:
            return None
        return cls._as_flag(value)

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:
        """One catalog number as an ``int``, or ``None`` when unreadable.

        The catalog is not under this backend's control; an unreadable
        count should cost that field its value, not the whole row. Zero is
        preserved: it is a real byte count and a real retention period.
        """
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def parse_databases(self, rows: List[Dict[str, Any]]) -> List[SnowflakeDatabaseInfo]:
        """Parse ``INFORMATION_SCHEMA.DATABASES`` rows.

        Columns read and their documented meanings are in
        :meth:`~..mixins.introspection.SnowflakeIntrospectionMixin.format_database_list_query_statement`
        and https://docs.snowflake.com/en/sql-reference/info-schema/databases:
        ``DATABASE_NAME``, ``DATABASE_OWNER``, ``IS_TRANSIENT`` (``VARCHAR``
        ``'YES'``/``'NO'``), ``COMMENT``, ``CREATED``, ``LAST_ALTERED``,
        ``RETENTION_TIME``, ``TYPE`` and ``OWNER_ROLE_TYPE``.
        """
        databases = []
        for row in rows:
            normalized = self._upper_row(row)
            databases.append(
                SnowflakeDatabaseInfo(
                    name=normalized.get("DATABASE_NAME", ""),
                    owner=normalized.get("DATABASE_OWNER"),
                    is_transient=self._as_flag(normalized.get("IS_TRANSIENT")),
                    comment=normalized.get("COMMENT"),
                    created=normalized.get("CREATED"),
                    last_altered=normalized.get("LAST_ALTERED"),
                    retention_time=self._as_int(normalized.get("RETENTION_TIME")),
                    database_type=normalized.get("TYPE"),
                    owner_role_type=normalized.get("OWNER_ROLE_TYPE"),
                )
            )
        return databases

    def parse_schemas(self, rows: List[Dict[str, Any]]) -> List[SnowflakeSchemaInfo]:
        """Parse ``INFORMATION_SCHEMA.SCHEMATA`` rows.

        Columns read are documented on
        https://docs.snowflake.com/en/sql-reference/info-schema/schemata:
        ``CATALOG_NAME``, ``SCHEMA_NAME``, ``SCHEMA_OWNER``,
        ``IS_TRANSIENT``, ``IS_MANAGED_ACCESS``, ``RETENTION_TIME``,
        ``CREATED``, ``LAST_ALTERED`` and ``COMMENT``.

        ``IS_MANAGED_ACCESS`` is kept as a flag rather than dropped: it is
        the documented answer to "does this schema use managed access?", and
        a caller deciding whether a grant will be honoured needs it.
        """
        schemas = []
        for row in rows:
            normalized = self._upper_row(row)
            schemas.append(
                SnowflakeSchemaInfo(
                    name=normalized.get("SCHEMA_NAME", ""),
                    catalog_name=normalized.get("CATALOG_NAME"),
                    owner=normalized.get("SCHEMA_OWNER"),
                    is_transient=self._as_flag(normalized.get("IS_TRANSIENT")),
                    is_managed_access=self._as_flag(normalized.get("IS_MANAGED_ACCESS")),
                    retention_time=self._as_int(normalized.get("RETENTION_TIME")),
                    created=normalized.get("CREATED"),
                    last_altered=normalized.get("LAST_ALTERED"),
                    comment=normalized.get("COMMENT"),
                )
            )
        return schemas

    def parse_warehouses(self, rows: List[Dict[str, Any]]) -> List[SnowflakeWarehouseInfo]:
        """Parse ``SHOW WAREHOUSES`` rows.

        The row shape is the one documented on
        https://docs.snowflake.com/en/sql-reference/sql/show-warehouses:
        **lowercase** keys, ``is_default`` / ``is_current`` /
        ``is_interactive`` as ``Y``/``N``, ``auto_suspend`` in seconds with
        ``null`` for "never", and ``size`` spelled ``X-Small`` ...
        ``6X-Large``. ``_upper_row`` bridges the casing and ``_as_flag`` the
        ``Y``/``N`` spelling, so nothing here depends on the driver choosing
        one casing over the other.

        ``available`` / ``provisioning`` / ``quiescing`` / ``other`` are
        percentages documented as possibly empty, and the ``actives`` /
        ``pendings`` / ``failed`` / ``suspended`` / ``uuid`` columns are
        documented as "for internal use and will be removed in a future
        release" -- none is modelled, because a field whose meaning the
        vendor has disclaimed is not metadata this backend should promise.
        """
        warehouses = []
        for row in rows:
            normalized = self._upper_row(row)
            warehouses.append(
                SnowflakeWarehouseInfo(
                    name=normalized.get("NAME", ""),
                    state=normalized.get("STATE"),
                    warehouse_type=normalized.get("TYPE"),
                    size=normalized.get("SIZE"),
                    min_cluster_count=self._as_int(normalized.get("MIN_CLUSTER_COUNT")),
                    max_cluster_count=self._as_int(normalized.get("MAX_CLUSTER_COUNT")),
                    started_clusters=self._as_int(normalized.get("STARTED_CLUSTERS")),
                    running=self._as_int(normalized.get("RUNNING")),
                    queued=self._as_int(normalized.get("QUEUED")),
                    is_default=self._as_flag(normalized.get("IS_DEFAULT")),
                    is_current=self._as_flag(normalized.get("IS_CURRENT")),
                    is_interactive=self._as_flag(normalized.get("IS_INTERACTIVE")),
                    auto_suspend=self._as_int(normalized.get("AUTO_SUSPEND")),
                    auto_resume=self._as_optional_flag(normalized.get("AUTO_RESUME")),
                    created_on=normalized.get("CREATED_ON"),
                    resumed_on=normalized.get("RESUMED_ON"),
                    updated_on=normalized.get("UPDATED_ON"),
                    owner=normalized.get("OWNER"),
                    comment=normalized.get("COMMENT"),
                    scaling_policy=normalized.get("SCALING_POLICY"),
                    resource_constraint=normalized.get("RESOURCE_CONSTRAINT"),
                    generation=self._as_int(normalized.get("GENERATION")),
                    enable_query_acceleration=self._as_optional_flag(
                        normalized.get("ENABLE_QUERY_ACCELERATION")
                    ),
                    query_acceleration_max_scale_factor=self._as_int(
                        normalized.get("QUERY_ACCELERATION_MAX_SCALE_FACTOR")
                    ),
                    resource_monitor=normalized.get("RESOURCE_MONITOR"),
                    owner_role_type=normalized.get("OWNER_ROLE_TYPE"),
                )
            )
        return warehouses

    def parse_table_storage_metrics(
        self,
        rows: List[Dict[str, Any]],
        table_name: str,
        schema: Optional[str],
    ) -> Optional[SnowflakeTableStorageMetrics]:
        """Parse the storage-metrics row for one table, or ``None``.

        The byte columns are the ones documented on
        https://docs.snowflake.com/en/sql-reference/info-schema/table_storage_metrics;
        ``ROW_COUNT``, ``CLUSTERING_KEY``, ``AUTO_CLUSTERING_ON`` and
        ``TABLE_TYPE`` come from the joined ``TABLES`` row, documented on
        https://docs.snowflake.com/en/sql-reference/info-schema/tables.
        See :meth:`~..mixins.introspection.SnowflakeIntrospectionMixin.format_table_storage_metrics_query_statement`
        for why the join exists and why only the current table version is asked
        for.

        Only the current version is used even if a wider result set arrives:
        a row with ``TABLE_DROPPED`` set describes a table that no longer
        exists, and reporting it as this table's metrics would answer a
        question nobody asked. The first current row wins; a result with no
        current row falls back to the first row so a caller that widened the
        query still gets the row it selected rather than a silent ``None``.

        ``None`` is returned for no rows, which -- per the view's documented
        ``ACCOUNTADMIN`` requirement -- can also mean "this role may not see
        the metrics". The caller cannot tell the two apart from this view;
        the docstring of :meth:`get_table_storage_metrics` says so instead of
        pretending otherwise.
        """
        if not rows:
            return None

        normalized_rows = [self._upper_row(row) for row in rows]
        row = next(
            (candidate for candidate in normalized_rows if candidate.get("TABLE_DROPPED") is None),
            normalized_rows[0],
        )

        return SnowflakeTableStorageMetrics(
            table_name=row.get("TABLE_NAME") or table_name,
            table_catalog=row.get("TABLE_CATALOG"),
            table_schema=row.get("TABLE_SCHEMA") or schema or None,
            table_id=self._as_int(row.get("ID")),
            clone_group_id=self._as_int(row.get("CLONE_GROUP_ID")),
            is_transient=self._as_flag(row.get("IS_TRANSIENT")),
            table_type=row.get("TABLE_TYPE"),
            active_bytes=self._as_int(row.get("ACTIVE_BYTES")) or 0,
            time_travel_bytes=self._as_int(row.get("TIME_TRAVEL_BYTES")) or 0,
            failsafe_bytes=self._as_int(row.get("FAILSAFE_BYTES")) or 0,
            retained_for_clone_bytes=self._as_int(
                row.get("RETAINED_FOR_CLONE_BYTES")
            )
            or 0,
            row_count=self._as_int(row.get("ROW_COUNT")),
            clustering_key=row.get("CLUSTERING_KEY"),
            auto_clustering_on=self._as_flag(row.get("AUTO_CLUSTERING_ON")),
            table_created=row.get("TABLE_CREATED"),
            table_dropped=row.get("TABLE_DROPPED"),
            table_entered_failsafe=row.get("TABLE_ENTERED_FAILSAFE"),
            comment=row.get("COMMENT"),
        )

    def parse_tables(
        self, rows: List[Dict[str, Any]], schema: Optional[str]
    ) -> List[IntrospectionTableInfo]:
        target_schema = schema if schema is not None else self.default_schema
        table_type_map = {
            "BASE TABLE": TableType.BASE_TABLE,
            "VIEW": TableType.VIEW,
            "MATERIALIZED VIEW": TableType.MATERIALIZED_VIEW,
            "SYSTEM TABLE": TableType.SYSTEM_TABLE,
            "EXTERNAL TABLE": TableType.EXTERNAL,
            "TEMPORARY TABLE": TableType.TEMPORARY,
        }
        tables = []
        for row in rows:
            t_type = table_type_map.get(
                row.get("TABLE_TYPE", "BASE TABLE"), TableType.BASE_TABLE
            )
            tables.append(
                IntrospectionTableInfo(
                    name=row["TABLE_NAME"],
                    schema=target_schema,
                    table_type=t_type,
                    comment=row.get("COMMENT"),
                )
            )
        return tables

    #: Concept name -> the ``INFORMATION_SCHEMA.COLUMNS`` column that carries
    #: that concept's width.
    #:
    #: Keyed by the concept's own ``name``, **not** by the catalog word, so the
    #: dialect stays the only place that knows which words mean which concept:
    #: the shape is decided by parsing the bare word once and reading ``name`` off
    #: the result, and this table only has to say which column answers which
    #: parameter.  That is the same division the rest of the codebase uses -- one
    #: place per vocabulary -- and it is why adding ``NVARCHAR2`` or ``CHAR
    #: VARYING`` to the manual needs no edit here.
    #:
    #: Every key names a concept whose size the manual states in **characters**,
    #: which is what the one column is documented in: "Maximum length in
    #: characters of string columns."
    #: https://docs.snowflake.com/en/sql-reference/info-schema/columns
    #:
    #: ``text`` is here because Snowflake documents it as the same storage:
    #: "STRING, TEXT, VARCHAR2, NVARCHAR, NVARCHAR2, CHAR VARYING, NCHAR
    #: VARYING -- Synonymous with VARCHAR."  A *sized* ``TEXT(50)`` column is
    #: therefore a 50-character variable-length string, and it is parsed as one;
    #: a bare ``TEXT`` stays :class:`~...expression.types.TextType`, because the
    #: bare form genuinely is the unbounded concept.  See
    #: :meth:`~...mixins.types.SnowflakeTypeSupportMixin.parse_type`.
    _SNOW_WIDTH_COLUMN = {
        "varchar": "CHARACTER_MAXIMUM_LENGTH",
        "char": "CHARACTER_MAXIMUM_LENGTH",
        "text": "CHARACTER_MAXIMUM_LENGTH",
    }

    #: The concept whose size the catalog reports as **numeric precision and
    #: scale** rather than as a length.  It is deliberately a single name and
    #: not a family, because the split is documented per type, not per shape:
    #:
    #: * ``NUMBER`` and its synonyms do carry both, and the catalog reports
    #:   them -- "NUMERIC_PRECISION -- Numeric precision of numeric columns",
    #:   "NUMERIC_SCALE -- Scale of numeric columns", and a bare ``NUMBER`` is
    #:   "NUMBER(38, 0)" by the manual's own words.
    #:   https://docs.snowflake.com/en/sql-reference/data-types-numeric
    #: * the integer names are documented as "Synonymous with NUMBER, **except
    #:   precision and scale can't be specified**", so their ``NUMERIC_PRECISION``
    #:   of 38 is the bare ``NUMBER`` they are, not a declared precision, and
    #:   composing it would turn every ``INT`` column into ``DecimalType(38, 0)``.
    #: * the float family is not composed at all: ``DESC TABLE`` renders
    #:   ``DOUBLE``, ``DOUBLE PRECISION`` and ``REAL`` as a bare ``FLOAT`` with
    #:   no precision, and the column that would settle what unit a reported
    #:   precision is in -- ``NUMERIC_PRECISION_RADIX``, documented as "Radix of
    #:   precision of numeric columns" -- is not selected by the query above.
    #:   Composing a number whose unit is unresolved would be a guess.
    _SNOW_NUMERIC_CONCEPT = "decimal"

    #: Concept names whose size is a **byte** count in the catalog rather than a
    #: character count, so they must never be fed the character column.
    #:
    #: ``BINARY`` is the only one, and it is here as a statement about what this
    #: backend does **not** claim.  The manual is explicit that the two are
    #: different units: "Unlike VARCHAR, the BINARY data type has no notion of
    #: Unicode characters, so the length is always measured in terms of bytes"
    #: (``BINARY(n)`` defaults to 8388608, and ``DESC TABLE`` renders
    #: ``BINARY(100)``).  But neither catalog column is documented for it --
    #: ``CHARACTER_MAXIMUM_LENGTH`` is "in characters of **string** columns" and
    #: ``CHARACTER_OCTET_LENGTH`` is "in bytes of **string** columns", and the
    #: manual files BINARY under "Data types for **binary** strings" -- so there
    #: is no column this backend can honestly read a binary width from.  It is
    #: named so the gap is visible in the source rather than implied by an
    #: absence, and ``_SNOW_WIDTH_COLUMN`` does not mention it.
    #: https://docs.snowflake.com/en/sql-reference/data-types-text
    _SNOW_BYTE_COUNTED_CONCEPTS = ("blob",)

    @staticmethod
    def _catalog_number(value: Any) -> Optional[int]:
        """One catalog number as an ``int``, or ``None`` when there is not one.

        The catalog columns are declared ``NUMBER``, so the driver hands back an
        integer; ``None`` is the documented "not applicable for this column"
        answer and is the only thing mapped to ``None`` here.  A value that is not
        a number at all is treated as absent rather than raising: the catalog is
        not under this backend's control, and an unreadable size should cost one
        column its width, not the whole table.

        **Zero is preserved, not filtered.**  ``NUMERIC_SCALE`` of ``0`` is a real
        answer with a meaning -- ``NUMBER(10, 0)`` is a column with no fractional
        digits, which is not the same column as a scale of "unspecified" -- so
        deciding what counts as a usable number is left to each call site, where
        the rule for that parameter is known.  Folding zero into "absent" here
        would have turned every ``NUMBER(10, 0)`` into ``NUMBER(10)`` and
        ``NUMBER(38, 0)`` -- the documented bare ``NUMBER`` -- into ``NUMBER(38)``,
        which is precisely the value :meth:`_catalog_type_string` has to recognise
        as the default.
        """
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _catalog_width(value: Any) -> Optional[int]:
        """A catalog length, or ``None`` when the column reports no usable one.

        A width of zero is not a column Snowflake can declare -- ``VARCHAR`` and
        ``CHAR`` both have a minimum of one character -- so a zero or a missing
        value is "no width here" and the bare word is what gets composed.
        """
        width = SnowflakeIntrospectorMixin._catalog_number(value)
        return width if width is not None and width > 0 else None

    def _catalog_type_string(
        self,
        row: Dict[str, Any],
        dialect: Any,
    ) -> str:
        """The one type string ``parse_type`` is asked to read, size included.

        Snowflake splits what a caller writes as a single type across several
        catalog columns, so handing ``parse_type`` the bare ``DATA_TYPE`` alone
        throws away the size and only the size.  Measured on this worktree with
        the query in :meth:`~...mixins.introspection.SnowflakeIntrospectionMixin.format_column_info_query_statement`:
        a ``VARCHAR(50)`` column answered ``16777216`` -- the *bare* word reached
        the parser and the parser honestly filled in Snowflake's documented
        default -- and a ``NUMBER(10, 2)`` column answered ``DecimalType()`` with
        both parameters gone.  Two different symptoms, one cause: the width never
        left the catalog.

        The shape of the fix follows the sibling introspectors rather than
        anything new.  PostgreSQL never has this problem because
        ``pg_catalog.format_type(a.atttypid, a.atttypmod)`` hands back a composed
        ``character varying(50)``; MySQL prefers ``COLUMN_TYPE`` over
        ``DATA_TYPE``, i.e. it asks for the already-composed column; SQL Server
        builds ``f"{data_type}({max_len})"`` / ``f"{data_type}({precision},{scale})"``
        / the bare word from ``INFORMATION_SCHEMA.COLUMNS`` itself, which is the
        shape Snowflake needs and the one used here.
        https://docs.snowflake.com/en/sql-reference/info-schema/columns

        What differs is *which column answers which shape*, and Snowflake's
        catalog answers per type rather than per family:

        ``CHARACTER_MAXIMUM_LENGTH``
            "Maximum length in **characters** of string columns" -- so it is fed
            to the string concepts named in :attr:`_SNOW_WIDTH_COLUMN` and to
            nothing else.  That it carries the declared width, not a fixed
            column width, is documented with a worked example: when Snowpark
            creates a string column as ``VARCHAR(134217728)``, "INFORMATION_SCHEMA
            .COLUMNS reports a ``CHARACTER_MAXIMUM_LENGTH`` of 134217728, not
            16777216."
        ``NUMERIC_PRECISION`` / ``NUMERIC_SCALE``
            "Numeric precision of numeric columns" / "Scale of numeric columns",
            fed to :attr:`_SNOW_NUMERIC_CONCEPT` only -- see that attribute for
            why the integer and float shapes are left alone.

        The exact numeric shape is the one whose reported pair used to be folded
        back to the bare word, and that folding is gone.  It existed only because
        a declaration that named no precision could carry none: the bare word was
        the one thing it could compare equal to.  Core now resolves
        ``DecimalType.precision``/``scale`` against
        :meth:`~...mixins.types.SnowflakeTypeSupportMixin.type_parameter_defaults`
        at read time, so ``DecimalType(dialect)`` carries 38/0 and
        ``NUMBER(38, 0)`` -- the pair the catalog reported, and the manual's own
        words for a bare ``NUMBER`` -- parses to an equal object.  Composing the
        pair the catalog actually reported is therefore both safe and more
        honest: ``data_type_full`` says what the size is instead of repeating a
        word whose size was only implied.
        """
        from rhosocial.activerecord.backend.expression.types._base import DataType

        word = row.get("DATA_TYPE") or "VARCHAR"
        # Which concept the catalog's word names is the dialect's answer, not
        # this file's: parse the bare word and read the identity off the result.
        # An unreadable word is caught here rather than raised, because not being
        # able to name its concept is the same as not knowing which column would
        # have carried its size -- so nothing is composed, the bare word is handed
        # on, and :meth:`parse_data_type` is where the unreadable type is
        # reported and degraded to ``None`` for that one column.
        try:
            concept = getattr(
                DataType.parse_data_type_str(dialect, word), "name", None
            )
        except Exception:  # noqa: BLE001 -- see the docstring
            concept = None
        width_column = self._SNOW_WIDTH_COLUMN.get(concept)
        if width_column is not None:
            width = self._catalog_width(row.get(width_column))
            return f"{word}({width})" if width is not None else word
        if concept == self._SNOW_NUMERIC_CONCEPT:
            precision = self._catalog_number(row.get("NUMERIC_PRECISION"))
            scale = self._catalog_number(row.get("NUMERIC_SCALE"))
            if precision is None or precision <= 0:
                return word
            if scale is None:
                return f"{word}({precision})"
            return f"{word}({precision}, {scale})"
        # Every other shape -- the integer names, the float family, BINARY,
        # BOOLEAN, the date/time words, VARIANT/OBJECT/ARRAY, GEOGRAPHY,
        # GEOMETRY, UUID -- is reported with no size the catalog documents for
        # it, and the bare word is the honest input for all of them.
        return word

    @staticmethod
    def parse_data_type(
        composed: str, row: Dict[str, Any], dialect: Any
    ) -> Optional[Any]:
        """Read one composed catalog type string into a ``DataType``, or ``None``.

        ``IntrospectionColumnInfo.parsed_data_type`` is ``None`` for exactly one reason --
        the catalog string could not be read -- and core's differ branches on
        it, falling back to comparing the ``data_type`` *strings*.  So an
        unreadable column must degrade to ``None`` rather than abort
        ``list_columns`` for the table: the catalog is not under this backend's
        control, and MariaDB's introspector already carries this guard for the
        same reason.

        The string handed in is built by :meth:`_catalog_type_string` and is read
        by the dialect's own ``parse_type``, so a type Snowflake adds cannot
        fail here unless it fails in ``parse_type`` too -- and ``parse_type``
        ends in ``CustomType``, whose constructor validates the raw name, so an
        unmodelled type still parses rather than raises.
        """
        from rhosocial.activerecord.backend.expression.types._base import DataType

        try:
            return DataType.parse_data_type_str(dialect, composed)
        except Exception as exc:  # noqa: BLE001 -- see the docstring
            warnings.warn(
                f"Snowflake reported column type {composed!r} (DATA_TYPE "
                f"{row.get('DATA_TYPE')!r}), which this backend's parse_type "
                f"could not read ({type(exc).__name__}: {exc}). That column's "
                f"parsed_data_type is left unset, so the schema differ will "
                f"compare its data_type string rather than the type object. "
                f"The rest of the table is unaffected.",
                RuntimeWarning,
                stacklevel=3,
            )
            return None

    def parse_columns(
        self,
        rows: List[Dict[str, Any]],
        table_name: str,
        schema: str,
    ) -> List[IntrospectionColumnInfo]:
        columns = []
        dialect = getattr(self._backend, "dialect", None)
        for row in rows:
            nullable = (
                ColumnNullable.NULLABLE
                if row.get("IS_NULLABLE") == "YES"
                else ColumnNullable.NOT_NULL
            )
            data_type = row.get("DATA_TYPE") or "VARCHAR"
            # ``data_type`` stays the bare word the catalog reported and
            # ``data_type_full`` carries the size, which is what the two fields
            # are for: the string core's differ falls back to when a type cannot
            # be parsed is the word, and the composed spelling is the one that
            # says how wide the column is.
            composed = (
                self._catalog_type_string(row, dialect) if dialect else data_type
            )
            columns.append(
                IntrospectionColumnInfo(
                    name=row["COLUMN_NAME"],
                    table_name=table_name,
                    schema=schema,
                    ordinal_position=row.get("ORDINAL_POSITION"),
                    data_type=data_type.lower(),
                    data_type_full=composed,
                    parsed_data_type=(
                        self.parse_data_type(composed, row, dialect)
                        if dialect
                        else None
                    ),
                    nullable=nullable,
                    default_value=row.get("COLUMN_DEFAULT"),
                    comment=row.get("COMMENT"),
                    character_maximum_length=row.get("CHARACTER_MAXIMUM_LENGTH"),
                    numeric_precision=row.get("NUMERIC_PRECISION"),
                    numeric_scale=row.get("NUMERIC_SCALE"),
                    collation=row.get("COLLATION_NAME"),
                )
            )
        return columns

    def parse_indexes(
        self,
        rows: List[Dict[str, Any]],
        table_name: str,
        schema: str,
    ) -> List[IndexInfo]:
        """Parse constraint rows into IndexInfo objects.

        Snowflake does not have traditional indexes. Primary key and unique
        constraints are mapped to IndexInfo for consistency with the
        introspection API.
        """
        constraint_map: Dict[str, IndexInfo] = {}
        for row in rows:
            c_name = row.get("CONSTRAINT_NAME", "")
            c_type = row.get("CONSTRAINT_TYPE", "")

            if c_name not in constraint_map:
                is_primary = c_type == "PRIMARY KEY"
                constraint_map[c_name] = IndexInfo(
                    name=c_name,
                    table_name=table_name,
                    schema=schema,
                    is_unique=True,
                    is_primary=is_primary,
                    index_type=IndexType.UNKNOWN,
                    columns=[],
                )
            constraint_map[c_name].columns.append(
                IndexColumnInfo(
                    name=row.get("COLUMN_NAME", ""),
                    ordinal_position=int(row.get("ORDINAL_POSITION", 1)),
                    is_descending=False,
                )
            )
        return list(constraint_map.values())

    def parse_foreign_keys(
        self,
        rows: List[Dict[str, Any]],
        table_name: str,
        schema: str,
    ) -> List[IntrospectionForeignKeyInfo]:
        action_map = {
            "NO ACTION": ReferentialAction.NO_ACTION,
            "RESTRICT": ReferentialAction.RESTRICT,
            "CASCADE": ReferentialAction.CASCADE,
            "SET NULL": ReferentialAction.SET_NULL,
            "SET DEFAULT": ReferentialAction.SET_DEFAULT,
        }
        fk_map: Dict[str, IntrospectionForeignKeyInfo] = {}
        for row in rows:
            fk_name = row.get("CONSTRAINT_NAME", "")
            if fk_name not in fk_map:
                on_update_raw = (row.get("UPDATE_RULE") or "NO ACTION").upper()
                on_delete_raw = (row.get("DELETE_RULE") or "NO ACTION").upper()
                fk_map[fk_name] = IntrospectionForeignKeyInfo(
                    name=fk_name,
                    table_name=table_name,
                    schema=schema,
                    referenced_table=row.get("REFERENCED_TABLE_NAME", ""),
                    on_update=action_map.get(on_update_raw, ReferentialAction.NO_ACTION),
                    on_delete=action_map.get(on_delete_raw, ReferentialAction.NO_ACTION),
                    columns=[],
                    referenced_columns=[],
                )
            fk_map[fk_name].columns.append(row.get("COLUMN_NAME", ""))
            fk_map[fk_name].referenced_columns.append(
                row.get("REFERENCED_COLUMN_NAME", "")
            )
        return list(fk_map.values())

    def parse_views(
        self, rows: List[Dict[str, Any]], schema: str
    ) -> List[IntrospectionViewInfo]:
        return [
            IntrospectionViewInfo(
                name=row.get("TABLE_NAME", ""),
                schema=schema,
                definition=row.get("VIEW_DEFINITION"),
                check_option=row.get("CHECK_OPTION"),
                is_updatable=row.get("IS_UPDATABLE") == "YES",
            )
            for row in rows
        ]

    def parse_view_info(
        self,
        rows: List[Dict[str, Any]],
        view_name: str,
        schema: str,
    ) -> Optional[IntrospectionViewInfo]:
        if not rows:
            return None
        row = rows[0]
        return IntrospectionViewInfo(
            name=row.get("TABLE_NAME", view_name),
            schema=schema,
            definition=row.get("VIEW_DEFINITION"),
            check_option=row.get("CHECK_OPTION"),
            is_updatable=row.get("IS_UPDATABLE") == "YES",
        )

    def parse_triggers(
        self, rows: List[Dict[str, Any]], schema: str
    ) -> List[IntrospectionTriggerInfo]:
        """Snowflake does not support triggers; always returns empty list."""
        return []


class SyncSnowflakeIntrospector(
    SnowflakeIntrospectorMixin, SyncAbstractIntrospector
):
    """Synchronous introspector for Snowflake backends.

    Access via ``backend.introspector``::

        tables = backend.introspector.list_tables()
        columns = backend.introspector.list_columns("my_table")
    """

    def __init__(
        self,
        backend: Any,
        executor: SyncIntrospectorExecutor,
        cache: Optional[IntrospectionCache] = None,
    ) -> None:
        super().__init__(backend, executor, cache)

    def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[IntrospectionTableInfo]:
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=schema
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        tables = self.list_tables(schema)
        table = next((t for t in tables if t.name == table_name), None)
        if table is None:
            return None

        table = copy.copy(table)
        table.columns = self.list_columns(table_name, schema)
        table.indexes = self.list_indexes(table_name, schema)
        table.foreign_keys = self.list_foreign_keys(table_name, schema)
        self._cache.set(key, table)
        return table

    # ------------------------------------------------------------------ #
    # Account-level objects: databases, schemas, warehouses, storage
    # ------------------------------------------------------------------ #

    def list_databases(self) -> List[SnowflakeDatabaseInfo]:
        """List every database the session's role can see.

        Reads ``SNOWFLAKE.INFORMATION_SCHEMA.DATABASES``; see
        :meth:`~..mixins.introspection.SnowflakeIntrospectionMixin.format_database_list_query_statement`
        for the columns and the reason the view is qualified with ``SNOWFLAKE``.
        This answers "which
        databases exist in the account", which is not what
        :meth:`get_database_info` answers ("which database am I connected
        to") -- hence the ``extra`` on the cache key: both live in
        :attr:`IntrospectionScope.DATABASE`, and without it the two questions
        would serve each other's answers.

        The view is documented to return fewer rows than ``SHOW DATABASES``
        for a holder of ``MANAGE GRANTS``, so this is the privilege-filtered
        answer, not a claim of omniscience.
        """
        key = self._cache.key(IntrospectionScope.DATABASE, extra="databases")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = SnowflakeDatabaseListQueryStatement(self.dialect).to_sql()
        result = self.parse_databases(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_schemas(self, database: Optional[str] = None) -> List[SnowflakeSchemaInfo]:
        """List the schemas of *database*, or of the session's current one.

        ``SCHEMATA`` is a database-level view (documented on
        https://docs.snowflake.com/en/sql-reference/info-schema/schemata),
        so ``database=None`` is a real choice -- "the current database" --
        and not a default standing in for a required argument. Passing a
        name qualifies the view with it; see
        :meth:`~..mixins.introspection.SnowflakeIntrospectionMixin.format_schema_list_query_statement`
        for the quoting rule.

        The ``database`` is part of the cache key as a positional
        discriminator, so ``list_schemas()`` and ``list_schemas("OTHER")``
        cannot answer each other -- ``schema=`` would be the wrong slot for
        it, because that parameter names the schema of the *requested*
        objects, and here the database is the container being enumerated.
        """
        key = self._cache.key(
            IntrospectionScope.SCHEMA, database or "*", extra="schemas"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = SnowflakeSchemaListQueryStatement(
            self.dialect, database=database
        ).to_sql()
        result = self.parse_schemas(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def list_warehouses(self) -> List[SnowflakeWarehouseInfo]:
        """List the virtual warehouses the session's role can see.

        ``SHOW WAREHOUSES`` is the documented route because there is no
        Information Schema view for warehouses; see
        :meth:`~..mixins.introspection.SnowflakeIntrospectionMixin.format_warehouse_list_query_statement`
        for the evidence, the lowercase row shape and why ``RESULT_SCAN`` is
        not used.

        Warehouses are account-level compute, not schema objects, and core's
        :class:`IntrospectionScope` has no warehouse member. The closest
        scope is ``DATABASE`` -- the account-level one -- and the ``extra``
        keeps it from colliding with both ``get_database_info`` and
        ``list_databases``. Core is not edited to add a scope this one
        backend needs; the key policy is the extension point it documents.

        Unlike the Information Schema queries, this one is documented not to
        require a running warehouse: "The command doesn't require a running
        warehouse to execute."
        """
        key = self._cache.key(IntrospectionScope.DATABASE, extra="warehouses")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = SnowflakeWarehouseListQueryStatement(self.dialect).to_sql()
        result = self.parse_warehouses(self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    def get_table_storage_metrics(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[SnowflakeTableStorageMetrics]:
        """Billed storage, row count and clustering for one live table.

        Read ``INFORMATION_SCHEMA.TABLE_STORAGE_METRICS`` joined to
        ``INFORMATION_SCHEMA.TABLES``; the columns, the join and the
        current-version filter are explained in
        :meth:`~..mixins.introspection.SnowflakeIntrospectionMixin.format_table_storage_metrics_query_statement`.

        The view belongs to the session's current **database**, so this
        method has no ``database`` argument: it answers for the database the
        session is in, exactly like the other schema introspection methods.
        *schema* defaults to the configured schema, as elsewhere; when there
        is no configured schema either, the statement does not filter by
        schema and the catalog's ``TABLE_SCHEMA`` is reported back.

        ``None`` means "no metrics row", which the documentation makes
        ambiguous on purpose: the view "is visible to other views and can be
        queried, but the queries will return no rows" for roles other than
        ``ACCOUNTADMIN``. This method cannot distinguish "the table is gone"
        from "your role cannot see the metrics", and does not pretend to.

        ``None`` is not cached, following :meth:`get_view_info`: an absent
        answer may become present after a grant or a load, and caching a
        permission-shaped ``None`` would outlive the permission.
        """
        target_schema = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE,
            table_name,
            schema=schema,
            extra="storage_metrics",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = SnowflakeTableStorageMetricsQueryStatement(
            self.dialect, table_name, schema=target_schema
        ).to_sql()
        result = self.parse_table_storage_metrics(
            self._executor.execute(sql, params), table_name, target_schema
        )
        if result is not None:
            self._cache.set(key, result)
        return result


class _SnowflakeAsyncIntrospectorExecutor:
    """Async executor wrapping synchronous Snowflake cursor operations.

    Since snowflake-connector-python has no native async driver, this
    executor runs all cursor operations in a thread pool via
    ``asyncio.run_in_executor``, mirroring the pattern used by
    AsyncSnowflakeBackend.
    """

    def __init__(self, backend: Any) -> None:
        self._backend = backend
        self._executor = getattr(backend, '_executor', None)

    async def execute(
        self, sql: str, params: tuple = ()
    ) -> List[Dict[str, Any]]:
        """Execute SQL in a thread pool and return rows as dicts."""
        loop = asyncio.get_event_loop()
        conn = self._backend._connection

        def _run():
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    return [
                        dict(zip(columns, row)) for row in cursor.fetchall()
                    ]
                return []
            finally:
                cursor.close()

        return await loop.run_in_executor(self._executor, _run)


class AsyncSnowflakeIntrospector(
    SnowflakeIntrospectorMixin, AsyncAbstractIntrospector
):
    """Asynchronous introspector for Snowflake backends.

    Uses a thread-pool-based executor since snowflake-connector-python
    has no native async support. Access via ``backend.introspector``::

        tables = await backend.introspector.list_tables()
        columns = await backend.introspector.list_columns("my_table")
    """

    def __init__(
        self,
        backend: Any,
        executor: _SnowflakeAsyncIntrospectorExecutor,
        cache: Optional[IntrospectionCache] = None,
    ) -> None:
        super().__init__(backend, executor, cache)

    async def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[IntrospectionTableInfo]:
        key = self._cache.key(
            IntrospectionScope.TABLE, table_name, schema=schema
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        tables = await self.list_tables(schema)
        table = next((t for t in tables if t.name == table_name), None)
        if table is None:
            return None

        table = copy.copy(table)
        table.columns = await self.list_columns(table_name, schema)
        table.indexes = await self.list_indexes(table_name, schema)
        table.foreign_keys = await self.list_foreign_keys(table_name, schema)
        self._cache.set(key, table)
        return table

    # ------------------------------------------------------------------ #
    # Account-level objects: databases, schemas, warehouses, storage
    # Method names and signatures match the sync class exactly.
    # ------------------------------------------------------------------ #

    async def list_databases(self) -> List[SnowflakeDatabaseInfo]:
        """List every database the session's role can see.

        Asynchronous twin of :meth:`SyncSnowflakeIntrospector.list_databases`;
        the SQL, parsing and cache key are shared through the mixin, so only
        the ``await`` differs.
        """
        key = self._cache.key(IntrospectionScope.DATABASE, extra="databases")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = SnowflakeDatabaseListQueryStatement(self.dialect).to_sql()
        result = self.parse_databases(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_schemas(
        self, database: Optional[str] = None
    ) -> List[SnowflakeSchemaInfo]:
        """List the schemas of *database*, or of the session's current one.

        Asynchronous twin of :meth:`SyncSnowflakeIntrospector.list_schemas`.
        """
        key = self._cache.key(
            IntrospectionScope.SCHEMA, database or "*", extra="schemas"
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = SnowflakeSchemaListQueryStatement(
            self.dialect, database=database
        ).to_sql()
        result = self.parse_schemas(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def list_warehouses(self) -> List[SnowflakeWarehouseInfo]:
        """List the virtual warehouses the session's role can see.

        Asynchronous twin of :meth:`SyncSnowflakeIntrospector.list_warehouses`.
        """
        key = self._cache.key(IntrospectionScope.DATABASE, extra="warehouses")
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = SnowflakeWarehouseListQueryStatement(self.dialect).to_sql()
        result = self.parse_warehouses(await self._executor.execute(sql, params))
        self._cache.set(key, result)
        return result

    async def get_table_storage_metrics(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[SnowflakeTableStorageMetrics]:
        """Billed storage, row count and clustering for one live table.

        Asynchronous twin of
        :meth:`SyncSnowflakeIntrospector.get_table_storage_metrics`, including
        the documented ``ACCOUNTADMIN`` caveat on the view and the decision
        not to cache ``None``.
        """
        target_schema = schema if schema is not None else self.default_schema
        key = self._cache.key(
            IntrospectionScope.TABLE,
            table_name,
            schema=schema,
            extra="storage_metrics",
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sql, params = SnowflakeTableStorageMetricsQueryStatement(
            self.dialect, table_name, schema=target_schema
        ).to_sql()
        result = self.parse_table_storage_metrics(
            await self._executor.execute(sql, params), table_name, target_schema
        )
        if result is not None:
            self._cache.set(key, result)
        return result

