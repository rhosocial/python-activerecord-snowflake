# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_introspection_database.py
"""
Tests for Snowflake database information introspection.

This module tests the get_database_info method and related functionality
for retrieving database metadata.
"""

import pytest

from rhosocial.activerecord.backend.introspection.types import DatabaseInfo


class TestDatabaseInfo:
    """Tests for database information introspection."""

    def test_get_database_info(self, snowflake_backend):
        """Test get_database_info returns valid DatabaseInfo."""
        db_info = snowflake_backend.introspector.get_database_info()

        assert isinstance(db_info, DatabaseInfo)
        assert db_info.name is not None
        assert db_info.vendor == "Snowflake"
        assert db_info.version is not None
        assert db_info.version_tuple is not None

    def test_database_info_version_tuple_format(self, snowflake_backend):
        """Test that version_tuple is correctly formatted."""
        db_info = snowflake_backend.introspector.get_database_info()

        assert isinstance(db_info.version_tuple, tuple)
        assert len(db_info.version_tuple) >= 2
        assert all(isinstance(x, int) for x in db_info.version_tuple)

    def test_database_info_encoding(self, snowflake_backend):
        """Test that encoding is populated."""
        db_info = snowflake_backend.introspector.get_database_info()

        # Snowflake should report charset/encoding
        assert db_info.encoding is not None

    def test_database_info_collation(self, snowflake_backend):
        """Test that collation is populated."""
        db_info = snowflake_backend.introspector.get_database_info()

        # Snowflake should report collation
        assert db_info.collation is not None

    def test_database_info_caching(self, snowflake_backend):
        """Test that database info is cached."""
        db_info1 = snowflake_backend.introspector.get_database_info()
        db_info2 = snowflake_backend.introspector.get_database_info()

        # Should return the same cached object
        assert db_info1 is db_info2

    def test_database_info_cache_invalidation(self, snowflake_backend):
        """Test that cache can be invalidated."""
        db_info1 = snowflake_backend.introspector.get_database_info()

        snowflake_backend.introspector.clear_cache()

        db_info2 = snowflake_backend.introspector.get_database_info()

        # Should be different objects after cache clear
        assert db_info1 is not db_info2
        # But with same values
        assert db_info1.version == db_info2.version

    def test_database_info_matches_server_version(self, snowflake_backend):
        """Test that database info matches server version."""
        db_info = snowflake_backend.introspector.get_database_info()
        server_version = snowflake_backend.get_server_version()

        assert db_info.version_tuple == server_version


class TestIntrospectionCapabilities:
    """Tests for introspection capability declarations."""

    def test_supports_introspection(self, snowflake_backend):
        """Test that Snowflake backend supports introspection."""
        assert snowflake_backend.dialect.supports_introspection() is True

    def test_supports_database_info(self, snowflake_backend):
        """Test that Snowflake backend supports database info."""
        assert snowflake_backend.dialect.supports_database_info() is True

    def test_supports_table_introspection(self, snowflake_backend):
        """Test that Snowflake backend supports table introspection."""
        assert snowflake_backend.dialect.supports_table_introspection() is True

    def test_supports_column_introspection(self, snowflake_backend):
        """Test that Snowflake backend supports column introspection."""
        assert snowflake_backend.dialect.supports_column_introspection() is True

    def test_supports_index_introspection(self, snowflake_backend):
        """Test that Snowflake backend supports index introspection."""
        assert snowflake_backend.dialect.supports_index_introspection() is True

    def test_supports_foreign_key_introspection(self, snowflake_backend):
        """Test that Snowflake backend supports foreign key introspection."""
        assert snowflake_backend.dialect.supports_foreign_key_introspection() is True

    def test_supports_view_introspection(self, snowflake_backend):
        """Test that Snowflake backend supports view introspection."""
        assert snowflake_backend.dialect.supports_view_introspection() is True

    def test_supports_trigger_introspection(self, snowflake_backend):
        """Test that Snowflake backend supports trigger introspection."""
        assert snowflake_backend.dialect.supports_trigger_introspection() is True

    def test_get_supported_introspection_scopes(self, snowflake_backend):
        """Test that all expected introspection scopes are supported."""
        from rhosocial.activerecord.backend.introspection.types import IntrospectionScope

        scopes = snowflake_backend.dialect.get_supported_introspection_scopes()

        expected_scopes = [
            IntrospectionScope.DATABASE,
            IntrospectionScope.TABLE,
            IntrospectionScope.COLUMN,
            IntrospectionScope.INDEX,
            IntrospectionScope.FOREIGN_KEY,
            IntrospectionScope.VIEW,
            IntrospectionScope.TRIGGER,
        ]

        for expected_scope in expected_scopes:
            assert expected_scope in scopes


class TestAsyncDatabaseInfo:
    """Async tests for database information introspection."""

    @pytest.mark.asyncio
    async def test_async_get_database_info(self, async_snowflake_backend):
        """Test async get_database_info returns valid DatabaseInfo."""
        db_info = await async_snowflake_backend.introspector.get_database_info()

        assert isinstance(db_info, DatabaseInfo)
        assert db_info.name is not None
        assert db_info.vendor == "Snowflake"

    @pytest.mark.asyncio
    async def test_async_database_info_caching(self, async_snowflake_backend):
        """Test that async database info is cached."""
        db_info1 = await async_snowflake_backend.introspector.get_database_info()
        db_info2 = await async_snowflake_backend.introspector.get_database_info()

        # Should return the same cached object
        assert db_info1 is db_info2

    @pytest.mark.asyncio
    async def test_async_database_info_cache_invalidation(self, async_snowflake_backend):
        """Test that async cache can be invalidated."""
        db_info1 = await async_snowflake_backend.introspector.get_database_info()

        async_snowflake_backend.introspector.clear_cache()

        db_info2 = await async_snowflake_backend.introspector.get_database_info()

        # Should be different objects after cache clear
        assert db_info1 is not db_info2

    @pytest.mark.asyncio
    async def test_async_supports_introspection(self, async_snowflake_backend):
        """Test that async Snowflake backend supports introspection."""
        assert async_snowflake_backend.dialect.supports_introspection() is True
