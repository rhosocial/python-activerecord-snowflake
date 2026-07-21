# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_introspection_foreign_keys.py
"""
Tests for Snowflake foreign key introspection.

This module tests the list_foreign_keys and get_foreign_key_info methods
for retrieving foreign key metadata.
"""

import pytest

from rhosocial.activerecord.backend.introspection.types import (
    ForeignKeyInfo,
    ReferentialAction,
)


class TestListForeignKeys:
    """Tests for list_foreign_keys method."""

    def test_list_foreign_keys_returns_fk_info(self, backend_with_tables):
        """Test that list_foreign_keys returns ForeignKeyInfo objects."""
        fks = backend_with_tables.introspector.list_foreign_keys("posts")

        assert isinstance(fks, list)
        assert len(fks) > 0

        for fk in fks:
            assert isinstance(fk, ForeignKeyInfo)

    def test_list_foreign_keys_posts_table(self, backend_with_tables):
        """Test foreign keys on posts table."""
        fks = backend_with_tables.introspector.list_foreign_keys("posts")

        assert len(fks) >= 1

        # Find the user_id foreign key
        user_fk = next((fk for fk in fks if fk.referenced_table == "users"), None)
        assert user_fk is not None
        assert "user_id" in user_fk.columns

    def test_list_foreign_keys_post_tags_table(self, backend_with_tables):
        """Test foreign keys on post_tags table (composite FKs)."""
        fks = backend_with_tables.introspector.list_foreign_keys("post_tags")

        assert len(fks) == 2

        referenced_tables = {fk.referenced_table for fk in fks}
        assert "posts" in referenced_tables
        assert "tags" in referenced_tables

    def test_list_foreign_keys_no_fks(self, backend_with_tables):
        """Test list_foreign_keys for table without foreign keys."""
        fks = backend_with_tables.introspector.list_foreign_keys("users")

        # users table has no foreign keys
        assert isinstance(fks, list)
        assert len(fks) == 0

    def test_list_foreign_keys_nonexistent_table(self, backend_with_tables):
        """Test list_foreign_keys for non-existent table."""
        fks = backend_with_tables.introspector.list_foreign_keys("nonexistent")

        # Should return empty list for non-existent table
        assert isinstance(fks, list)
        assert len(fks) == 0

    def test_list_foreign_keys_caching(self, backend_with_tables):
        """Test that foreign key list is cached."""
        fks1 = backend_with_tables.introspector.list_foreign_keys("posts")
        fks2 = backend_with_tables.introspector.list_foreign_keys("posts")

        # Should return the same cached list
        assert fks1 is fks2


class TestGetForeignKeyInfo:
    """Tests for get_foreign_key_info method."""

    def test_get_foreign_key_info_existing(self, backend_with_tables):
        """Test get_foreign_key_info for existing FK."""
        # Get all FKs first to find the name
        fks = backend_with_tables.introspector.list_foreign_keys("posts")
        assert len(fks) > 0

        fk_name = fks[0].name
        fk = backend_with_tables.introspector.get_foreign_key_info("posts", fk_name)

        assert fk is not None
        assert isinstance(fk, ForeignKeyInfo)
        assert fk.name == fk_name

    def test_get_foreign_key_info_nonexistent(self, backend_with_tables):
        """Test get_foreign_key_info for non-existent FK."""
        fk = backend_with_tables.introspector.get_foreign_key_info("posts", "nonexistent")

        assert fk is None


