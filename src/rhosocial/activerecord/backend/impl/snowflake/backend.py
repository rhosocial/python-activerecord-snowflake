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
                    server_version = tuple(int(p) for p in parts if p.isdigit())
                    if server_version and server_version[0] > 0:
                        self._server_version_cache = server_version
                        return self._server_version_cache
            except Exception:
                pass

        return self._version

    def introspect_and_adapt(self) -> None:
        """Introspect the Snowflake database and adapt type mappings."""
        pass

    def _get_cursor(self):
        """Get a cursor from the current connection.

        Returns:
            A Snowflake cursor object.

        Raises:
            ConnectionError: If not connected to Snowflake.
        """
        if self._connection is None:
            raise ConnectionError("Not connected to Snowflake")
        return self._connection.cursor()

    def _build_query_result(self, cursor, data, duration):
        """Build QueryResult, handling fakesnow/DuckDB RETURNING quirks.

        fakesnow (DuckDB-based emulator) has two issues with RETURNING:

        1. Column names are DuckDB metadata names instead of actual column
           names: "number of rows inserted", "number of rows updated",
           "number of rows deleted", "number of multi-joined rows updated".

        2. cursor.rowcount accumulates across operations on the same cursor,
           making it unreliable for DML affected_rows.

        When we detect these metadata column names we fix both issues:
        extract last_insert_id from INSERT data, and use the result-set
        length instead of cursor.rowcount for affected_rows.
        """
        from rhosocial.activerecord.backend.result import QueryResult

        last_insert_id = getattr(cursor, "lastrowid", None)
        affected_rows = getattr(cursor, "rowcount", 0)

        # Detect fakesnow/DuckDB RETURNING quirks
        _FAKESNOW_COLUMNS = {
            "number of rows inserted",
            "number of rows updated",
            "number of rows deleted",
            "number of multi-joined rows updated",
        }

        if data and isinstance(data, list) and len(data) > 0:
            first_row = data[0]
            if isinstance(first_row, dict):
                row_keys = set(first_row.keys())
                if row_keys & _FAKESNOW_COLUMNS:
                    # fakesnow RETURNING detected
                    affected_rows = len(data)

                    # INSERT: extract PK value as last_insert_id
                    nri = first_row.get("number of rows inserted")
                    if nri is not None and isinstance(nri, int) and last_insert_id is None:
                        last_insert_id = nri

                    # Clear misleading data so core uses last_insert_id path
                    data = None

        return QueryResult(
            data=data,
            affected_rows=affected_rows,
            last_insert_id=last_insert_id,
            duration=duration,
        )

    def _process_result_set(self, cursor, is_select, column_adapters=None, column_mapping=None):
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
            rows = cursor.fetchall()
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
            self.logger.error(f"Error processing result set: {str(e)}", exc_info=True)
            raise

    def _create_introspector(self):
        """Create a SyncSnowflakeIntrospector backed by a SyncIntrospectorExecutor."""
        from rhosocial.activerecord.backend.introspection.executor import SyncIntrospectorExecutor
        from .introspection import SyncSnowflakeIntrospector
        return SyncSnowflakeIntrospector(self, SyncIntrospectorExecutor(self))
