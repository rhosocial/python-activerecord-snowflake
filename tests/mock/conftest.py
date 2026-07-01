"""Mock connector fixtures for Layer 2 tests.

Provides mock snowflake.connector connection and cursor objects,
plus a configured SnowflakeBackend that can be used to test
AR model behavior without any real DB connection.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from rhosocial.activerecord.backend.impl.snowflake import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig


@pytest.fixture
def mock_cursor():
    """Construct a configurable mock cursor."""
    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    cursor.description = []
    cursor.rowcount = 0
    cursor.sfqid = "mock-query-id-0001"
    return cursor


@pytest.fixture
def mock_connection(mock_cursor):
    """Construct a mock snowflake connection."""
    conn = MagicMock()
    conn.cursor.return_value = mock_cursor
    conn.__enter__ = lambda s: s
    conn.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture
def mock_backend(mock_connection):
    """Construct a SnowflakeBackend with a mock connection injected."""
    config = SnowflakeConnectionConfig(
        account="mock-account",
        user="mock-user",
        password="mock-password",
        database="TEST_DB",
        schema="PUBLIC",
        warehouse="MOCK_WH",
    )
    backend = SnowflakeBackend(connection_config=config)
    backend._conn = mock_connection
    backend._connected = True
    yield backend


@pytest.fixture
def configure_model(mock_backend):
    """Helper to bind an ActiveRecord subclass to the mock backend."""
    def _configure(model_class):
        model_class.configure(mock_backend.__class__.__name__, mock_backend)
        return model_class
    return _configure
