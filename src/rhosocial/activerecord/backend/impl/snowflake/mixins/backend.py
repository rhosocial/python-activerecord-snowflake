# src/rhosocial/activerecord/backend/impl/snowflake/mixins/backend.py
"""SnowflakeBackendMixin — shared non-I/O backend logic.

This mixin contains all non-I/O logic shared between sync and async
Snowflake backends, including adapter registration, error classification,
and dialect property management.
"""
import logging
from typing import Any, Dict, Optional, Tuple, Type

from rhosocial.activerecord.backend.errors import DatabaseError
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter

from ..adapters import (
    SnowflakeArrayAdapter,
    SnowflakeBooleanAdapter,
    SnowflakeDecimalAdapter,
    SnowflakeTimestampAdapter,
    SnowflakeVariantAdapter,
)

# Driver messages are the last-resort signal, after driver code and exception
# class (see the error-taxonomy backend mapping rules). Snowflake declares
# UNIQUE constraints but does not enforce them by default, and has no row-level
# deadlock/lock-wait semantics to classify, so lock and deadlock failures are
# deliberately absent from this taxonomy: they fall back to the driver's own
# Operational/Programming/Database class instead of LockError/DeadlockError.
_INTEGRITY_SIGNALS = (
    'already exists',
    'duplicate',
    'unique constraint',
    'unique violation',
    'primary key',
    'foreign key',
    'not null',
    'non-nullable',
    'null result',
    'cannot be null',
    'constraint violation',
    'constraint failed',
)
_CONNECTION_SIGNALS = (
    'incorrect username or password',
    'invalid username',
    'invalid password',
    'authentication',
    'login',
    'credential',
    'failed to connect',
    'connect',
    'connection',
    'network',
    'timeout',
    'timed out',
    'handshake',
    'refused',
    'service unavailable',
    'gateway timeout',
    'session is invalid',
    'session has expired',
    'connection is closed',
    'temporarily unavailable',
    'too many requests',
)
_QUERY_SIGNALS = (
    'syntax error',
    'invalid identifier',
    'invalid object',
    'invalid column',
    'unknown column',
    'unknown table',
    'does not exist',
    'not found',
    'sql compilation error',
)
_PERMISSION_SIGNALS = (
    'permission',
    'not authorized',
    'unauthorized',
    'access denied',
    'not allowed',
    'privilege',
)
_INVALID_CREDENTIAL_SIGNALS = (
    'incorrect username or password',
    'invalid username',
    'invalid password',
    'authentication',
    'login',
    'credential',
    'user is disabled',
    'account is locked',
)