class TestForeignKeyDetails:
    """Tests for detailed foreign key information."""

    def test_foreign_key_referenced_table(self, backend_with_tables):
        """Test referenced table detection."""
        fks = backend_with_tables.introspector.list_foreign_keys("posts")

        user_fk = next((fk for fk in fks if fk.referenced_table == "users"), None)
        assert user_fk is not None

    def test_foreign_key_referenced_columns(self, backend_with_tables):
        """Test referenced columns detection."""
        fks = backend_with_tables.introspector.list_foreign_keys("posts")

        user_fk = next((fk for fk in fks if fk.referenced_table == "users"), None)
        assert user_fk is not None
        assert len(user_fk.referenced_columns) == 1
        assert user_fk.referenced_columns[0] == "id"

    def test_foreign_key_on_delete_cascade(self, backend_with_tables):
        """Test ON DELETE CASCADE detection."""
        fks = backend_with_tables.introspector.list_foreign_keys("posts")

        user_fk = next((fk for fk in fks if fk.referenced_table == "users"), None)
        assert user_fk is not None
        assert user_fk.on_delete == ReferentialAction.CASCADE

    def test_foreign_key_on_delete_no_action(self, backend_with_tables):
        """Test ON DELETE NO ACTION detection."""
        # Create table with NO ACTION
        backend_with_tables.executescript("""
            DROP TABLE IF EXISTS child_no_action;
            DROP TABLE IF EXISTS parent_no_action;

            CREATE TABLE parent_no_action (
                id INT PRIMARY KEY
            ) ENGINE=InnoDB;

            CREATE TABLE child_no_action (
                id INT PRIMARY KEY,
                parent_id INT NOT NULL,
                CONSTRAINT fk_no_action
                    FOREIGN KEY (parent_id)
                    REFERENCES parent_no_action(id)
                    ON DELETE NO ACTION
            ) ENGINE=InnoDB;
        """)

        fks = backend_with_tables.introspector.list_foreign_keys("child_no_action")

        assert len(fks) == 1
        assert fks[0].on_delete == ReferentialAction.NO_ACTION

        backend_with_tables.executescript("""
            DROP TABLE IF EXISTS child_no_action;
            DROP TABLE IF EXISTS parent_no_action;
        """)

    def test_foreign_key_on_update_restrict(self, backend_with_tables):
        """Test ON UPDATE RESTRICT detection."""
        backend_with_tables.executescript("""
            DROP TABLE IF EXISTS child_restrict;
            DROP TABLE IF EXISTS parent_restrict;

            CREATE TABLE parent_restrict (
                id INT PRIMARY KEY
            ) ENGINE=InnoDB;

            CREATE TABLE child_restrict (
                id INT PRIMARY KEY,
                parent_id INT NOT NULL,
                CONSTRAINT fk_restrict
                    FOREIGN KEY (parent_id)
                    REFERENCES parent_restrict(id)
                    ON UPDATE RESTRICT
            ) ENGINE=InnoDB;
        """)

        fks = backend_with_tables.introspector.list_foreign_keys("child_restrict")

        assert len(fks) == 1
        assert fks[0].on_update == ReferentialAction.RESTRICT

        backend_with_tables.executescript("""
            DROP TABLE IF EXISTS child_restrict;
            DROP TABLE IF EXISTS parent_restrict;
        """)

    def test_foreign_key_on_delete_set_null(self, backend_with_tables):
        """Test ON DELETE SET NULL detection."""
        backend_with_tables.executescript("""
            DROP TABLE IF EXISTS child_set_null;
            DROP TABLE IF EXISTS parent_set_null;

            CREATE TABLE parent_set_null (
                id INT PRIMARY KEY
            ) ENGINE=InnoDB;

            CREATE TABLE child_set_null (
                id INT PRIMARY KEY,
                parent_id INT,
                CONSTRAINT fk_set_null
                    FOREIGN KEY (parent_id)
                    REFERENCES parent_set_null(id)
                    ON DELETE SET NULL
            ) ENGINE=InnoDB;
        """)

        fks = backend_with_tables.introspector.list_foreign_keys("child_set_null")

        assert len(fks) == 1
        assert fks[0].on_delete == ReferentialAction.SET_NULL

        backend_with_tables.executescript("""
            DROP TABLE IF EXISTS child_set_null;
            DROP TABLE IF EXISTS parent_set_null;
        """)

    def test_composite_foreign_key_columns(self, backend_with_tables):
        """Test composite foreign key columns."""
        backend_with_tables.executescript("""
            DROP TABLE IF EXISTS child_composite;
            DROP TABLE IF EXISTS parent_composite;

            CREATE TABLE parent_composite (
                col1 INT NOT NULL,
                col2 INT NOT NULL,
                PRIMARY KEY (col1, col2)
            ) ENGINE=InnoDB;

            CREATE TABLE child_composite (
                id INT PRIMARY KEY,
                parent_col1 INT NOT NULL,
                parent_col2 INT NOT NULL,
                CONSTRAINT fk_composite
                    FOREIGN KEY (parent_col1, parent_col2)
                    REFERENCES parent_composite(col1, col2)
            ) ENGINE=InnoDB;
        """)

        fks = backend_with_tables.introspector.list_foreign_keys("child_composite")

        assert len(fks) == 1
        fk = fks[0]

        assert len(fk.columns) == 2
        assert len(fk.referenced_columns) == 2

        assert fk.columns == ["parent_col1", "parent_col2"]
        assert fk.referenced_columns == ["col1", "col2"]

        backend_with_tables.executescript("""
            DROP TABLE IF EXISTS child_composite;
            DROP TABLE IF EXISTS parent_composite;
        """)


class TestAsyncForeignKeyIntrospection:
    """Async tests for foreign key introspection."""

    @pytest.mark.asyncio
    async def test_async_list_foreign_keys(self, async_backend_with_tables):
        """Test async list_foreign_keys returns ForeignKeyInfo objects."""
        fks = await async_backend_with_tables.introspector.list_foreign_keys("posts")

        assert isinstance(fks, list)
        assert len(fks) > 0

        for fk in fks:
            assert isinstance(fk, ForeignKeyInfo)

    @pytest.mark.asyncio
    async def test_async_get_foreign_key_info(self, async_backend_with_tables):
        """Test async get_foreign_key_info for existing FK."""
        fks = await async_backend_with_tables.introspector.list_foreign_keys("posts")
        assert len(fks) > 0

        fk_name = fks[0].name
        fk = await async_backend_with_tables.introspector.get_foreign_key_info("posts", fk_name)

        assert fk is not None
        assert isinstance(fk, ForeignKeyInfo)
        assert fk.name == fk_name

    @pytest.mark.asyncio
    async def test_async_list_foreign_keys_caching(self, async_backend_with_tables):
        """Test that async foreign key list is cached."""
        fks1 = await async_backend_with_tables.introspector.list_foreign_keys("posts")
        fks2 = await async_backend_with_tables.introspector.list_foreign_keys("posts")

        # Should return the same cached list
        assert fks1 is fks2
