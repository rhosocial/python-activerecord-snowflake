# tests/rhosocial/activerecord_snowflake_test/feature/backend/core/test_driver_error_mapping.py
"""Driver-error to taxonomy mapping for the Snowflake backend.

These tests construct ``snowflake.connector.errors`` exceptions directly and
call ``_handle_error`` on an unconnected backend, so they need no Snowflake
account. The driver is optional: when the connector is not installed the whole
module skips.

Snowflake has weak locking semantics: lock waits and deadlocks are not
classified as LockError/DeadlockError, which one test pins down.
"""
import pytest

pytest.importorskip("snowflake.connector")

from snowflake.connector import errors as driver_errors  # noqa: E402

from rhosocial.activerecord.backend.errors import (  # noqa: E402
    ConnectionError as BackendConnectionError,
    DatabaseError as BackendDatabaseError,
    DataError,
    DeadlockError,
    IntegrityError,
    LockError,
    OperationalError as BackendOperationalError,
    QueryError,
)
from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend  # noqa: E402
from rhosocial.activerecord.backend.impl.snowflake.backend.async_backend import (  # noqa: E402
    AsyncSnowflakeBackend,
)
from rhosocial.activerecord.backend.impl.snowflake.config import (  # noqa: E402
    SnowflakeConnectionConfig,
)


def _config() -> SnowflakeConnectionConfig:
    """Build a config with dummy credentials; nothing connects."""
    return SnowflakeConnectionConfig(
        account="unit-test-account",
        username="unit-test-user",
        password="unit-test-password",
        database="unit-test-database",
    )


def _driver_error(name, message, errno=None, sqlstate=None):
    """Construct a driver exception, tolerating older connector signatures."""
    cls = getattr(driver_errors, name)
    try:
        return cls(msg=message, errno=errno, sqlstate=sqlstate)
    except TypeError:
        pass
    try:
        return cls(msg=message, errno=errno)
    except TypeError:
        return cls(msg=message)


def _assert_diagnostics(mapped, error):
    """Assert every mapped error carries the shared driver diagnostics."""
    assert mapped.backend == "snowflake"
    assert mapped.operation == "execute"
    assert mapped.driver_code == getattr(error, "errno", None)
    assert mapped.sqlstate == getattr(error, "sqlstate", None)


class TestDriverErrorMapping:
    """Synchronous driver-error mapping."""

    def test_duplicate_unique_maps_to_integrity(self):
        error = _driver_error(
            "ProgrammingError",
            "Duplicate key value violates unique constraint",
            errno=100132,
            sqlstate="23000",
        )
        with pytest.raises(IntegrityError) as info:
            SnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert isinstance(mapped, DataError)
        assert mapped.retryable is False
        assert mapped.transient is False
        _assert_diagnostics(mapped, error)
        assert mapped.__cause__ is error

    def test_already_exists_maps_to_integrity(self):
        error = _driver_error(
            "DatabaseError",
            "Object 'USERS' already exists.",
            errno=100132,
            sqlstate="23000",
        )
        with pytest.raises(IntegrityError):
            SnowflakeBackend(connection_config=_config())._handle_error(error)

    def test_not_null_maps_to_integrity(self):
        error = _driver_error(
            "ProgrammingError",
            "NULL result in a non-nullable column",
            errno=100072,
            sqlstate="22004",
        )
        with pytest.raises(IntegrityError) as info:
            SnowflakeBackend(connection_config=_config())._handle_error(error)
        assert isinstance(info.value, DataError)
        assert info.value.retryable is False
        _assert_diagnostics(info.value, error)

    def test_syntax_error_maps_to_query(self):
        error = _driver_error(
            "ProgrammingError",
            "SQL compilation error: syntax error line 1 unexpected 'SELEC'.",
            errno=100038,
            sqlstate="42000",
        )
        with pytest.raises(QueryError) as info:
            SnowflakeBackend(connection_config=_config())._handle_error(error)
        assert info.value.retryable is False
        _assert_diagnostics(info.value, error)

    def test_unknown_column_maps_to_query(self):
        error = _driver_error(
            "DatabaseError",
            "Invalid identifier 'NAME'",
            errno=100038,
            sqlstate="42000",
        )
        with pytest.raises(QueryError):
            SnowflakeBackend(connection_config=_config())._handle_error(error)

    def test_network_timeout_maps_to_transient_operational(self):
        error = _driver_error(
            "OperationalError",
            "Connection timeout occurred while waiting for a response.",
            errno=250002,
        )
        with pytest.raises(BackendOperationalError) as info:
            SnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert mapped.transient is True
        assert mapped.retryable is True
        _assert_diagnostics(mapped, error)

    def test_service_unavailable_maps_to_transient_operational(self):
        if not hasattr(driver_errors, "ServiceUnavailableError"):
            pytest.skip("ServiceUnavailableError not available in this connector")
        error = _driver_error("ServiceUnavailableError", "Service unavailable")
        with pytest.raises(BackendOperationalError) as info:
            SnowflakeBackend(connection_config=_config())._handle_error(error)
        assert info.value.transient is True
        assert info.value.retryable is True

    def test_login_failure_maps_to_non_transient_connection(self):
        error = _driver_error(
            "DatabaseError",
            "Incorrect username or password was specified.",
            errno=390100,
        )
        with pytest.raises(BackendConnectionError) as info:
            SnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert mapped.transient is False
        assert mapped.retryable is False
        _assert_diagnostics(mapped, error)

    def test_permission_denial_maps_to_database_error(self):
        error = _driver_error(
            "ProgrammingError",
            "User does not have permission to execute this statement.",
            errno=390403,
            sqlstate="42501",
        )
        with pytest.raises(BackendDatabaseError) as info:
            SnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert not isinstance(mapped, QueryError)
        assert not isinstance(mapped, DataError)
        assert mapped.retryable is False
        _assert_diagnostics(mapped, error)

    def test_generic_driver_error_maps_to_database_error(self):
        error = _driver_error(
            "DatabaseError",
            "Some unexpected database failure",
            errno=999999,
        )
        with pytest.raises(BackendDatabaseError) as info:
            SnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert mapped.transient is None
        assert mapped.retryable is False
        _assert_diagnostics(mapped, error)

    def test_lock_and_deadlock_are_not_invented(self):
        error = _driver_error(
            "OperationalError",
            "Deadlock detected while waiting for a lock",
            errno=999999,
        )
        with pytest.raises(BackendOperationalError) as info:
            SnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert not isinstance(mapped, DeadlockError)
        assert not isinstance(mapped, LockError)
        assert mapped.retryable is False


