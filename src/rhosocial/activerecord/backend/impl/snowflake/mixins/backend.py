# src/rhosocial/activerecord/backend/impl/snowflake/mixins/backend.py
"""SnowflakeBackendMixin — shared non-I/O backend logic.

This mixin contains all non-I/O logic shared between sync and async
Snowflake backends, including adapter registration, error classification,
and dialect property management.
"""
import logging
from typing import Any, Dict, Optional, Tuple, Type

from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter

from ..adapters import (
    SnowflakeArrayAdapter,
    SnowflakeBooleanAdapter,
    SnowflakeDecimalAdapter,
    SnowflakeTimestampAdapter,
    SnowflakeVariantAdapter,
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
            from ..dialect import SnowflakeDialect
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

        if isinstance(error, SnowflakeIntegrityError):
            return 'integrity'

        if isinstance(error, (
            SnowflakeInterfaceError,
            SnowflakeGatewayTimeoutError,
            SnowflakeRequestTimeoutError,
            SnowflakeServiceUnavailableError,
        )):
            return 'connection'

        if isinstance(error, SnowflakeOperationalError):
            error_msg = str(error).lower()
            if any(s in error_msg for s in [
                'connection', 'network', 'timeout',
                'handshake', 'connect', 'refused',
            ]):
                return 'connection'
            return 'operational'

        if isinstance(error, SnowflakeProgrammingError):
            return 'query'

        if isinstance(error, SnowflakeDataError):
            return 'query'

        if isinstance(error, SnowflakeNotSupportedError):
            return 'query'

        if isinstance(error, SnowflakeHttpError):
            return 'connection'

        if isinstance(error, SnowflakeDatabaseError):
            return 'unknown'

        if isinstance(error, SnowflakeError):
            return 'unknown'

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
            (bool, int),
            (datetime, str),
            (date, str),
            (time, str),
            (Decimal, float),
            (UUID, str),
            (dict, str),
            (list, str),
            (Enum, str),
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