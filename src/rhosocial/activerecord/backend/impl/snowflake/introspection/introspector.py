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

    def _parse_columns(
        self,
        rows: List[Dict[str, Any]],
        table_name: str,
        schema: str,
    ) -> List[ColumnInfo]:
        columns = []
        for row in rows:
            nullable = (
                ColumnNullable.NULLABLE
                if row.get("IS_NULLABLE") == "YES"
                else ColumnNullable.NOT_NULL
            )
            data_type = row.get("DATA_TYPE") or "VARCHAR"
            columns.append(
                ColumnInfo(
                    name=row["COLUMN_NAME"],
                    table_name=table_name,
                    schema=schema,
                    ordinal_position=row.get("ORDINAL_POSITION"),
                    data_type=data_type.lower(),
                    data_type_full=data_type,
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
