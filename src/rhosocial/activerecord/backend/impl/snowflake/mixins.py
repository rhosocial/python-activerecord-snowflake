"""Snowflake dialect-specific Mixin implementations.

This module provides shared non-I/O mixin classes for the Snowflake backend,
including backend mixin, transaction mixin, concurrency mixins, and
Snowflake-specific feature mixins for time travel, VARIANT, ARRAY,
CLONE, and stage support.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple, Type, TYPE_CHECKING

from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter
from rhosocial.activerecord.backend.protocols import ConcurrencyHint
from rhosocial.activerecord.backend.transaction import IsolationLevel

from .adapters import (
    SnowflakeVariantAdapter,
    SnowflakeArrayAdapter,
    SnowflakeBooleanAdapter,
    SnowflakeDecimalAdapter,
    SnowflakeTimestampAdapter,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.introspection.types import IntrospectionScope
    from rhosocial.activerecord.backend.expression.introspection import (
        DatabaseInfoExpression,
        TableListExpression,
        ColumnInfoExpression,
        IndexInfoExpression,
        ForeignKeyExpression,
        ViewListExpression,
        ViewInfoExpression,
        TriggerListExpression,
    )


class SnowflakeBackendMixin:
    """Shared non-I/O methods for Snowflake backend implementations.

    This mixin contains all non-I/O logic shared between sync and async
    Snowflake backends, including adapter registration, error classification,
    and dialect property management.
    """

    def _register_snowflake_adapters(self) -> None:
        """Register Snowflake-specific type adapters."""
        adapters = [
            SnowflakeVariantAdapter(),
            SnowflakeArrayAdapter(),
            SnowflakeBooleanAdapter(),
            SnowflakeDecimalAdapter(),
            SnowflakeTimestampAdapter(),
        ]

        for adapter in adapters:
            for py_type, db_types in adapter.supported_types.items():
                for db_type in db_types:
                    self.adapter_registry.register(adapter, py_type, db_type, allow_override=True)

    @property
    def _dialect_instance(self) -> Any:
        """Lazy initialization of SnowflakeDialect instance."""
        if not hasattr(self, '_dialect_cache') or self._dialect_cache is None:
            from .dialect import SnowflakeDialect
            version = self.get_server_version() if self._connection else (8, 0, 0)
            self._dialect_cache = SnowflakeDialect(version=version)
        return self._dialect_cache

    def _classify_error(self, error: Exception) -> str:
        """Classify a Snowflake error into a standard error category.

        Uses snowflake.connector.errors exception type hierarchy for
        accurate classification, with string matching as fallback for
        non-Snowflake exceptions.

        Args:
            error: The exception to classify.

        Returns:
            String category: 'connection', 'integrity', 'query',
            'operational', or 'unknown'
        """
        from snowflake.connector.errors import (
            Error as SnowflakeError,
            InterfaceError as SnowflakeInterfaceError,
            DatabaseError as SnowflakeDatabaseError,
            OperationalError as SnowflakeOperationalError,
            ProgrammingError as SnowflakeProgrammingError,
            IntegrityError as SnowflakeIntegrityError,
            DataError as SnowflakeDataError,
            NotSupportedError as SnowflakeNotSupportedError,
            HttpError as SnowflakeHttpError,
            GatewayTimeoutError as SnowflakeGatewayTimeoutError,
            RequestTimeoutError as SnowflakeRequestTimeoutError,
            ServiceUnavailableError as SnowflakeServiceUnavailableError,
        )

        # IntegrityError is most specific, check first
        if isinstance(error, SnowflakeIntegrityError):
            return 'integrity'

        # Connection-related errors (network, timeout, service unavailable)
        if isinstance(error, (
            SnowflakeInterfaceError,
            SnowflakeGatewayTimeoutError,
            SnowflakeRequestTimeoutError,
            SnowflakeServiceUnavailableError,
        )):
            return 'connection'

        # OperationalError spans both connection and operational issues;
        # use string matching to distinguish
        if isinstance(error, SnowflakeOperationalError):
            error_msg = str(error).lower()
            if any(s in error_msg for s in [
                'connection', 'network', 'timeout',
                'handshake', 'connect', 'refused',
            ]):
                return 'connection'
            return 'operational'

        # ProgrammingError: syntax errors, invalid SQL, object not found
        if isinstance(error, SnowflakeProgrammingError):
            return 'query'

        # DataError: data processing errors (type mismatch, value out of range)
        if isinstance(error, SnowflakeDataError):
            return 'query'

        # NotSupportedError: unsupported feature usage
        if isinstance(error, SnowflakeNotSupportedError):
            return 'query'

        # HttpError: network-level, classify as connection
        if isinstance(error, SnowflakeHttpError):
            return 'connection'

        # Generic Snowflake DatabaseError fallback
        if isinstance(error, SnowflakeDatabaseError):
            return 'unknown'

        # Generic Snowflake Error fallback
        if isinstance(error, SnowflakeError):
            return 'unknown'

        # Non-Snowflake exceptions: fallback to string matching
        error_msg = str(error).lower()
        if any(s in error_msg for s in [
            'connection', 'network', 'timeout', 'handshake',
        ]):
            return 'connection'
        if any(s in error_msg for s in [
            'unique', 'constraint', 'duplicate',
            'primary key', 'foreign key',
        ]):
            return 'integrity'
        if any(s in error_msg for s in [
            'syntax', 'invalid', 'not found', 'does not exist',
        ]):
            return 'query'

        return 'unknown'

    def get_default_adapter_suggestions(self) -> Dict[Type, Tuple[SQLTypeAdapter, Type]]:
        """Provide default type adapter suggestions for Snowflake.

        Maps Python types to their Snowflake-compatible driver representations
        by retrieving registered adapters from the adapter_registry.
        Types that are natively compatible (str, int, float) are omitted.
        """
        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID
        from enum import Enum

        suggestions: Dict[Type, Tuple[SQLTypeAdapter, Type]] = {}

        type_mappings = [
            (bool, int),        # Python bool -> DB driver int (Snowflake BOOLEAN stored as int)
            (datetime, str),    # Python datetime -> DB driver str (Snowflake TIMESTAMP)
            (date, str),        # Python date -> DB driver str (Snowflake DATE)
            (time, str),        # Python time -> DB driver str (Snowflake TIME)
            (Decimal, float),   # Python Decimal -> DB driver float (Snowflake NUMBER)
            (UUID, str),        # Python UUID -> DB driver str (Snowflake VARCHAR)
            (dict, str),        # Python dict -> DB driver str (Snowflake VARIANT)
            (list, str),        # Python list -> DB driver str (Snowflake ARRAY)
            (Enum, str),        # Python Enum -> DB driver str (Snowflake VARCHAR)
        ]

        for py_type, db_type in type_mappings:
            adapter = self.adapter_registry.get_adapter(py_type, db_type)
            if adapter:
                suggestions[py_type] = (adapter, db_type)
            else:
                self.log(
                    logging.DEBUG,
                    f"No adapter found for ({py_type.__name__}, {db_type.__name__}). "
                    "Suggestion will not be provided for this type."
                )

        return suggestions

    def get_default_schema(self) -> Optional[str]:
        """Get the default schema for Snowflake.

        Snowflake uses a three-level namespace: database.schema.table.
        The default schema can be set in the connection config.
        """
        if hasattr(self, 'config') and self.config:
            return getattr(self.config, 'schema', None) or getattr(self.config, 'schema_name', None)
        return None


# ========== Snowflake-Specific Feature Mixins ==========

class SnowflakeTimeTravelMixin:
    """Mixin for Snowflake time travel query support."""

    def supports_time_travel(self) -> bool:
        """Snowflake supports time travel queries."""
        return True

    def format_time_travel_at_timestamp(self, timestamp: str) -> str:
        """Format AT(TIMESTAMP => ...) clause."""
        return f"AT(TIMESTAMP => '{timestamp}')"

    def format_time_travel_at_offset(self, seconds: int) -> str:
        """Format AT(OFFSET => ...) clause."""
        return f"AT(OFFSET => {seconds})"

    def format_time_travel_before_timestamp(self, timestamp: str) -> str:
        """Format BEFORE(TIMESTAMP => ...) clause."""
        return f"BEFORE(TIMESTAMP => '{timestamp}')"


class SnowflakeVariantMixin:
    """Mixin for Snowflake VARIANT semi-structured data type support."""

    def supports_variant_type(self) -> bool:
        """Snowflake supports VARIANT type."""
        return True

    def format_variant_path_access(self, column: str, path: str) -> str:
        """Format VARIANT path access expression using colon notation."""
        return f'{column}:{path}'

    def format_variant_cast(self, column: str, path: str, target_type: str) -> str:
        """Format VARIANT path access with explicit cast."""
        return f'{column}:{path}::{target_type}'


class SnowflakeArrayMixin:
    """Mixin for Snowflake ARRAY type support."""

    def supports_array_type(self) -> bool:
        """Snowflake supports ARRAY type."""
        return True

    def format_array_construct(self, elements: str) -> str:
        """Format array construction expression."""
        return f'ARRAY_CONSTRUCT({elements})'

    def format_array_access(self, array_expr: str, index: str) -> str:
        """Format array element access expression."""
        return f'{array_expr}[{index}]'


class SnowflakeCloneMixin:
    """Mixin for Snowflake CLONE operation support."""

    def supports_clone(self) -> bool:
        """Snowflake supports CLONE operations."""
        return True

    def format_clone_table(self, target: str, source: str) -> str:
        """Format CREATE TABLE ... CLONE statement."""
        return f'CREATE TABLE {target} CLONE {source}'


class SnowflakeStageMixin:
    """Mixin for Snowflake stage (data staging area) support."""

    def supports_stages(self) -> bool:
        """Snowflake supports stages."""
        return True

    def format_copy_into_table(
        self, table: str, stage: str, file_format: Optional[str] = None
    ) -> str:
        """Format COPY INTO table FROM stage statement."""
        sql = f'COPY INTO {table} FROM @{stage}'
        if file_format:
            sql += f' FILE_FORMAT = ({file_format})'
        return sql


# ========== Transaction & Concurrency Mixins ==========

class SnowflakeTransactionMixin:
    """Shared non-I/O transaction logic for Snowflake.

    Snowflake supports READ COMMITTED isolation level only.
    ALTER SESSION SET TRANSACTION_ISOLATION_LEVEL is not needed
    as Snowflake only supports READ COMMITTED.
    """

    _ISOLATION_LEVELS = {
        IsolationLevel.READ_COMMITTED: 'READ COMMITTED',
    }

    def _build_set_isolation_sql(self, level: IsolationLevel) -> Tuple[str, tuple]:
        """Build SQL to set transaction isolation level.

        Snowflake only supports READ COMMITTED. If another level is requested,
        we warn and use READ COMMITTED.

        Args:
            level: The desired isolation level.

        Returns:
            Tuple of (SQL string, parameters)
        """
        if level not in self._ISOLATION_LEVELS:
            import warnings
            warnings.warn(
                f"Snowflake only supports READ COMMITTED isolation level. "
                f"Requested level {level} is not supported.",
                RuntimeWarning,
                stacklevel=3,
            )
        # Snowflake uses READ COMMITTED by default, no SET TRANSACTION needed
        return ("", ())

    def _build_begin_sql(self) -> Tuple[str, tuple]:
        """Build BEGIN TRANSACTION SQL for Snowflake.

        Returns:
            Tuple of (SQL string, parameters)
        """
        return ("BEGIN", ())


class SnowflakeConcurrencyMixin:
    """Snowflake concurrency hint (sync)."""

    def _fetch_concurrency_hint(self) -> ConcurrencyHint:
        """Snowflake uses warehouse-based concurrency.

        Returns:
            ConcurrencyHint indicating Snowflake's concurrency model.
        """
        return ConcurrencyHint.ADVISORY


class AsyncSnowflakeConcurrencyMixin:
    """Snowflake concurrency hint (async)."""

    def _fetch_concurrency_hint(self) -> ConcurrencyHint:
        """Snowflake uses warehouse-based concurrency.

        Returns:
            ConcurrencyHint indicating Snowflake's concurrency model.
        """
        return ConcurrencyHint.ADVISORY


# ========== Introspection Mixin ==========

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
    """

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

    # ========== Query Formatting ==========

    def format_database_info_query(
        self, expr: "DatabaseInfoExpression"
    ) -> Tuple[str, tuple]:
        """Format database information query using context functions."""
        sql = (
            "SELECT CURRENT_DATABASE() AS CATALOG_NAME, "
            "CURRENT_VERSION() AS SERVER_VERSION"
        )
        return (sql, ())

    def format_table_list_query(
        self, expr: "TableListExpression"
    ) -> Tuple[str, tuple]:
        """Format table list query using INFORMATION_SCHEMA.TABLES."""
        params = expr.get_params()
        schema = params.get("schema", "")
        include_views = params.get("include_views", True)
        include_system = params.get("include_system", False)
        table_type = params.get("table_type")

        conditions = ["TABLE_SCHEMA = %s"]
        sql_params: list = [schema]

        if not include_system:
            conditions.append(
                "TABLE_SCHEMA NOT IN ('information_schema', 'PUBLIC')"
            )
        if not include_views:
            conditions.append("TABLE_TYPE = 'BASE TABLE'")
        if table_type:
            conditions.append("TABLE_TYPE = %s")
            sql_params.append(table_type)

        where = " AND ".join(conditions)
        sql = (
            "SELECT TABLE_NAME, TABLE_TYPE, COMMENT "
            f"FROM INFORMATION_SCHEMA.TABLES WHERE {where} "
            "ORDER BY TABLE_NAME"
        )
        return (sql, tuple(sql_params))

    def format_column_info_query(
        self, expr: "ColumnInfoExpression"
    ) -> Tuple[str, tuple]:
        """Format column information query using INFORMATION_SCHEMA.COLUMNS."""
        params = expr.get_params()
        table_name = params.get("table_name", "")
        schema = params.get("schema", "")

        sql = (
            "SELECT COLUMN_NAME, ORDINAL_POSITION, COLUMN_DEFAULT, IS_NULLABLE, "
            "DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE, "
            "COLLATION_NAME, COMMENT "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION"
        )
        return (sql, (schema, table_name))

    def format_index_info_query(
        self, expr: "IndexInfoExpression"
    ) -> Tuple[str, tuple]:
        """Format index information query using constraints.

        Snowflake does not have traditional indexes. This queries
        TABLE_CONSTRAINTS + KEY_COLUMN_USAGE for PRIMARY KEY and UNIQUE
        constraints, which serve as the closest analog.
        """
        params = expr.get_params()
        table_name = params.get("table_name", "")
        schema = params.get("schema", "")

        sql = (
            "SELECT tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE, "
            "kcu.COLUMN_NAME, kcu.ORDINAL_POSITION "
            "FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
            "  ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
            "  AND tc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA "
            "WHERE tc.TABLE_SCHEMA = %s AND tc.TABLE_NAME = %s "
            "  AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE') "
            "ORDER BY tc.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
        )
        return (sql, (schema, table_name))

    def format_foreign_key_query(
        self, expr: "ForeignKeyExpression"
    ) -> Tuple[str, tuple]:
        """Format foreign key information query.

        Joins REFERENTIAL_CONSTRAINTS, KEY_COLUMN_USAGE, and
        TABLE_CONSTRAINTS to resolve referenced table and columns.
        """
        params = expr.get_params()
        table_name = params.get("table_name", "")
        schema = params.get("schema", "")

        sql = (
            "SELECT rc.CONSTRAINT_NAME, rc.UPDATE_RULE, rc.DELETE_RULE, "
            "kcu.COLUMN_NAME, kcu.ORDINAL_POSITION, "
            "utc.TABLE_NAME AS REFERENCED_TABLE_NAME, "
            "ukcu.COLUMN_NAME AS REFERENCED_COLUMN_NAME "
            "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
            "  ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
            "  AND rc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA "
            "JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS utc "
            "  ON rc.UNIQUE_CONSTRAINT_NAME = utc.CONSTRAINT_NAME "
            "  AND rc.UNIQUE_CONSTRAINT_SCHEMA = utc.CONSTRAINT_SCHEMA "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ukcu "
            "  ON rc.UNIQUE_CONSTRAINT_NAME = ukcu.CONSTRAINT_NAME "
            "  AND rc.UNIQUE_CONSTRAINT_SCHEMA = ukcu.CONSTRAINT_SCHEMA "
            "  AND kcu.POSITION_IN_UNIQUE_CONSTRAINT = ukcu.ORDINAL_POSITION "
            "WHERE rc.CONSTRAINT_SCHEMA = %s "
            "  AND kcu.TABLE_NAME = %s "
            "ORDER BY rc.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
        )
        return (sql, (schema, table_name))

    def format_view_list_query(
        self, expr: "ViewListExpression"
    ) -> Tuple[str, tuple]:
        """Format view list query using INFORMATION_SCHEMA.VIEWS."""
        params = expr.get_params()
        schema = params.get("schema", "")
        include_system = params.get("include_system", False)

        conditions = ["TABLE_SCHEMA = %s"]
        sql_params: list = [schema]

        if not include_system:
            conditions.append(
                "TABLE_SCHEMA NOT IN ('information_schema', 'PUBLIC')"
            )

        where = " AND ".join(conditions)
        sql = (
            "SELECT TABLE_NAME, VIEW_DEFINITION, CHECK_OPTION, IS_UPDATABLE "
            f"FROM INFORMATION_SCHEMA.VIEWS WHERE {where} "
            "ORDER BY TABLE_NAME"
        )
        return (sql, tuple(sql_params))

    def format_view_info_query(
        self, expr: "ViewInfoExpression"
    ) -> Tuple[str, tuple]:
        """Format single view information query."""
        params = expr.get_params()
        view_name = params.get("view_name", "")
        schema = params.get("schema", "")

        sql = (
            "SELECT TABLE_NAME, VIEW_DEFINITION, CHECK_OPTION, IS_UPDATABLE "
            "FROM INFORMATION_SCHEMA.VIEWS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s"
        )
        return (sql, (schema, view_name))

    def format_trigger_list_query(
        self, expr: "TriggerListExpression"
    ) -> Tuple[str, tuple]:
        """Snowflake does not support triggers; return empty result."""
        return ("SELECT 1 WHERE 1 = 0", ())

    def format_trigger_info_query(
        self, expr
    ) -> Tuple[str, tuple]:
        """Snowflake does not support triggers; return empty result."""
        return ("SELECT 1 WHERE 1 = 0", ())
