# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_introspection_indexes.py
"""
Tests for Snowflake index introspection.

This module tests the list_indexes, get_index_info, and get_primary_key methods
for retrieving index metadata.
"""

import pytest

from rhosocial.activerecord.backend.introspection.types import (
    IndexInfo,
    IndexType,
    IndexColumnInfo,
)


class TestListIndexes:
    """Tests for list_indexes method."""

    def test_list_indexes_returns_index_info(self, backend_with_tables):
        """Test that list_indexes returns IndexInfo objects."""
        indexes = backend_with_tables.introspector.list_indexes("users")

        assert isinstance(indexes, list)
        assert len(indexes) > 0

        for idx in indexes:
            assert isinstance(idx, IndexInfo)

    def test_list_indexes_all_indexes_present(self, backend_with_tables):
        """Test that all indexes are returned."""
        indexes = backend_with_tables.introspector.list_indexes("users")
        index_names = [i.name for i in indexes]

        # PRIMARY key is always present
        assert "PRIMARY" in index_names
        # Unique index on email
        assert "idx_users_email" in index_names
        # Composite index on name, age
        assert "idx_users_name_age" in index_names

    def test_list_indexes_nonexistent_table(self, backend_with_tables):
        """Test list_indexes for non-existent table."""
        indexes = backend_with_tables.introspector.list_indexes("nonexistent")

        # Should return empty list for non-existent table
        assert isinstance(indexes, list)
        assert len(indexes) == 0

    def test_list_indexes_caching(self, backend_with_tables):
        """Test that index list is cached."""
        indexes1 = backend_with_tables.introspector.list_indexes("users")
        indexes2 = backend_with_tables.introspector.list_indexes("users")

        # Should return the same cached list
        assert indexes1 is indexes2


class TestGetIndexInfo:
    """Tests for get_index_info method."""

    def test_get_index_info_existing(self, backend_with_tables):
        """Test get_index_info for existing index."""
        idx = backend_with_tables.introspector.get_index_info("users", "idx_users_email")

        assert idx is not None
        assert isinstance(idx, IndexInfo)
        assert idx.name == "idx_users_email"
        assert idx.table_name == "users"

    def test_get_index_info_nonexistent(self, backend_with_tables):
        """Test get_index_info for non-existent index."""
        idx = backend_with_tables.introspector.get_index_info("users", "nonexistent")

        assert idx is None


class TestGetPrimaryKey:
    """Tests for get_primary_key method."""

    def test_get_primary_key_single(self, backend_with_tables):
        """Test get_primary_key for table with single-column PK."""
        pk = backend_with_tables.introspector.get_primary_key("users")

        assert pk is not None
        assert pk.is_primary is True
        assert len(pk.columns) >= 1
        assert pk.columns[0].name == "id"

    def test_get_primary_key_composite(self, backend_with_tables):
        """Test get_primary_key for table with composite PK."""
        pk = backend_with_tables.introspector.get_primary_key("post_tags")

        assert pk is not None
        assert pk.is_primary is True
        assert len(pk.columns) == 2

        column_names = [c.name for c in pk.columns]
        assert "post_id" in column_names
        assert "tag_id" in column_names


