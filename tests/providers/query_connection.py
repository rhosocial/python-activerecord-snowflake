"""Query connection test provider for Snowflake backend.

Implements IQueryConnectionProvider for connection pool query tests.
"""
from typing import Type, Tuple, Optional, List

from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord
from rhosocial.activerecord.backend.impl.snowflake import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig
from rhosocial.activerecord.connection.pool import BackendPool, AsyncBackendPool, PoolConfig
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

from rhosocial.activerecord.testsuite.feature.query.connection.interfaces import IQueryConnectionProvider
from .scenarios import get_scenario, get_enabled_scenarios


class SyncQueryTestUser(ActiveRecord):
    __table_name__ = "test_users"
    id: Optional[int] = None
    name: str
    email: str


class AsyncQueryTestUser(AsyncActiveRecord):
    __table_name__ = "test_users"
    id: Optional[int] = None
    name: str
    email: str


class QueryConnectionProvider(IQueryConnectionProvider):

    def __init__(self):
        self._active_backends: List = []
        self._active_async_backends: List = []

    def get_test_scenarios(self) -> list:
        return list(get_enabled_scenarios().keys())

    def _create_test_table(self, backend):
        try:
            backend.execute("DROP TABLE IF EXISTS test_users", options=ExecutionOptions(stmt_type=StatementType.DDL))
        except Exception:
            pass
        backend.execute("""
            CREATE TABLE test_users (
                id INTEGER AUTOINCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL
            )
        """, options=ExecutionOptions(stmt_type=StatementType.DDL))

    async def _create_test_table_async(self, backend):
        try:
            await backend.execute("DROP TABLE IF EXISTS test_users", options=ExecutionOptions(stmt_type=StatementType.DDL))
        except Exception:
            pass
        await backend.execute("""
            CREATE TABLE test_users (
                id INTEGER AUTOINCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL
            )
        """, options=ExecutionOptions(stmt_type=StatementType.DDL))

    def setup_sync_pool_and_model(self, scenario_name: str) -> Tuple[BackendPool, Type[ActiveRecord]]:
        _, config = get_scenario(scenario_name)

        pool_config = PoolConfig(
            min_size=1,
            max_size=5,
            backend_factory=lambda: SnowflakeBackend(connection_config=config)
        )
        pool = BackendPool.create(pool_config)

        with pool.connection() as backend:
            self._create_test_table(backend)
            self._active_backends.append(backend)

        SyncQueryTestUser.configure(config, SnowflakeBackend)
        self._active_backends.append(SyncQueryTestUser.__backend__)

        return pool, SyncQueryTestUser

    async def setup_async_pool_and_model(self, scenario_name: str) -> Tuple[AsyncBackendPool, Type[AsyncActiveRecord]]:
        from rhosocial.activerecord.backend.impl.snowflake import AsyncSnowflakeBackend

        _, config = get_scenario(scenario_name)

        pool_config = PoolConfig(
            min_size=1,
            max_size=5,
            backend_factory=lambda: AsyncSnowflakeBackend(connection_config=config)
        )

        pool = await AsyncBackendPool.create(pool_config)

        async with pool.connection() as backend:
            await self._create_test_table_async(backend)
            self._active_async_backends.append(backend)

        await AsyncQueryTestUser.configure(config, AsyncSnowflakeBackend)
        self._active_async_backends.append(AsyncQueryTestUser.__backend__)

        return pool, AsyncQueryTestUser

    def cleanup_sync(self, scenario_name: str, pool: BackendPool):
        pool.close(timeout=1.0)
        for backend in self._active_backends:
            try:
                backend.disconnect()
            except Exception:
                pass
        self._active_backends.clear()

    async def cleanup_async(self, scenario_name: str, pool: AsyncBackendPool):
        await pool.close(timeout=1.0)
        for backend in self._active_async_backends:
            try:
                await backend.disconnect()
            except Exception:
                pass
        self._active_async_backends.clear()