class SnowflakeBackendMixin:
    """Shared non-I/O methods for Snowflake backend implementations.

    This mixin contains all non-I/O logic shared between sync and async
    Snowflake backends, including adapter registration, error classification,
    and dialect property management.
    """

    def _get_logger_name(self) -> str:
        """Return the canonical Snowflake backend logger name.

        Both the synchronous and asynchronous backends use the same library
        logger, so application logging configuration has one name to target.
        """
        return "rhosocial.activerecord.backend.snowflake"

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

    @staticmethod
    def _matches(message: str, signals: Tuple[str, ...]) -> bool:
        """Return whether any lowercase message signal occurs in the message."""
        return any(signal in message for signal in signals)

    def _classify_error(self, error: Exception) -> str:
        """Classify a Snowflake error into a standard error category.

        Framework errors (``rhosocial.activerecord.backend.errors.DatabaseError``
        and every subclass, including ``ConnectionError``,
        ``TypeConversionError`` and ``TransactionError``) are returned as
        ``'framework'`` before any driver inspection. They already carry the
        intended taxonomy type, and their messages can contain words such as
        ``connection`` or ``timeout`` that the message fallback would otherwise
        misread as a driver category.

        For everything else, uses snowflake.connector.errors exception type
        hierarchy for accurate classification, then driver messages for the
        cases the class alone cannot express (unique/not-null constraints raised
        as ProgrammingError, permission denials, login failures). String
        matching remains the fallback for non-Snowflake exceptions.

        Snowflake has weak locking semantics: lock waits and deadlocks are not
        translated to LockError/DeadlockError; they keep the driver's own
        operational/programming category.

        Args:
            error: The exception to classify.

        Returns:
            String category: 'connection', 'integrity', 'query',
            'operational', 'framework', or 'unknown'
        """
        # Short-circuit before the driver import: framework errors must not be
        # re-translated, and must not reach the message fallback at the end of
        # this method.
        if isinstance(error, DatabaseError):
            return 'framework'

        import snowflake.connector.errors as _errors
        SnowflakeError = _errors.Error
        SnowflakeInterfaceError = _errors.InterfaceError
        SnowflakeDatabaseError = _errors.DatabaseError
        SnowflakeOperationalError = _errors.OperationalError
        SnowflakeProgrammingError = _errors.ProgrammingError
        SnowflakeIntegrityError = _errors.IntegrityError
        SnowflakeDataError = _errors.DataError
        SnowflakeNotSupportedError = _errors.NotSupportedError
        # HTTP-level errors were added in newer connector versions; older
        # ones (e.g. the wheel resolved on Python 3.8) lack them entirely.
        # Fall back to a private sentinel that matches nothing — NEVER to a
        # base class like Error, or every subclass would hit this branch.
        _missing = type("_MissingSnowflakeError", (Exception,), {})
        SnowflakeHttpError = getattr(_errors, "HttpError", _missing)
        SnowflakeGatewayTimeoutError = getattr(_errors, "GatewayTimeoutError", _missing)
        SnowflakeRequestTimeoutError = getattr(_errors, "RequestTimeoutError", _missing)
        SnowflakeServiceUnavailableError = getattr(_errors, "ServiceUnavailableError", _missing)

        message = str(error).lower()

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
            if self._matches(message, _CONNECTION_SIGNALS):
                return 'connection'
            return 'operational'

        if isinstance(error, (
            SnowflakeProgrammingError,
            SnowflakeDataError,
            SnowflakeNotSupportedError,
        )):
            # Permission failures also arrive as ProgrammingError; keep them
            # in the generic DatabaseError bucket rather than QueryError.
            if self._matches(message, _PERMISSION_SIGNALS):
                return 'unknown'
            if self._matches(message, _INTEGRITY_SIGNALS):
                return 'integrity'
            return 'query'

        if isinstance(error, SnowflakeHttpError):
            return 'connection'

        if isinstance(error, (SnowflakeDatabaseError, SnowflakeError)):
            if self._matches(message, _INTEGRITY_SIGNALS):
                return 'integrity'
            if self._matches(message, _CONNECTION_SIGNALS):
                return 'connection'
            if self._matches(message, _QUERY_SIGNALS):
                return 'query'
            return 'unknown'

        if self._matches(message, _CONNECTION_SIGNALS):
            return 'connection'
        if self._matches(message, _INTEGRITY_SIGNALS):
            return 'integrity'
        if self._matches(message, _QUERY_SIGNALS):
            return 'query'

        return 'unknown'

    def _is_transient_infrastructure_error(self, error: Exception) -> bool:
        """Return whether a connection/operational failure should clear on retry.

        Only network timeouts, HTTP gateway/service failures and lost
        connections are transient. Invalid credentials, permission denials,
        syntax errors and integrity violations are not: retrying them cannot
        succeed without an external change.
        """
        message = str(error).lower()
        if self._matches(message, _INVALID_CREDENTIAL_SIGNALS):
            return False

        try:
            import snowflake.connector.errors as _errors
        except ImportError:  # pragma: no cover - driver optional at import time
            _errors = None

        if _errors is not None:
            transient_types = tuple(
                cls for cls in (
                    getattr(_errors, "GatewayTimeoutError", None),
                    getattr(_errors, "RequestTimeoutError", None),
                    getattr(_errors, "ServiceUnavailableError", None),
                ) if cls is not None
            )
            if transient_types and isinstance(error, transient_types):
                return True
            http_error = getattr(_errors, "HttpError", None)
            if http_error is not None and isinstance(error, http_error):
                return True
            # InterfaceError covers driver-internal protocol failures; the
            # existing contract keeps it a non-transient ConnectionError.
            interface_error = getattr(_errors, "InterfaceError", None)
            if interface_error is not None and isinstance(error, interface_error):
                return False

        return self._matches(message, _CONNECTION_SIGNALS)

    def _resolve_error_mapping(self, error: Exception, category: str) -> Tuple[str, Any]:
        """Decide the concrete taxonomy target and retry hint for a category.

        Framework errors are never mapped: they return ``'framework'`` so
        :meth:`_handle_error` can re-raise the original instance unchanged.
        This check also covers ``category`` values computed elsewhere, because
        the type of ``error`` is the authoritative signal.

        Args:
            error: The driver exception being translated.
            category: Coarse category returned by :meth:`_classify_error`.

        Returns:
            ``(target, transient)`` where target is one of ``connection``,
            ``operational``, ``integrity``, ``query``, ``framework`` or
            ``database``. ``transient`` is ``True``/``False`` for infrastructure
            failures and ``None`` otherwise.
        """
        if isinstance(error, DatabaseError) or category == 'framework':
            return 'framework', None
        if category == 'integrity':
            return 'integrity', False
        if category == 'query':
            return 'query', False
        if category == 'operational':
            return 'operational', self._is_transient_infrastructure_error(error)
        if category == 'connection':
            if self._is_transient_infrastructure_error(error):
                return 'operational', True
            return 'connection', False
        return 'database', None

    @staticmethod
    def _error_diagnostics(error: Exception, transient: Any) -> Dict[str, Any]:
        """Build ``attach_diagnostics`` keyword arguments for a driver exception."""
        return {
            'operation': 'execute',
            'driver_code': getattr(error, 'errno', None),
            'sqlstate': getattr(error, 'sqlstate', None),
            'backend': 'snowflake',
            'transient': transient,
        }

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