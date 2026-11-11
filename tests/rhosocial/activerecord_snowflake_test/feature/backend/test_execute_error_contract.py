# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_execute_error_contract.py
"""Execute-phase error contract for the Snowflake backend.

These tests need no Snowflake account: backends are constructed without
connecting, and driver exceptions are built directly from
``snowflake.connector.errors``. The connector is optional, so the module skips
when it is not installed.

The contract under test:

* framework ``DatabaseError`` subclasses (``ConnectionError``,
  ``TypeConversionError``, ``TransactionError``) pass through ``_handle_error``
  unchanged instead of being reclassified into a driver category;
* the ``_classify_error`` message fallback cannot catch a framework error;
* a transient driver timeout becomes ``OperationalError(transient=True)``;
* a non-transient authentication failure stays ``ConnectionError``;
* a commit failure is surfaced as ``TransactionError`` (Snowflake's commit path
  is the transaction manager, not an execute auto-commit hook).
"""
import pytest

pytest.importorskip("snowflake.connector")

from snowflake.connector import errors as driver_errors  # noqa: E402

from rhosocial.activerecord.backend.errors import (  # noqa: E402
    ConnectionError as BackendConnectionError,
    OperationalError as BackendOperationalError,
    QueryError,
    TransactionError,
    TypeConversionError,
    attach_diagnostics,
)
from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend  # noqa: E402
from rhosocial.activerecord.backend.impl.snowflake.backend.async_backend import (  # noqa: E402
    AsyncSnowflakeBackend,
)
from rhosocial.activerecord.backend.impl.snowflake.config import (  # noqa: E402
    SnowflakeConnectionConfig,
)
from rhosocial.activerecord.backend.impl.snowflake.transaction import (  # noqa: E402
    SnowflakeTransactionManager,
)
from rhosocial.activerecord.backend.impl.snowflake.async_transaction import (  # noqa: E402
    AsyncSnowflakeTransactionManager,
)
from rhosocial.activerecord.backend.transaction import TransactionState  # noqa: E402


def _config() -> SnowflakeConnectionConfig:
    """Build a config with dummy credentials; nothing connects."""
    return SnowflakeConnectionConfig(
        account="unit-test-account",
        username="unit-test-user",
        password="unit-test-password",
        database="unit-test-database",
    )


def _backend() -> SnowflakeBackend:
    """Create an unconnected synchronous backend."""
    return SnowflakeBackend(connection_config=_config())


def _async_backend() -> AsyncSnowflakeBackend:
    """Create an unconnected asynchronous backend."""
    return AsyncSnowflakeBackend(connection_config=_config())


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


class TestExecuteErrorContract:
    """Synchronous execute-phase error contract."""

    def test_framework_type_conversion_error_is_preserved(self):
        """A framework TypeConversionError must not become DatabaseError."""
        error = TypeConversionError("Cannot convert parameter value")
        backend = _backend()
        with pytest.raises(TypeConversionError) as info:
            backend._handle_error(error)
        mapped = info.value
        assert mapped is error
        assert type(mapped) is TypeConversionError
        assert not isinstance(mapped, BackendOperationalError)
        assert not isinstance(mapped, BackendConnectionError)

    def test_framework_error_message_fallback_is_not_used(self):
        """The driver-message fallback must leave framework errors alone."""
        error = QueryError("syntax error: connection refused by server")
        backend = _backend()
        assert backend._classify_error(error) == "framework"
        assert backend._resolve_error_mapping(error, "framework") == ("framework", None)
        with pytest.raises(QueryError) as info:
            backend._handle_error(error)
        assert info.value is error

    def test_framework_connection_error_with_transient_flag_is_preserved(self):
        """A framework ConnectionError keeps its type, diagnostics and flags."""
        error = attach_diagnostics(
            BackendConnectionError("Session is invalid"),
            operation="execute",
            backend="snowflake",
            transient=True,
        )
        backend = _backend()
        with pytest.raises(BackendConnectionError) as info:
            backend._handle_error(error)
        mapped = info.value
        assert mapped is error
        assert mapped.transient is True
        assert mapped.retryable is True

    def test_driver_timeout_maps_to_transient_operational_error(self):
        """A network timeout is a retryable OperationalError."""
        error = _driver_error(
            "OperationalError",
            "Connection timeout occurred while waiting for a response.",
            errno=250002,
        )
        backend = _backend()
        with pytest.raises(BackendOperationalError) as info:
            backend._handle_error(error)
        mapped = info.value
        assert mapped.transient is True
        assert mapped.retryable is True
        assert mapped.backend == "snowflake"
        assert mapped.__cause__ is error

    def test_auth_failure_stays_non_transient_connection_error(self):
        """Bad credentials are a ConnectionError that retrying cannot fix."""
        error = _driver_error(
            "DatabaseError",
            "Incorrect username or password was specified.",
            errno=390100,
        )
        backend = _backend()
        with pytest.raises(BackendConnectionError) as info:
            backend._handle_error(error)
        mapped = info.value
        assert mapped.transient is False
        assert mapped.retryable is False
        assert mapped.backend == "snowflake"

    def test_lock_and_deadlock_are_not_invented(self):
        """Snowflake execute has no lock/deadlock semantics to classify."""
        error = _driver_error(
            "OperationalError",
            "Deadlock detected while waiting for a lock",
            errno=999999,
        )
        backend = _backend()
        with pytest.raises(BackendOperationalError):
            backend._handle_error(error)

    def test_execute_has_no_auto_commit_hook(self):
        """Snowflake inherits the no-op auto-commit hook from core."""
        backend = _backend()
        assert backend._handle_auto_commit() is None

    def test_commit_failure_surfaces_as_transaction_error(self):
        """A failing COMMIT must never be swallowed."""
        backend = _backend()
        manager = SnowflakeTransactionManager(backend)
        manager._transaction_level = 1
        manager._state = TransactionState.ACTIVE

        def fail_commit():
            raise RuntimeError("driver commit failed")

        manager._do_commit = fail_commit
        with pytest.raises(TransactionError) as info:
            manager.commit()
        assert isinstance(info.value.__cause__, RuntimeError)


