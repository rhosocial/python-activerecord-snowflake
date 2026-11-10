# tests/rhosocial/activerecord_snowflake_test/feature/logging/test_execution_logging_unit.py
"""Database-free coverage of the Snowflake execution logging contract.

The execution-logging change is mostly a set of small branches: the error
classifier's DEBUG records on both backends, the result-set failure records,
the canonical logger name shared by the sync and async backends, and the CLI
module logger. None of that needs a warehouse, so this module builds backends
with dummy connection configurations, swaps only the classifier, and asserts
what is logged.

Contract under test:

* ``SnowflakeBackend`` and ``AsyncSnowflakeBackend`` resolve to the single
  library logger ``rhosocial.activerecord.backend.snowflake``; the transaction
  managers do not emit a second "Executing: ..." record because the backend
  execution path owns the canonical DEBUG SQL record.
* Every ``_handle_error`` category logs at DEBUG (not ERROR) before raising the
  typed backend error.
* A failing result-set conversion logs at DEBUG and re-raises the original
  exception.

No ``snowflake.connector`` import is required: the classifier is replaced on
the instance, and connection state stays ``None`` throughout.
"""

import logging

import pytest

from rhosocial.activerecord.backend.errors import (
    ConnectionError as BackendConnectionError,
)
from rhosocial.activerecord.backend.errors import (
    DatabaseError as BackendDatabaseError,
)
from rhosocial.activerecord.backend.errors import (
    IntegrityError as BackendIntegrityError,
)
from rhosocial.activerecord.backend.errors import (
    OperationalError as BackendOperationalError,
)
from rhosocial.activerecord.backend.errors import (
    QueryError as BackendQueryError,
)
from rhosocial.activerecord.backend.impl.snowflake.async_transaction import (
    AsyncSnowflakeTransactionManager,
)
from rhosocial.activerecord.backend.impl.snowflake.backend.async_backend import (
    AsyncSnowflakeBackend,
)
from rhosocial.activerecord.backend.impl.snowflake.backend.backend import (
    SnowflakeBackend,
)
from rhosocial.activerecord.backend.impl.snowflake.cli import info as cli_info
from rhosocial.activerecord.backend.impl.snowflake.config import (
    SnowflakeConnectionConfig,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import SnowflakeBackendMixin
from rhosocial.activerecord.backend.impl.snowflake.transaction import (
    SnowflakeTransactionManager,
)
from rhosocial.activerecord.logging.defaults import get_logger

#: The one library logger both backend halves and the CLI must resolve to.
CANONICAL_LOGGER = "rhosocial.activerecord.backend.snowflake"

#: ``(classifier category, raised error type, log label)`` for every branch.
ERROR_CASES = [
    ("connection", BackendConnectionError, "Connection"),
    ("integrity", BackendIntegrityError, "Integrity"),
    ("query", BackendQueryError, "Query"),
    ("operational", BackendOperationalError, "Operational"),
    ("unknown", BackendDatabaseError, "Database"),
]


def _config() -> SnowflakeConnectionConfig:
    """Build a connection config with dummy credentials; nothing connects."""
    return SnowflakeConnectionConfig(
        account="unit-test-account",
        username="unit-test-user",
        password="unit-test-password",
        database="unit-test-database",
    )


def _logged_messages(caplog) -> list:
    """Return the captured records' formatted messages."""
    return [record.getMessage() for record in caplog.records]


class _FakeExecutor:
    """Placeholder executor; the async backend only stores it during ``init``."""


class _FailingCursor:
    """Cursor whose ``fetchall`` fails after a statement has run."""

    description = ()

    def fetchall(self):
        raise RuntimeError("result set boom")


class _FailingAsyncCursor:
    """Async counterpart of :class:`_FailingCursor`."""

    description = ()

    async def fetchall(self):
        raise RuntimeError("result set boom")


class _RecordingBackend:
    """Minimal sync backend that records the SQL the transaction manager runs."""

    dialect = SnowflakeDialect()

    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, tuple(params or ())))


class _RecordingAsyncBackend:
    """Async counterpart of :class:`_RecordingBackend`."""

    dialect = SnowflakeDialect()

    def __init__(self):
        self.calls = []

    async def execute(self, sql, params=None):
        self.calls.append((sql, tuple(params or ())))