class TestAsyncDriverErrorMapping:
    """Asynchronous driver-error mapping (same cases as the sync class)."""

    async def test_duplicate_unique_maps_to_integrity(self):
        error = _driver_error(
            "ProgrammingError",
            "Duplicate key value violates unique constraint",
            errno=100132,
            sqlstate="23000",
        )
        with pytest.raises(IntegrityError) as info:
            await AsyncSnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert isinstance(mapped, DataError)
        assert mapped.retryable is False
        assert mapped.transient is False
        _assert_diagnostics(mapped, error)
        assert mapped.__cause__ is error

    async def test_already_exists_maps_to_integrity(self):
        error = _driver_error(
            "DatabaseError",
            "Object 'USERS' already exists.",
            errno=100132,
            sqlstate="23000",
        )
        with pytest.raises(IntegrityError):
            await AsyncSnowflakeBackend(connection_config=_config())._handle_error(error)

    async def test_not_null_maps_to_integrity(self):
        error = _driver_error(
            "ProgrammingError",
            "NULL result in a non-nullable column",
            errno=100072,
            sqlstate="22004",
        )
        with pytest.raises(IntegrityError) as info:
            await AsyncSnowflakeBackend(connection_config=_config())._handle_error(error)
        assert isinstance(info.value, DataError)
        assert info.value.retryable is False
        _assert_diagnostics(info.value, error)

    async def test_syntax_error_maps_to_query(self):
        error = _driver_error(
            "ProgrammingError",
            "SQL compilation error: syntax error line 1 unexpected 'SELEC'.",
            errno=100038,
            sqlstate="42000",
        )
        with pytest.raises(QueryError) as info:
            await AsyncSnowflakeBackend(connection_config=_config())._handle_error(error)
        assert info.value.retryable is False
        _assert_diagnostics(info.value, error)

    async def test_unknown_column_maps_to_query(self):
        error = _driver_error(
            "DatabaseError",
            "Invalid identifier 'NAME'",
            errno=100038,
            sqlstate="42000",
        )
        with pytest.raises(QueryError):
            await AsyncSnowflakeBackend(connection_config=_config())._handle_error(error)

    async def test_network_timeout_maps_to_transient_operational(self):
        error = _driver_error(
            "OperationalError",
            "Connection timeout occurred while waiting for a response.",
            errno=250002,
        )
        with pytest.raises(BackendOperationalError) as info:
            await AsyncSnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert mapped.transient is True
        assert mapped.retryable is True
        _assert_diagnostics(mapped, error)

    async def test_service_unavailable_maps_to_transient_operational(self):
        if not hasattr(driver_errors, "ServiceUnavailableError"):
            pytest.skip("ServiceUnavailableError not available in this connector")
        error = _driver_error("ServiceUnavailableError", "Service unavailable")
        with pytest.raises(BackendOperationalError) as info:
            await AsyncSnowflakeBackend(connection_config=_config())._handle_error(error)
        assert info.value.transient is True
        assert info.value.retryable is True

    async def test_login_failure_maps_to_non_transient_connection(self):
        error = _driver_error(
            "DatabaseError",
            "Incorrect username or password was specified.",
            errno=390100,
        )
        with pytest.raises(BackendConnectionError) as info:
            await AsyncSnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert mapped.transient is False
        assert mapped.retryable is False
        _assert_diagnostics(mapped, error)

    async def test_permission_denial_maps_to_database_error(self):
        error = _driver_error(
            "ProgrammingError",
            "User does not have permission to execute this statement.",
            errno=390403,
            sqlstate="42501",
        )
        with pytest.raises(BackendDatabaseError) as info:
            await AsyncSnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert not isinstance(mapped, QueryError)
        assert not isinstance(mapped, DataError)
        assert mapped.retryable is False
        _assert_diagnostics(mapped, error)

    async def test_generic_driver_error_maps_to_database_error(self):
        error = _driver_error(
            "DatabaseError",
            "Some unexpected database failure",
            errno=999999,
        )
        with pytest.raises(BackendDatabaseError) as info:
            await AsyncSnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert mapped.transient is None
        assert mapped.retryable is False
        _assert_diagnostics(mapped, error)

    async def test_lock_and_deadlock_are_not_invented(self):
        error = _driver_error(
            "OperationalError",
            "Deadlock detected while waiting for a lock",
            errno=999999,
        )
        with pytest.raises(BackendOperationalError) as info:
            await AsyncSnowflakeBackend(connection_config=_config())._handle_error(error)
        mapped = info.value
        assert not isinstance(mapped, DeadlockError)
        assert not isinstance(mapped, LockError)
        assert mapped.retryable is False
