"""Snowflake dialect-specific Mixin implementations.

This module provides shared non-I/O mixin classes for the Snowflake backend,
including backend mixin, transaction mixin, concurrency mixins, and
Snowflake-specific feature mixins for time travel, VARIANT, ARRAY,
CLONE, and stage support.
"""
import logging
from typing import Any, Dict, Optional, Tuple, Type

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
