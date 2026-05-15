"""Snowflake synchronous transaction manager implementation.

This module provides Snowflake-specific transaction management.
Snowflake only supports READ COMMITTED isolation level.
"""
import logging
from typing import TYPE_CHECKING

from rhosocial.activerecord.backend.transaction import TransactionManager
from .mixins import SnowflakeTransactionMixin

if TYPE_CHECKING:
    from .backend import SnowflakeBackend


class SnowflakeTransactionManager(SnowflakeTransactionMixin, TransactionManager):
    """Snowflake synchronous transaction manager implementation.

    Snowflake only supports READ COMMITTED isolation level, so
    SET TRANSACTION ISOLATION LEVEL is not needed. This class
    uses a simple BEGIN/COMMIT/ROLLBACK flow.

    Non-I/O methods (_ISOLATION_LEVELS, _build_set_isolation_sql)
    are inherited from SnowflakeTransactionMixin.
    """

    def __init__(self, backend: "SnowflakeBackend", logger=None):
        """Initialize Snowflake transaction manager.

        Args:
            backend: SnowflakeBackend instance.
            logger: Optional logger instance.
        """
        super().__init__(backend, logger)

    def _do_begin(self) -> None:
        """Begin a new transaction.

        Snowflake uses BEGIN (or START TRANSACTION) to begin a transaction.
        No isolation level setting is needed since Snowflake only supports
        READ COMMITTED.
        """
        sql, params = self._build_begin_sql()
        self.log(logging.DEBUG, f"Executing: {sql}")
        self._backend.execute(sql, params)
