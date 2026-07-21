# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_concurrency_protocol.py
"""
Test for ConcurrencyAware protocol implementation in Snowflake backend.

This test verifies that SnowflakeBackend correctly implements the ConcurrencyAware
protocol by fetching max_connections during connect and returning the appropriate
concurrency hint.
"""
import pytest

from rhosocial.activerecord.backend.protocols import ConcurrencyAware, ConcurrencyHint


class TestMySQLConcurrencyAware:
    """Test ConcurrencyAware protocol implementation for Snowflake backend."""

    def test_snowflake_backend_implements_protocol(self, snowflake_backend_single):
        """Test that SnowflakeBackend implements ConcurrencyAware protocol."""
        assert isinstance(snowflake_backend_single, ConcurrencyAware)

    def test_mysql_get_concurrency_hint(self, snowflake_backend_single):
        """Test SnowflakeBackend returns correct concurrency hint."""
        hint = snowflake_backend_single.get_concurrency_hint()

        assert hint is not None
        assert isinstance(hint, ConcurrencyHint)
        assert hint.max_concurrency is not None
        assert hint.max_concurrency > 0
        assert "max_connections" in hint.reason
        assert "pool_size" in hint.reason

    def test_mysql_concurrency_hint_value(self, snowflake_backend_single):
        """Test concurrency hint value is bounded by pool_size."""
        pool_size = snowflake_backend_single.config.pool_size or 5
        hint = snowflake_backend_single.get_concurrency_hint()

        assert hint.max_concurrency <= pool_size
        assert hint.max_concurrency > 0

    def test_mysql_concurrency_hint_not_none_after_connect(self, snowflake_backend_single):
        """Test that concurrency hint is populated after connect."""
        assert snowflake_backend_single._connection is not None
        assert snowflake_backend_single.get_concurrency_hint() is not None


class TestAsyncMySQLConcurrencyAware:
    """Test ConcurrencyAware protocol implementation for async Snowflake backend."""

    @pytest.mark.asyncio
    async def test_async_snowflake_backend_implements_protocol(self, async_snowflake_backend_single):
        """Test that AsyncSnowflakeBackend implements ConcurrencyAware protocol."""
        assert isinstance(async_snowflake_backend_single, ConcurrencyAware)

    @pytest.mark.asyncio
    async def test_async_mysql_get_concurrency_hint(self, async_snowflake_backend_single):
        """Test AsyncSnowflakeBackend returns correct concurrency hint."""
        hint = async_snowflake_backend_single.get_concurrency_hint()

        assert hint is not None
        assert isinstance(hint, ConcurrencyHint)
        assert hint.max_concurrency is not None
        assert hint.max_concurrency > 0
        assert "max_connections" in hint.reason
        assert "pool_size" in hint.reason

    @pytest.mark.asyncio
    async def test_async_mysql_concurrency_hint_value(self, async_snowflake_backend_single):
        """Test async concurrency hint value is bounded by pool_size."""
        pool_size = async_snowflake_backend_single.config.pool_size or 5
        hint = async_snowflake_backend_single.get_concurrency_hint()

        assert hint.max_concurrency <= pool_size
        assert hint.max_concurrency > 0

    @pytest.mark.asyncio
    async def test_async_mysql_concurrency_hint_not_none_after_connect(
        self, async_snowflake_backend_single
    ):
        """Test that async concurrency hint is populated after connect."""
        assert async_snowflake_backend_single._connection is not None
        assert async_snowflake_backend_single.get_concurrency_hint() is not None