class TestExecutionLoggingContract:
    """Synchronous half of the execution logging contract."""

    def test_backend_uses_canonical_logger(self):
        backend = SnowflakeBackend(connection_config=_config())
        assert backend.logger.name == CANONICAL_LOGGER
        assert backend._get_logger_name() == CANONICAL_LOGGER

    def test_mixin_declares_canonical_logger_name(self):
        assert SnowflakeBackendMixin()._get_logger_name() == CANONICAL_LOGGER

    def test_backend_builds_config_from_keyword_arguments(self):
        backend = SnowflakeBackend(
            account="unit-test-account",
            username="unit-test-user",
            password="unit-test-password",
            database="unit-test-database",
            version=(8, 0, 0),
        )
        assert backend.config.account == "unit-test-account"
        assert backend.get_server_version() == (8, 0, 0)

    def test_ping_does_not_reconnect_offline(self):
        backend = SnowflakeBackend(connection_config=_config())
        assert backend._connection is None
        assert backend.ping(reconnect=False) is False

    @pytest.mark.parametrize("category, error_type, label", ERROR_CASES)
    def test_handle_error_logs_debug_and_raises_typed_error(
        self, category, error_type, label, caplog, monkeypatch
    ):
        caplog.set_level(logging.DEBUG, logger=CANONICAL_LOGGER)
        backend = SnowflakeBackend(connection_config=_config())
        monkeypatch.setattr(backend, "_classify_error", lambda error: category)

        with pytest.raises(error_type, match="boom"):
            backend._handle_error(RuntimeError("boom"))

        assert f"{label} error: boom" in _logged_messages(caplog)
        assert all(
            record.levelno == logging.DEBUG
            for record in caplog.records
            if " error: boom" in record.getMessage()
        )

    def test_process_result_set_logs_debug_and_reraises(self, caplog):
        caplog.set_level(logging.DEBUG, logger=CANONICAL_LOGGER)
        backend = SnowflakeBackend(connection_config=_config())

        with pytest.raises(RuntimeError, match="result set boom"):
            backend._process_result_set(_FailingCursor(), is_select=True)

        assert "Error processing result set: result set boom" in _logged_messages(caplog)
        assert all(
            record.levelno == logging.DEBUG
            for record in caplog.records
            if "Error processing result set" in record.getMessage()
        )

    def test_begin_and_commit_delegate_to_backend(self):
        backend = _RecordingBackend()
        manager = SnowflakeTransactionManager(
            backend, logger=logging.getLogger("test.snowflake.transaction")
        )

        manager.begin()
        manager.commit()

        assert backend.calls == [("BEGIN", ()), ("COMMIT", ())]
        assert manager.is_active is False


class TestAsyncExecutionLoggingContract:
    """Async counterpart of :class:`TestExecutionLoggingContract`."""

    @pytest.mark.asyncio
    async def test_backend_uses_canonical_logger(self):
        backend = AsyncSnowflakeBackend(connection_config=_config())
        assert backend.logger.name == CANONICAL_LOGGER
        assert backend._get_logger_name() == CANONICAL_LOGGER

    @pytest.mark.asyncio
    async def test_backend_builds_config_from_keyword_arguments(self):
        executor = _FakeExecutor()
        backend = AsyncSnowflakeBackend(
            executor=executor,
            account="unit-test-account",
            username="unit-test-user",
            password="unit-test-password",
            database="unit-test-database",
            version=(8, 0, 0),
        )
        assert backend.config.account == "unit-test-account"
        assert backend._executor is executor
        assert await backend.get_server_version() == (8, 0, 0)

    @pytest.mark.asyncio
    async def test_ping_does_not_reconnect_offline(self):
        backend = AsyncSnowflakeBackend(connection_config=_config())
        assert backend._connection is None
        assert await backend.ping(reconnect=False) is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("category, error_type, label", ERROR_CASES)
    async def test_handle_error_logs_debug_and_raises_typed_error(
        self, category, error_type, label, caplog, monkeypatch
    ):
        caplog.set_level(logging.DEBUG, logger=CANONICAL_LOGGER)
        backend = AsyncSnowflakeBackend(connection_config=_config())
        monkeypatch.setattr(backend, "_classify_error", lambda error: category)

        with pytest.raises(error_type, match="boom"):
            await backend._handle_error(RuntimeError("boom"))

        assert f"{label} error: boom" in _logged_messages(caplog)
        assert all(
            record.levelno == logging.DEBUG
            for record in caplog.records
            if " error: boom" in record.getMessage()
        )

    @pytest.mark.asyncio
    async def test_process_result_set_logs_debug_and_reraises(self, caplog):
        caplog.set_level(logging.DEBUG, logger=CANONICAL_LOGGER)
        backend = AsyncSnowflakeBackend(connection_config=_config())

        with pytest.raises(RuntimeError, match="result set boom"):
            await backend._process_result_set(_FailingAsyncCursor(), is_select=True)

        assert (
            "Error processing async result set: result set boom"
            in _logged_messages(caplog)
        )
        assert all(
            record.levelno == logging.DEBUG
            for record in caplog.records
            if "Error processing async result set" in record.getMessage()
        )

    @pytest.mark.asyncio
    async def test_begin_and_commit_delegate_to_backend(self):
        backend = _RecordingAsyncBackend()
        manager = AsyncSnowflakeTransactionManager(
            backend, logger=logging.getLogger("test.snowflake.async_transaction")
        )

        await manager.begin()
        await manager.commit()

        assert backend.calls == [("BEGIN", ()), ("COMMIT", ())]
        assert manager.is_active is False


class TestCliInfoLogger:
    """The CLI module uses the canonical logger, not its module namespace."""

    def test_info_uses_canonical_logger(self):
        assert cli_info.logger.name == CANONICAL_LOGGER
        assert cli_info.logger is get_logger(CANONICAL_LOGGER)
