"""Snowflake synchronous backend implementation.

This module provides the concrete implementation for interacting with Snowflake databases,
handling connections, queries, transactions, and type adaptations tailored for Snowflake's
specific behaviors and SQL dialect.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from rhosocial.activerecord.backend.base import StorageBackend
from rhosocial.activerecord.backend.errors import (
    ConnectionError,
    DatabaseError,
    IntegrityError,
    OperationalError,
    QueryError,
)
from rhosocial.activerecord.backend.result import QueryResult
from rhosocial.activerecord.backend.introspection.backend_mixin import IntrospectorBackendMixin
from .config import SnowflakeConnectionConfig
from .dialect import SnowflakeDialect
from .transaction import SnowflakeTransactionManager
from .mixins import SnowflakeBackendMixin, SnowflakeConcurrencyMixin


class SnowflakeBackend(
    IntrospectorBackendMixin,
    SnowflakeBackendMixin,
    SnowflakeConcurrencyMixin,
    StorageBackend,
):
    """Snowflake-specific backend implementation (synchronous).

    Uses snowflake-connector-python for database connectivity.
    """

    def __init__(self, **kwargs):
        """Initialize Snowflake backend with connection configuration.

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

    def connect(self) -> None:
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

            self._connection = snowflake.connector.connect(**conn_params)
            self._connected = True
            self.log(logging.INFO, "Connected to Snowflake")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Snowflake: {e}") from e

    def disconnect(self) -> None:
        """Close the connection to the Snowflake database."""
        if self._connection:
            try:
                self._connection.close()
                self.log(logging.INFO, "Disconnected from Snowflake")
            except Exception as e:
                self.log(logging.WARNING, f"Error disconnecting from Snowflake: {e}")
            finally:
                self._connection = None
                self._connected = False

    def ping(self, reconnect: bool = True) -> bool:
        """Check if the connection is alive.

        Args:
            reconnect: Whether to attempt reconnection if the connection is dead.

        Returns:
            True if the connection is alive, False otherwise.
        """
        if self._connection is None:
            if reconnect:
                self.connect()
                return True
            return False
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            if reconnect:
                try:
                    self.disconnect()
                    self.connect()
                    return True
                except Exception:
                    return False
            return False

    def _handle_error(self, error: Exception) -> None:
        """Handle and classify a Snowflake error.

        Args:
            error: The exception to handle.

        Raises:
            Appropriate rhosocial error based on classification.
        """
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

    def get_server_version(self) -> Tuple[int, ...]:
        """Get the Snowflake server version.

        Returns:
            Version tuple (major, minor, patch).
        """
        if self._server_version_cache is not None:
            return self._server_version_cache

        if self._connection:
            try:
                cursor = self._connection.cursor()
                cursor.execute("SELECT CURRENT_VERSION()")
                row = cursor.fetchone()
                cursor.close()
                if row:
                    version_str = row[0]
                    parts = version_str.split('.')
                    self._server_version_cache = tuple(int(p) for p in parts if p.isdigit())
                    return self._server_version_cache
            except Exception:
                pass

        return self._version

    def introspect_and_adapt(self) -> None:
        """Introspect the Snowflake database and adapt type mappings."""
        pass
