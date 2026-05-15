"""Mock-based tests for Snowflake backend.

Tests backend behavior using mocked snowflake.connector to avoid
requiring a real Snowflake instance.
"""
from unittest.mock import MagicMock, patch

import pytest

from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.async_backend import AsyncSnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.adapters import (
    SnowflakeVariantAdapter,
    SnowflakeArrayAdapter,
    SnowflakeBooleanAdapter,
    SnowflakeDecimalAdapter,
    SnowflakeTimestampAdapter,
)


class TestSnowflakeBackendMocked:
    """Test SnowflakeBackend with mocked connector."""

    def test_backend_instantiation(self):
        backend = SnowflakeBackend(
            account="test_account",
            database="test_db",
            username="test_user",
            password="test_pass",
        )
        assert backend is not None

    @patch("snowflake.connector.connect")
    def test_connect_success(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        backend = SnowflakeBackend(
            connection_config=SnowflakeConnectionConfig(
                account="test_account",
                database="test_db",
                username="test_user",
                password="test_pass",
                warehouse="COMPUTE_WH",
                role="SYSADMIN",
            )
        )
        backend.connect()

        assert backend._connection is not None
        mock_connect.assert_called_once()

    @patch("snowflake.connector.connect")
    def test_disconnect(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        backend = SnowflakeBackend(
            connection_config=SnowflakeConnectionConfig(
                account="test_account",
                database="test_db",
                username="test_user",
                password="test_pass",
            )
        )
        backend.connect()
        backend.disconnect()

        mock_conn.close.assert_called_once()
        assert backend._connection is None

    @patch("snowflake.connector.connect")
    def test_ping_success(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        backend = SnowflakeBackend(
            connection_config=SnowflakeConnectionConfig(
                account="test_account",
                database="test_db",
                username="test_user",
                password="test_pass",
            )
        )
        backend.connect()
        result = backend.ping(reconnect=False)

        assert result is True

    @patch("snowflake.connector.connect")
    def test_get_server_version(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("8.42.0",)
        mock_cursor.execute.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        backend = SnowflakeBackend(
            connection_config=SnowflakeConnectionConfig(
                account="test_account",
                database="test_db",
                username="test_user",
                password="test_pass",
            )
        )
        backend._connection = mock_conn
        version = backend.get_server_version()

        assert isinstance(version, tuple)
        assert len(version) >= 2


class TestSnowflakeBackendErrorClassification:
    """Test error classification in SnowflakeBackendMixin."""

    def setup_method(self):
        self.backend = SnowflakeBackend(
            account="test_account",
            database="test_db",
            username="test_user",
            password="test_pass",
        )

    def test_classify_connection_error(self):
        assert self.backend._classify_error(Exception("connection refused")) == "connection"

    def test_classify_network_error(self):
        assert self.backend._classify_error(Exception("network timeout")) == "connection"

    def test_classify_integrity_error(self):
        assert self.backend._classify_error(Exception("unique constraint violation")) == "integrity"

    def test_classify_duplicate_key_error(self):
        assert self.backend._classify_error(Exception("duplicate key value")) == "integrity"

    def test_classify_query_error(self):
        assert self.backend._classify_error(Exception("syntax error")) == "query"

    def test_classify_not_found_error(self):
        assert self.backend._classify_error(Exception("table does not exist")) == "query"

    def test_classify_unknown_error(self):
        assert self.backend._classify_error(Exception("something unexpected")) == "unknown"


class TestSnowflakeBackendAdapters:
    """Test adapter registration in backend."""

    def test_adapters_registered(self):
        backend = SnowflakeBackend(
            account="test_account",
            database="test_db",
            username="test_user",
            password="test_pass",
        )
        registry = backend.adapter_registry
        assert registry is not None


class TestSnowflakeBackendDialect:
    """Test dialect property."""

    def test_dialect_returns_snowflake_dialect(self):
        backend = SnowflakeBackend(
            account="test_account",
            database="test_db",
            username="test_user",
            password="test_pass",
        )
        dialect = backend.dialect
        assert isinstance(dialect, SnowflakeDialect)


class TestSnowflakeBackendDefaultSchema:
    """Test default schema behavior."""

    def test_default_schema_from_config(self):
        backend = SnowflakeBackend(
            connection_config=SnowflakeConnectionConfig(
                account="test_account",
                database="test_db",
                username="test_user",
                password="test_pass",
                schema="PUBLIC",
            )
        )
        assert backend.get_default_schema() == "PUBLIC"

    def test_default_schema_none_when_not_set(self):
        backend = SnowflakeBackend(
            connection_config=SnowflakeConnectionConfig(
                account="test_account",
                database="test_db",
                username="test_user",
                password="test_pass",
            )
        )
        assert backend.get_default_schema() is None
