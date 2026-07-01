"""Snowflake asynchronous backend implementation.

This module provides the async Snowflake backend using a thread pool
wrapper around the synchronous snowflake-connector-python driver,
since there is no native async driver for Snowflake.

IMPORTANT: This is a pseudo-async implementation. All I/O operations
are executed in a thread pool executor (``run_in_executor``), which
means:

1. Under high concurrency, the default ThreadPoolExecutor may become
   a bottleneck (default size: ``min(32, cpu_count + 4)``).
2. Performance benefits from uvloop or similar are lost — the
   underlying snowflake-connector-python calls remain synchronous.
3. To prevent connection storms, inject a bounded executor:

       from concurrent.futures import ThreadPoolExecutor
       backend = AsyncSnowflakeBackend(
           executor=ThreadPoolExecutor(max_workers=10),
           ...
       )

When a native async Snowflake connector becomes available, this
backend will be updated to use it transparently.
"""
import asyncio
import logging
from concurrent.futures import Executor
from typing import Any, Dict, Optional, Tuple

from rhosocial.activerecord.backend.base import AsyncStorageBackend
from rhosocial.activerecord.backend.errors import (
    ConnectionError,
    DatabaseError,
    IntegrityError,
    OperationalError,
    QueryError,
)
from rhosocial.activerecord.backend.introspection.backend_mixin import IntrospectorBackendMixin
from .config import SnowflakeConnectionConfig
from .dialect import SnowflakeDialect
from .async_transaction import AsyncSnowflakeTransactionManager
from .mixins import SnowflakeBackendMixin, AsyncSnowflakeConcurrencyMixin