class TestIndexInfoDetails:
    """Tests for detailed index information."""

    def test_index_is_unique(self, backend_with_tables):
        """Test unique index detection."""
        indexes = backend_with_tables.introspector.list_indexes("users")

        email_idx = next((i for i in indexes if i.name == "idx_users_email"), None)
        assert email_idx is not None
        assert email_idx.is_unique is True

    def test_index_is_non_unique(self, backend_with_tables):
        """Test non-unique index detection."""
        indexes = backend_with_tables.introspector.list_indexes("posts")

        user_idx = next((i for i in indexes if i.name == "idx_posts_user_id"), None)
        assert user_idx is not None
        assert user_idx.is_unique is False

    def test_index_type_btree(self, backend_with_tables):
        """Test BTREE index type detection."""
        indexes = backend_with_tables.introspector.list_indexes("users")

        for idx in indexes:
            # Snowflake default is BTREE
            assert idx.index_type in (IndexType.BTREE, IndexType.HASH)

    def test_index_columns(self, backend_with_tables):
        """Test index column information."""
        indexes = backend_with_tables.introspector.list_indexes("users")

        name_age_idx = next(i for i in indexes if i.name == "idx_users_name_age")
        assert len(name_age_idx.columns) == 2

        column_names = [c.name for c in name_age_idx.columns]
        assert "name" in column_names
        assert "age" in column_names

    def test_index_column_ordinal_positions(self, backend_with_tables):
        """Test index column ordinal positions."""
        indexes = backend_with_tables.introspector.list_indexes("users")

        name_age_idx = next(i for i in indexes if i.name == "idx_users_name_age")
        positions = [c.ordinal_position for c in name_age_idx.columns]

        assert positions[0] == 1
        assert positions[1] == 2

    def test_primary_key_detection_in_indexes(self, backend_with_tables):
        """Test that primary key is detected in index list."""
        indexes = backend_with_tables.introspector.list_indexes("users")

        pk_indexes = [i for i in indexes if i.is_primary]

        # Snowflake uses 'PRIMARY' as the name for primary key index
        assert len(pk_indexes) == 1
        assert pk_indexes[0].name == "PRIMARY"

    def test_multi_table_indexes(self, backend_with_tables):
        """Test indexes for multiple tables."""
        users_indexes = backend_with_tables.introspector.list_indexes("users")
        posts_indexes = backend_with_tables.introspector.list_indexes("posts")

        assert len(users_indexes) > 0
        assert len(posts_indexes) > 0

        # Verify index names are different (except PRIMARY)
        users_idx_names = {i.name for i in users_indexes}
        posts_idx_names = {i.name for i in posts_indexes}

        # PRIMARY exists in both, but other indexes should be unique per table
        non_pk_users = users_idx_names - {"PRIMARY"}
        non_pk_posts = posts_idx_names - {"PRIMARY"}
        assert not non_pk_users.intersection(non_pk_posts)


class TestFulltextIndex:
    """Tests for FULLTEXT index introspection."""

    def test_fulltext_index_detection(self, backend_with_tables):
        """Test FULLTEXT index type detection."""
        backend_with_tables.executescript("""
            DROP TABLE IF EXISTS articles;
            CREATE TABLE articles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255),
                content TEXT,
                FULLTEXT INDEX idx_fulltext_content (content)
            ) ENGINE=InnoDB;
        """)

        indexes = backend_with_tables.introspector.list_indexes("articles")

        fulltext_idx = next((i for i in indexes if i.name == "idx_fulltext_content"), None)
        assert fulltext_idx is not None
        assert fulltext_idx.index_type == IndexType.FULLTEXT

        backend_with_tables.executescript("DROP TABLE IF EXISTS articles;")


class TestAsyncIndexIntrospection:
    """Async tests for index introspection."""

    @pytest.mark.asyncio
    async def test_async_list_indexes(self, async_backend_with_tables):
        """Test async list_indexes returns IndexInfo objects."""
        indexes = await async_backend_with_tables.introspector.list_indexes("users")

        assert isinstance(indexes, list)
        assert len(indexes) > 0

        for idx in indexes:
            assert isinstance(idx, IndexInfo)

    @pytest.mark.asyncio
    async def test_async_get_index_info(self, async_backend_with_tables):
        """Test async get_index_info for existing index."""
        idx = await async_backend_with_tables.introspector.get_index_info("users", "idx_users_email")

        assert idx is not None
        assert isinstance(idx, IndexInfo)
        assert idx.name == "idx_users_email"

    @pytest.mark.asyncio
    async def test_async_get_primary_key(self, async_backend_with_tables):
        """Test async get_primary_key for table with single-column PK."""
        pk = await async_backend_with_tables.introspector.get_primary_key("users")

        assert pk is not None
        assert pk.is_primary is True
        assert len(pk.columns) >= 1

    @pytest.mark.asyncio
    async def test_async_list_indexes_caching(self, async_backend_with_tables):
        """Test that async index list is cached."""
        indexes1 = await async_backend_with_tables.introspector.list_indexes("users")
        indexes2 = await async_backend_with_tables.introspector.list_indexes("users")

        # Should return the same cached list
        assert indexes1 is indexes2