class TestAsyncExecuteErrorContract:
    """Asynchronous execute-phase error contract (same cases as sync)."""

    @pytest.mark.asyncio
    async def test_framework_type_conversion_error_is_preserved(self):
        """A framework TypeConversionError must not become DatabaseError."""
        error = TypeConversionError("Cannot convert parameter value")
        backend = _async_backend()
        with pytest.raises(TypeConversionError) as info:
            await backend._handle_error(error)
        mapped = info.value
        assert mapped is error
        assert type(mapped) is TypeConversionError
        assert not isinstance(mapped, BackendOperationalError)
        assert not isinstance(mapped, BackendConnectionError)

    @pytest.mark.asyncio
    async def test_framework_error_message_fallback_is_not_used(self):
        """The driver-message fallback must leave framework errors alone."""
        error = QueryError("syntax error: connection refused by server")
        backend = _async_backend()
        assert backend._classify_error(error) == "framework"
        assert backend._resolve_error_mapping(error, "framework") == ("framework", None)
        with pytest.raises(QueryError) as info:
            await backend._handle_error(error)
        assert info.value is error

    @pytest.mark.asyncio
    async def test_framework_connection_error_with_transient_flag_is_preserved(self):
        """A framework ConnectionError keeps its type, diagnostics and flags."""
        error = attach_diagnostics(
            BackendConnectionError("Session is invalid"),
            operation="execute",
            backend="snowflake",
            transient=True,
        )
        backend = _async_backend()
        with pytest.raises(BackendConnectionError) as info:
            await backend._handle_error(error)
        mapped = info.value
        assert mapped is error
        assert mapped.transient is True
        assert mapped.retryable is True

    @pytest.mark.asyncio
    async def test_driver_timeout_maps_to_transient_operational_error(self):
        """A network timeout is a retryable OperationalError."""
        error = _driver_error(
            "OperationalError",
            "Connection timeout occurred while waiting for a response.",
            errno=250002,
        )
        backend = _async_backend()
        with pytest.raises(BackendOperationalError) as info:
            await backend._handle_error(error)
        mapped = info.value
        assert mapped.transient is True
        assert mapped.retryable is True
        assert mapped.backend == "snowflake"
        assert mapped.__cause__ is error

    @pytest.mark.asyncio
    async def test_auth_failure_stays_non_transient_connection_error(self):
        """Bad credentials are a ConnectionError that retrying cannot fix."""
        error = _driver_error(
            "DatabaseError",
            "Incorrect username or password was specified.",
            errno=390100,
        )
        backend = _async_backend()
        with pytest.raises(BackendConnectionError) as info:
            await backend._handle_error(error)
        mapped = info.value
        assert mapped.transient is False
        assert mapped.retryable is False
        assert mapped.backend == "snowflake"

    @pytest.mark.asyncio
    async def test_lock_and_deadlock_are_not_invented(self):
        """Snowflake execute has no lock/deadlock semantics to classify."""
        error = _driver_error(
            "OperationalError",
            "Deadlock detected while waiting for a lock",
            errno=999999,
        )
        backend = _async_backend()
        with pytest.raises(BackendOperationalError):
            await backend._handle_error(error)

    @pytest.mark.asyncio
    async def test_execute_has_no_auto_commit_hook(self):
        """Snowflake inherits the no-op async auto-commit hook from core."""
        backend = _async_backend()
        assert await backend._handle_auto_commit() is None

    @pytest.mark.asyncio
    async def test_commit_failure_surfaces_as_transaction_error(self):
        """A failing COMMIT must never be swallowed."""
        backend = _async_backend()
        manager = AsyncSnowflakeTransactionManager(backend)
        manager._transaction_level = 1
        manager._state = TransactionState.ACTIVE

        async def fail_commit():
            raise RuntimeError("driver commit failed")

        manager._do_commit = fail_commit
        with pytest.raises(TransactionError) as info:
            await manager.commit()
        assert isinstance(info.value.__cause__, RuntimeError)
