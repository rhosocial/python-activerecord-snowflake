"""Snowflake asynchronous transaction manager implementation.

This module provides async transaction management for the Snowflake backend.
Snowflake only supports READ COMMITTED isolation level.
"""
import logging
from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.transaction import AsyncTransactionManager
from .mixins import SnowflakeTransactionMixin

if TYPE_CHECKING:
    from .async_backend import AsyncSnowflakeBackend


class AsyncSnowflakeTransactionManager(SnowflakeTransactionMixin, AsyncTransactionManager):
    """Snowflake asynchronous transaction manager implementation.

    Snowflake only supports READ COMMITTED isolation level, so
    SET TRANSACTION ISOLATION LEVEL is not needed. This class
    uses a simple BEGIN/COMMIT/ROLLBACK flow.

    Non-I/O methods (_ISOLATION_LEVELS, _build_set_isolation_sql)
    are inherited from SnowflakeTransactionMixin.
    """

    def __init__(self, backend: "AsyncSnowflakeBackend", logger=None):
        """Initialize async Snowflake transaction manager.

        Args:
            backend: AsyncSnowflakeBackend instance.
            logger: Optional logger instance.
        """
        super().__init__(backend, logger)

    async def _do_begin(self) -> None:
        """Begin a new transaction asynchronously.

        Snowflake uses BEGIN (or START TRANSACTION) to begin a transaction.
        No isolation level setting is needed since Snowflake only supports
        READ COMMITTED.
        """
        sql, params = self._build_begin_sql()
        self.log(logging.DEBUG, f"Executing: {sql}")
        await self._backend.execute(sql, params)
