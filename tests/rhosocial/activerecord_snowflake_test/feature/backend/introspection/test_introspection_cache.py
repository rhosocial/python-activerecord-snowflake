# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_introspection_cache.py
"""
Tests for Snowflake introspection cache management.

This module tests the cache management methods including
invalidate_introspection_cache and clear_introspection_cache.
"""

import time

import pytest

from rhosocial.activerecord.backend.introspection.types import IntrospectionScope


class TestCacheManagement:
    """Tests for cache management methods."""

    def test_clear_introspection_cache(self, backend_with_tables):
        """Test clear_introspection_cache clears all cache."""
        # First, populate cache
        backend_with_tables.introspector.get_database_info()
        backend_with_tables.introspector.list_tables()
        backend_with_tables.introspector.list_columns("users")

        # Clear cache
        backend_with_tables.introspector.clear_cache()

        # Verify cache is empty by checking internal cache dict
        assert len(backend_with_tables.introspector._cache) == 0

    def test_cache_hit(self, backend_with_tables):
        """Test that cached results are returned."""
        db_info1 = backend_with_tables.introspector.get_database_info()

        # Second call should return cached result
        db_info2 = backend_with_tables.introspector.get_database_info()

        # Same object reference means it was cached
        assert db_info1 is db_info2

    def test_cache_miss_after_clear(self, backend_with_tables):
        """Test cache miss after clear."""
        db_info1 = backend_with_tables.introspector.get_database_info()
        backend_with_tables.introspector.clear_cache()
        db_info2 = backend_with_tables.introspector.get_database_info()

        # Different object reference means cache was cleared
        assert db_info1 is not db_info2


class TestInvalidateIntrospectionCache:
    """Tests for invalidate_introspection_cache method."""

    def test_invalidate_all_scopes(self, backend_with_tables):
        """Test invalidating all caches."""
        # Populate multiple caches
        backend_with_tables.introspector.get_database_info()
        backend_with_tables.introspector.list_tables()
        backend_with_tables.introspector.list_columns("users")
        backend_with_tables.introspector.list_indexes("users")

        # Invalidate all
        backend_with_tables.introspector.invalidate_cache()

        assert len(backend_with_tables.introspector._cache) == 0

    def test_invalidate_specific_scope(self, backend_with_tables):
        """Test invalidating specific scope."""
        # Populate caches
        db_info = backend_with_tables.introspector.get_database_info()
        tables = backend_with_tables.introspector.list_tables()

        # Invalidate only database scope
        backend_with_tables.introspector.invalidate_cache(
            scope=IntrospectionScope.DATABASE
        )

        # Database cache should be cleared
        db_info2 = backend_with_tables.introspector.get_database_info()
        # Check internal cache was cleared for database scope
        db_cache_key = backend_with_tables.introspector._make_cache_key(IntrospectionScope.DATABASE)
        # The new result should be cached now
        assert db_info2 is not None

        # Table cache should still be cached
        tables2 = backend_with_tables.introspector.list_tables()
        assert tables is tables2

    def test_invalidate_table_scope(self, backend_with_tables):
        """Test invalidating table scope."""
        # Populate caches
        tables = backend_with_tables.introspector.list_tables()
        columns = backend_with_tables.introspector.list_columns("users")

        # Invalidate table scope
        backend_with_tables.introspector.invalidate_cache(
            scope=IntrospectionScope.TABLE
        )

        # Table cache should be cleared
        tables2 = backend_with_tables.introspector.list_tables()
        assert tables is not tables2

        # Column cache should still be cached
        columns2 = backend_with_tables.introspector.list_columns("users")
        assert columns is columns2

    def test_invalidate_specific_table(self, backend_with_tables):
        """Test invalidating cache for specific table."""
        # Populate caches
        users_info = backend_with_tables.introspector.get_table_info("users")
        posts_info = backend_with_tables.introspector.get_table_info("posts")

        # Invalidate only users table
        backend_with_tables.introspector.invalidate_cache(
            scope=IntrospectionScope.TABLE,
            name="users"
        )

        # Users table cache should be cleared
        users_info2 = backend_with_tables.introspector.get_table_info("users")
        assert users_info is not users_info2

        # Posts table cache should still be cached
        posts_info2 = backend_with_tables.introspector.get_table_info("posts")
        assert posts_info is posts_info2


class TestCacheExpiration:
    """Tests for cache expiration behavior."""

    def test_cache_ttl(self, backend_with_tables):
        """Test that cache has TTL configured."""
        # Check that TTL is set
        assert hasattr(backend_with_tables.introspector, "_cache_ttl")
        assert backend_with_tables.introspector._cache_ttl > 0

    def test_expired_cache_not_returned(self, snowflake_backend_single):
        """Test that expired cache entries are not returned."""
        # Set very short TTL
        snowflake_backend_single.introspector._cache_ttl = 0.01  # 10ms

        # Get database info
        db_info1 = snowflake_backend_single.introspector.get_database_info()

        # Wait for cache to expire
        time.sleep(0.05)

        # Get again - should fetch fresh data
        db_info2 = snowflake_backend_single.introspector.get_database_info()

        # Different objects because cache expired
        assert db_info1 is not db_info2


