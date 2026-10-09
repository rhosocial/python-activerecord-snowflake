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
  - Result parsing: _parse_* methods in this module (pure Python, no I/O)

Key behaviours:
  - Queries INFORMATION_SCHEMA.TABLES, COLUMNS, TABLE_CONSTRAINTS,
    KEY_COLUMN_USAGE, REFERENTIAL_CONSTRAINTS, VIEWS
  - _parse_* methods are pure Python -- shared by sync and async introspectors
  - Snowflake does not support triggers; _parse_triggers returns empty list
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
from rhosocial.activerecord.backend.introspection.executor import (
    SyncIntrospectorExecutor,
)
from rhosocial.activerecord.backend.introspection.types import (
    DatabaseInfo,
    TableInfo,
    TableType,
    ColumnInfo,
    ColumnNullable,
    IndexInfo,
    IndexColumnInfo,
    IndexType,
    ForeignKeyInfo,
    ReferentialAction,
    ViewInfo,
    TriggerInfo,
    IntrospectionScope,
)


class SnowflakeIntrospectorMixin(IntrospectorMixin):
    """Mixin providing shared Snowflake-specific introspection logic.

    Both SyncSnowflakeIntrospector and AsyncSnowflakeIntrospector inherit
    from this mixin to share:
    - Default schema handling
    - Snowflake version detection
    - _parse_* implementations

    SQL generation is delegated to the Dialect layer via Expression.to_sql()
    which calls SnowflakeIntrospectionMixin.format_*_query() methods.
    """

    def _get_default_schema(self) -> str:
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

    def _get_version(self) -> tuple:
        """Return the Snowflake server version tuple from the backend."""
        return getattr(self._backend, '_version', (8, 0, 0))

    # ------------------------------------------------------------------ #
    # Parse methods — pure Python, no I/O
    # ------------------------------------------------------------------ #

    def _parse_database_info(self, rows: List[Dict[str, Any]]) -> DatabaseInfo:
        version = self._get_version()
        version_str = ".".join(str(v) for v in version)
        db_name = self._get_default_schema()

        db_row = rows[0] if rows else {}

        return DatabaseInfo(
            name=db_row.get("CATALOG_NAME", db_name),
            version=version_str,
            version_tuple=version,
            vendor="Snowflake",
        )

    def _parse_tables(
        self, rows: List[Dict[str, Any]], schema: Optional[str]
    ) -> List[TableInfo]:
        target_schema = schema if schema is not None else self._get_default_schema()
        table_type_map = {
            "BASE TABLE": TableType.BASE_TABLE,
            "VIEW": TableType.VIEW,
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
                TableInfo(
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
        the query in :meth:`~...mixins.introspection.SnowflakeIntrospectionMixin.format_column_info_query`:
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
        # on, and :meth:`_parse_data_type` is where the unreadable type is
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
    def _parse_data_type(
        composed: str, row: Dict[str, Any], dialect: Any
    ) -> Optional[Any]:
        """Read one composed catalog type string into a ``DataType``, or ``None``.

        ``ColumnInfo.parsed_data_type`` is ``None`` for exactly one reason --
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

    def _parse_columns(
        self,
        rows: List[Dict[str, Any]],
        table_name: str,
        schema: str,
    ) -> List[ColumnInfo]:
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
                ColumnInfo(
                    name=row["COLUMN_NAME"],
                    table_name=table_name,
                    schema=schema,
                    ordinal_position=row.get("ORDINAL_POSITION"),
                    data_type=data_type.lower(),
                    data_type_full=composed,
                    parsed_data_type=(
                        self._parse_data_type(composed, row, dialect)
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

    def _parse_indexes(
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

    def _parse_foreign_keys(
        self,
        rows: List[Dict[str, Any]],
        table_name: str,
        schema: str,
    ) -> List[ForeignKeyInfo]:
        action_map = {
            "NO ACTION": ReferentialAction.NO_ACTION,
            "RESTRICT": ReferentialAction.RESTRICT,
            "CASCADE": ReferentialAction.CASCADE,
            "SET NULL": ReferentialAction.SET_NULL,
            "SET DEFAULT": ReferentialAction.SET_DEFAULT,
        }
        fk_map: Dict[str, ForeignKeyInfo] = {}
        for row in rows:
            fk_name = row.get("CONSTRAINT_NAME", "")
            if fk_name not in fk_map:
                on_update_raw = (row.get("UPDATE_RULE") or "NO ACTION").upper()
                on_delete_raw = (row.get("DELETE_RULE") or "NO ACTION").upper()
                fk_map[fk_name] = ForeignKeyInfo(
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

    def _parse_views(
        self, rows: List[Dict[str, Any]], schema: str
    ) -> List[ViewInfo]:
        return [
            ViewInfo(
                name=row.get("TABLE_NAME", ""),
                schema=schema,
                definition=row.get("VIEW_DEFINITION"),
                check_option=row.get("CHECK_OPTION"),
                is_updatable=row.get("IS_UPDATABLE") == "YES",
            )
            for row in rows
        ]

    def _parse_view_info(
        self,
        rows: List[Dict[str, Any]],
        view_name: str,
        schema: str,
    ) -> Optional[ViewInfo]:
        if not rows:
            return None
        row = rows[0]
        return ViewInfo(
            name=row.get("TABLE_NAME", view_name),
            schema=schema,
            definition=row.get("VIEW_DEFINITION"),
            check_option=row.get("CHECK_OPTION"),
            is_updatable=row.get("IS_UPDATABLE") == "YES",
        )

    def _parse_triggers(
        self, rows: List[Dict[str, Any]], schema: str
    ) -> List[TriggerInfo]:
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
        self, backend: Any, executor: SyncIntrospectorExecutor
    ) -> None:
        super().__init__(backend, executor)

    def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[TableInfo]:
        key = self._make_cache_key(
            IntrospectionScope.TABLE, table_name, schema=schema
        )
        cached = self._get_cached(key)
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
        self._set_cached(key, table)
        return table


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
        self, backend: Any, executor: _SnowflakeAsyncIntrospectorExecutor
    ) -> None:
        super().__init__(backend, executor)

    async def get_table_info(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[TableInfo]:
        key = self._make_cache_key(
            IntrospectionScope.TABLE, table_name, schema=schema
        )
        cached = self._get_cached(key)
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
        self._set_cached(key, table)
        return table
