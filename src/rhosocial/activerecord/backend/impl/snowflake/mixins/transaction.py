# src/rhosocial/activerecord/backend/impl/snowflake/mixins/transaction.py
"""Transaction and concurrency mixins for Snowflake.

Snowflake supports READ COMMITTED isolation level only.
"""
from typing import Any, Dict, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.protocols import ConcurrencyHint
from rhosocial.activerecord.backend.transaction import IsolationLevel


class SnowflakeTransactionMixin:
    """Shared non-I/O transaction logic for Snowflake.

    Snowflake supports READ COMMITTED isolation level only.
    ALTER SESSION SET TRANSACTION_ISOLATION_LEVEL is not needed
    as Snowflake only supports READ COMMITTED.
    """

    _ISOLATION_LEVELS = {
        IsolationLevel.READ_COMMITTED: 'READ COMMITTED',
    }

    def supports_transaction_mode(self) -> bool:
        """Snowflake does not support READ ONLY / READ WRITE modes."""
        return False

    def supports_isolation_level_in_begin(self) -> bool:
        """Snowflake only supports READ COMMITTED and not in BEGIN."""
        return False

    def supports_read_only_transaction(self) -> bool:
        """Snowflake does not support READ ONLY transactions."""
        return False

    def supports_deferrable_transaction(self) -> bool:
        """Snowflake does not support DEFERRABLE transactions."""
        return False

    def supports_transaction_wait(self) -> bool:
        """Snowflake has no ``WAIT`` / ``NO WAIT`` transaction clause.

        The reference grammar for BEGIN is
        ``BEGIN [ { WORK | TRANSACTION } ] [ NAME <name> ]``; there is no
        lock-wait clause, and Snowflake has no SET TRANSACTION statement at
        all. The pair is refused by name rather than dropped.
        https://docs.snowflake.com/en/sql-reference/sql/begin
        """
        return False

    def _refuse_transaction_wait(
        self, params: Dict[str, Any], statement: str
    ) -> None:
        """Refuse the WAIT / NO WAIT pair by name when the probe declines it.

        The pair has no Snowflake spelling, so a request must fail closed --
        the same shape as every other probe-gated clause -- instead of being
        silently dropped from the rendered statement.
        """
        wait = params.get("wait")
        no_wait = params.get("no_wait")
        if (wait or no_wait) and not self.supports_transaction_wait():
            feature = f"{statement} {'WAIT' if wait else 'NO WAIT'}"
            raise UnsupportedFeatureError(
                self.name,
                feature,
                suggestion=(
                    "Snowflake's BEGIN takes no WAIT / NO WAIT clause, and "
                    "there is no SET TRANSACTION statement."
                ),
            )

    def supports_savepoint(self) -> bool:
        """Snowflake supports savepoints."""
        return True

    def _build_set_isolation_sql(self, level: IsolationLevel) -> Tuple[str, tuple]:
        """Build SQL to set transaction isolation level.

        Snowflake only supports READ COMMITTED. If another level is requested,
        we warn and use READ COMMITTED.

        Args:
            level: The desired isolation level.

        Returns:
            Tuple of (SQL string, parameters)
        """
        if level not in self._ISOLATION_LEVELS:
            import warnings
            warnings.warn(
                f"Snowflake only supports READ COMMITTED isolation level. "
                f"Requested level {level} is not supported.",
                RuntimeWarning,
                stacklevel=3,
            )
        return ("", ())

    def _build_begin_sql(self) -> Tuple[str, tuple]:
        """Build BEGIN TRANSACTION SQL for Snowflake.

        Returns:
            Tuple of (SQL string, parameters)
        """
        return ("BEGIN", ())


class SnowflakeConcurrencyMixin:
    """Snowflake concurrency hint (sync)."""

    def _fetch_concurrency_hint(self) -> ConcurrencyHint:
        """Snowflake uses warehouse-based concurrency.

        Returns:
            ConcurrencyHint indicating Snowflake's concurrency model.
        """
        return ConcurrencyHint.ADVISORY


class AsyncSnowflakeConcurrencyMixin:
    """Snowflake concurrency hint (async)."""

    def _fetch_concurrency_hint(self) -> ConcurrencyHint:
        """Snowflake uses warehouse-based concurrency.

        Returns:
            ConcurrencyHint indicating Snowflake's concurrency model.
        """
        return ConcurrencyHint.ADVISORY