class TestCacheThreadSafety:
    """Tests for cache thread safety."""

    def test_cache_lock_exists(self, backend_with_tables):
        """Test that cache lock exists."""
        assert hasattr(backend_with_tables.introspector, "_cache_lock")

    @pytest.mark.skip(reason="Snowflake connections are not thread-safe; concurrent DB access on a single connection is expected to fail")
    def test_concurrent_cache_access(self, backend_with_tables):
        """Test concurrent cache access."""
        import threading

        results = []
        errors = []

        def read_cache():
            try:
                for _ in range(10):
                    info = backend_with_tables.introspector.get_database_info()
                    results.append(info)
            except Exception as e:
                errors.append(e)

        def clear_cache():
            try:
                for _ in range(5):
                    backend_with_tables.introspector.clear_cache()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=read_cache)
            for _ in range(3)
        ]
        threads.append(threading.Thread(target=clear_cache))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No exceptions should have occurred
        assert len(errors) == 0
        assert len(results) > 0


class TestCacheKeys:
    """Tests for cache key generation."""

    def test_cache_key_generation(self, snowflake_backend_single):
        """Test that cache keys are generated correctly."""
        key = snowflake_backend_single.introspector._make_cache_key(
            IntrospectionScope.TABLE,
            "users",
            schema=snowflake_backend_single.config.database
        )

        assert "table" in key
        assert "users" in key

    def test_cache_key_with_extra(self, snowflake_backend_single):
        """Test cache key with extra component."""
        key = snowflake_backend_single.introspector._make_cache_key(
            IntrospectionScope.TABLE,
            schema=snowflake_backend_single.config.database,
            extra="True"
        )

        assert "table" in key
        assert "True" in key

    def test_cache_key_uniqueness(self, snowflake_backend_single):
        """Test that different parameters produce different keys."""
        key1 = snowflake_backend_single.introspector._make_cache_key(
            IntrospectionScope.TABLE,
            "users"
        )
        key2 = snowflake_backend_single.introspector._make_cache_key(
            IntrospectionScope.TABLE,
            "posts"
        )
        key3 = snowflake_backend_single.introspector._make_cache_key(
            IntrospectionScope.COLUMN,
            "users"
        )

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3


class TestAsyncCacheManagement:
    """Async tests for cache management."""

    @pytest.mark.asyncio
    async def test_async_clear_introspection_cache(self, async_backend_with_tables):
        """Test async clear_introspection_cache clears all cache."""
        # First, populate cache
        await async_backend_with_tables.introspector.get_database_info()
        await async_backend_with_tables.introspector.list_tables()
        await async_backend_with_tables.introspector.list_columns("users")

        # Clear cache
        async_backend_with_tables.introspector.clear_cache()

        # Verify cache is empty
        assert len(async_backend_with_tables.introspector._cache) == 0

    @pytest.mark.asyncio
    async def test_async_cache_hit(self, async_backend_with_tables):
        """Test that async cached results are returned."""
        db_info1 = await async_backend_with_tables.introspector.get_database_info()
        db_info2 = await async_backend_with_tables.introspector.get_database_info()

        # Same object reference means it was cached
        assert db_info1 is db_info2

    @pytest.mark.asyncio
    async def test_async_cache_miss_after_clear(self, async_backend_with_tables):
        """Test async cache miss after clear."""
        db_info1 = await async_backend_with_tables.introspector.get_database_info()
        async_backend_with_tables.introspector.clear_cache()
        db_info2 = await async_backend_with_tables.introspector.get_database_info()

        # Different object reference means cache was cleared
        assert db_info1 is not db_info2

    @pytest.mark.asyncio
    async def test_async_invalidate_all_scopes(self, async_backend_with_tables):
        """Test async invalidating all caches."""
        # Populate multiple caches
        await async_backend_with_tables.introspector.get_database_info()
        await async_backend_with_tables.introspector.list_tables()
        await async_backend_with_tables.introspector.list_columns("users")

        # Invalidate all
        async_backend_with_tables.introspector.invalidate_cache()

        assert len(async_backend_with_tables.introspector._cache) == 0

    @pytest.mark.asyncio
    async def test_async_invalidate_specific_scope(self, async_backend_with_tables):
        """Test async invalidating specific scope."""
        # Populate caches
        db_info = await async_backend_with_tables.introspector.get_database_info()
        tables = await async_backend_with_tables.introspector.list_tables()

        # Invalidate only database scope
        async_backend_with_tables.introspector.invalidate_cache(
            scope=IntrospectionScope.DATABASE
        )

        # Database cache should be cleared
        db_info2 = await async_backend_with_tables.introspector.get_database_info()
        assert db_info2 is not None

        # Table cache should still be cached
        tables2 = await async_backend_with_tables.introspector.list_tables()
        assert tables is tables2
