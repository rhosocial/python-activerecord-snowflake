"""Snowflake asynchronous backend implementation.

This module provides the async Snowflake backend using a thread pool
wrapper around the synchronous snowflake-connector-python driver,
since there is no native async driver for Snowflake.
"""
import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

from rhosocial.activerecord.backend.base import AsyncStorageBackend
from rhosocial.activerecord.backend.errors import (
    ConnectionError,
    DatabaseError,
    IntegrityError,
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

    Note: Since snowflake-connector-python does not provide a native async driver,
    all I/O operations are executed in a thread pool executor to avoid blocking
    the event loop.
    """

    def __init__(self, **kwargs):
        """Initialize async Snowflake backend with connection configuration.

        Args:
            version: Expected Snowflake server version tuple.
                    Defaults to (8, 0, 0). Can be passed as 'version' in kwargs.
        """
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
                None, lambda: snowflake.connector.connect(**conn_params)
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
                await loop.run_in_executor(None, self._connection.close)
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
            cursor = await loop.run_in_executor(None, self._connection.cursor)
            await loop.run_in_executor(None, cursor.execute, "SELECT 1")
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
        if category == 'connection':
            raise ConnectionError(str(error)) from error
        elif category == 'integrity':
            raise IntegrityError(str(error)) from error
        elif category == 'query':
            raise QueryError(str(error)) from error
        else:
            raise DatabaseError(str(error)) from error

    async def get_server_version(self) -> Tuple[int, ...]:
        """Get the Snowflake server version."""
        if self._server_version_cache is not None:
            return self._server_version_cache

        if self._connection:
            try:
                loop = asyncio.get_event_loop()
                cursor = await loop.run_in_executor(None, self._connection.cursor)
                await loop.run_in_executor(None, cursor.execute, "SELECT CURRENT_VERSION()")
                row = await loop.run_in_executor(None, cursor.fetchone)
                cursor.close()
                if row:
                    version_str = row[0]
                    parts = version_str.split('.')
                    self._server_version_cache = tuple(int(p) for p in parts if p.isdigit())
                    return self._server_version_cache
            except Exception:
                pass

        return self._version

    async def introspect_and_adapt(self) -> None:
        """Introspect the Snowflake database and adapt type mappings."""
        pass