class AsyncSnowflakeBackend(
    IntrospectorBackendMixin,
    SnowflakeBackendMixin,
    AsyncSnowflakeConcurrencyMixin,
    AsyncStorageBackend,
):
    """Snowflake-specific async backend implementation.

    Uses asyncio thread pool to wrap the synchronous snowflake-connector-python
    driver for async compatibility. This follows the project's sync/async parity
    principle, providing the same API surface with async/await syntax.

    Caveats:
        - All I/O operations run in a thread pool executor, not truly async.
        - High-concurrency scenarios should inject a bounded executor to
          prevent thread pool exhaustion.
        - Snowflake warehouse concurrency limits are not automatically
          respected — configure ``max_workers`` accordingly.
    """

    def __init__(self, *, executor: Optional[Executor] = None, **kwargs):
        """Initialize async Snowflake backend with connection configuration.

        Args:
            executor: Optional custom ``concurrent.futures.Executor`` for
                running synchronous snowflake-connector-python operations.
                If not provided, the default ``ThreadPoolExecutor`` is used.
                For production use, inject a bounded executor to prevent
                connection storms::

                    from concurrent.futures import ThreadPoolExecutor
                    backend = AsyncSnowflakeBackend(
                        executor=ThreadPoolExecutor(max_workers=10),
                        ...
                    )
            version: Expected Snowflake server version tuple.
                    Defaults to (8, 0, 0). Can be passed as 'version' in kwargs.
        """
        self._executor = executor
        version = kwargs.pop('version', None) or (8, 0, 0)

        connection_config = kwargs.get('connection_config')
        if connection_config is None:
            config_params = {}
            snowflake_params = [
                'host', 'port', 'database', 'username', 'password',
                'account', 'warehouse', 'schema', 'schema_name', 'role',
                'authenticator', 'private_key', 'private_key_path',
                'private_key_passphrase', 'token', 'oauth_token',
                'autocommit', 'client_session_keep_alive',
                'client_session_keep_alive_heartbeat_frequency',
                'session_parameters', 'network_timeout', 'login_timeout',
                'ssl_ca', 'ssl_cert', 'ssl_key',
                'charset', 'timezone', 'version',
                'log_queries', 'log_level',
                'pool_size', 'pool_timeout',
            ]
            for param in snowflake_params:
                if param in kwargs:
                    config_params[param] = kwargs[param]

            config_params.setdefault('autocommit', True)
            config_params['version'] = version
            kwargs['connection_config'] = SnowflakeConnectionConfig(**config_params)

        super().__init__(**kwargs)
        self._version = version
        self._dialect_cache = None
        self._register_snowflake_adapters()

    @property
    def dialect(self) -> SnowflakeDialect:
        """Get the Snowflake dialect instance."""
        return self._dialect_instance

    async def connect(self) -> None:
        """Establish a connection to the Snowflake database."""
        try:
            import snowflake.connector
            config = self.config
            conn_params = {
                'user': config.username,
                'password': config.password,
                'account': getattr(config, 'account', None),
                'database': config.database,
            }
            if getattr(config, 'warehouse', None):
                conn_params['warehouse'] = config.warehouse
            if getattr(config, 'schema', None) or getattr(config, 'schema_name', None):
                conn_params['schema'] = getattr(config, 'schema', None) or getattr(config, 'schema_name', None)
            if getattr(config, 'role', None):
                conn_params['role'] = config.role
            if getattr(config, 'authenticator', None):
                conn_params['authenticator'] = config.authenticator
            if getattr(config, 'session_parameters', None):
                conn_params['session_parameters'] = config.session_parameters

            loop = asyncio.get_event_loop()
            self._connection = await loop.run_in_executor(
                self._executor, lambda: snowflake.connector.connect(**conn_params)
            )
            self._connected = True
            self.log(logging.INFO, "Connected to Snowflake (async)")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Snowflake: {e}") from e

    async def disconnect(self) -> None:
        """Close the connection to the Snowflake database."""
        if self._connection:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self._executor, self._connection.close)
                self.log(logging.INFO, "Disconnected from Snowflake (async)")
            except Exception as e:
                self.log(logging.WARNING, f"Error disconnecting from Snowflake: {e}")
            finally:
                self._connection = None
                self._connected = False

    async def ping(self, reconnect: bool = True) -> bool:
        """Check if the connection is alive."""
        if self._connection is None:
            if reconnect:
                await self.connect()
                return True
            return False
        try:
            loop = asyncio.get_event_loop()
            cursor = await loop.run_in_executor(self._executor, self._connection.cursor)
            await loop.run_in_executor(self._executor, cursor.execute, "SELECT 1")
            cursor.close()
            return True
        except Exception:
            if reconnect:
                try:
                    await self.disconnect()
                    await self.connect()
                    return True
                except Exception:
                    return False
            return False

    async def _handle_error(self, error: Exception) -> None:
        """Handle and classify a Snowflake error."""
        category = self._classify_error(error)
        error_msg = str(error)
        if category == 'connection':
            self.log(logging.ERROR, f"Connection error: {error_msg}")
            raise ConnectionError(error_msg) from error
        elif category == 'integrity':
            self.log(logging.ERROR, f"Integrity error: {error_msg}")
            raise IntegrityError(error_msg) from error
        elif category == 'query':
            self.log(logging.ERROR, f"Query error: {error_msg}")
            raise QueryError(error_msg) from error
        elif category == 'operational':
            self.log(logging.ERROR, f"Operational error: {error_msg}")
            raise OperationalError(error_msg) from error
        else:
            self.log(logging.ERROR, f"Database error: {error_msg}")
            raise DatabaseError(error_msg) from error

    async def get_server_version(self) -> Tuple[int, ...]:
        """Get the Snowflake server version."""
        if self._server_version_cache is not None:
            return self._server_version_cache

        if self._connection:
            try:
                loop = asyncio.get_event_loop()
                cursor = await loop.run_in_executor(self._executor, self._connection.cursor)
                await loop.run_in_executor(self._executor, cursor.execute, "SELECT CURRENT_VERSION()")
                row = await loop.run_in_executor(self._executor, cursor.fetchone)
                cursor.close()
                if row:
                    version_str = row[0]
                    parts = version_str.split('.')
                    server_version = tuple(int(p) for p in parts if p.isdigit())
                    if server_version and server_version[0] > 0:
                        self._server_version_cache = server_version
                        return self._server_version_cache
            except Exception:
                pass

        return self._version

    async def introspect_and_adapt(self) -> None:
        """Introspect the Snowflake database and adapt type mappings."""
        pass

    async def _process_result_set(self, cursor, is_select, column_adapters=None, column_mapping=None):
        """Process result set with Snowflake column name normalization.

        Snowflake stores unquoted identifiers as UPPERCASE, and
        ``cursor.description`` returns them as such.  Python model
        field names are lowercase by convention, so we normalise
        column names to lowercase before building row dicts so that
        ``_map_columns_to_fields()`` and ``_remap_row_columns()`` can
        match them correctly.
        """
        if not is_select:
            return None
        try:
            rows = await cursor.fetchall()
            if not rows:
                return []
            column_names = [desc[0].strip('"').lower() for desc in cursor.description]
            final_results = []
            adapters = column_adapters or {}
            mapping = column_mapping or {}
            for row in rows:
                row_dict = dict(zip(column_names, row))
                adapted_row = self._adapt_row_types(row_dict, adapters)
                final_row = self._remap_row_columns(adapted_row, mapping)
                final_results.append(final_row)
            return final_results
        except Exception as e:
            self.logger.error(f"Error processing async result set: {str(e)}", exc_info=True)
            raise

    def _create_introspector(self):
        """Create an AsyncSnowflakeIntrospector with a thread-pool executor."""
        from .introspection import AsyncSnowflakeIntrospector, _SnowflakeAsyncIntrospectorExecutor
        return AsyncSnowflakeIntrospector(self, _SnowflakeAsyncIntrospectorExecutor(self))
