# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_introspection_columns.py
"""
Tests for Snowflake column introspection.

This module tests the list_columns, get_column_info, and column_exists methods
for retrieving column metadata.
"""

import pytest

from rhosocial.activerecord.backend.introspection.types import (
    ColumnInfo,
    ColumnNullable,
)


class TestListColumns:
    """Tests for list_columns method."""

    def test_list_columns_returns_column_info(self, backend_with_tables):
        """Test that list_columns returns ColumnInfo objects."""
        columns = backend_with_tables.introspector.list_columns("users")

        assert isinstance(columns, list)
        assert len(columns) > 0

        for col in columns:
            assert isinstance(col, ColumnInfo)

    def test_list_columns_users_table(self, backend_with_tables):
        """Test columns for users table."""
        columns = backend_with_tables.introspector.list_columns("users")
        column_names = [c.name for c in columns]

        assert "id" in column_names
        assert "name" in column_names
        assert "email" in column_names
        assert "age" in column_names
        assert "created_at" in column_names

    def test_list_columns_nonexistent_table(self, backend_with_tables):
        """Test list_columns for non-existent table."""
        columns = backend_with_tables.introspector.list_columns("nonexistent")

        # Should return empty list for non-existent table
        assert isinstance(columns, list)
        assert len(columns) == 0

    def test_list_columns_caching(self, backend_with_tables):
        """Test that column list is cached."""
        columns1 = backend_with_tables.introspector.list_columns("users")
        columns2 = backend_with_tables.introspector.list_columns("users")

        # Should return the same cached list
        assert columns1 is columns2


class TestGetColumnInfo:
    """Tests for get_column_info method."""

    def test_get_column_info_existing(self, backend_with_tables):
        """Test get_column_info for existing column."""
        col = backend_with_tables.introspector.get_column_info("users", "email")

        assert col is not None
        assert isinstance(col, ColumnInfo)
        assert col.name == "email"

    def test_get_column_info_nonexistent_column(self, backend_with_tables):
        """Test get_column_info for non-existent column."""
        col = backend_with_tables.introspector.get_column_info("users", "nonexistent")

        assert col is None

    def test_get_column_info_nonexistent_table(self, backend_with_tables):
        """Test get_column_info for non-existent table."""
        col = backend_with_tables.introspector.get_column_info("nonexistent", "id")

        assert col is None


class TestColumnExists:
    """Tests for column_exists method."""

    def test_column_exists_true(self, backend_with_tables):
        """Test column_exists returns True for existing column."""
        assert backend_with_tables.introspector.column_exists("users", "id") is True
        assert backend_with_tables.introspector.column_exists("users", "email") is True

    def test_column_exists_false(self, backend_with_tables):
        """Test column_exists returns False for non-existent column."""
        assert backend_with_tables.introspector.column_exists("users", "nonexistent") is False


class TestColumnInfoDetails:
    """Tests for detailed column information."""

    def test_column_ordinal_position(self, backend_with_tables):
        """Test column ordinal positions are correct."""
        columns = backend_with_tables.introspector.list_columns("users")

        # Columns should be ordered by ordinal position
        positions = [c.ordinal_position for c in columns]
        assert positions == sorted(positions)

        # First column should be id
        first_col = next(c for c in columns if c.ordinal_position == 1)
        assert first_col.name == "id"

    def test_column_data_type(self, backend_with_tables):
        """Test column data type detection."""
        columns = backend_with_tables.introspector.list_columns("users")

        id_col = next(c for c in columns if c.name == "id")
        assert id_col.data_type == "int"

        name_col = next(c for c in columns if c.name == "name")
        assert name_col.data_type == "varchar"

    def test_column_data_type_full(self, backend_with_tables):
        """Test full data type includes length."""
        columns = backend_with_tables.introspector.list_columns("users")

        name_col = next(c for c in columns if c.name == "name")
        assert "varchar(100)" in name_col.data_type_full.lower()

    def test_column_nullable(self, backend_with_tables):
        """Test nullable column detection."""
        columns = backend_with_tables.introspector.list_columns("users")

        id_col = next(c for c in columns if c.name == "id")
        assert id_col.nullable == ColumnNullable.NOT_NULL

        age_col = next(c for c in columns if c.name == "age")
        assert age_col.nullable == ColumnNullable.NULLABLE

    def test_column_primary_key(self, backend_with_tables):
        """Test primary key detection."""
        columns = backend_with_tables.introspector.list_columns("users")

        id_col = next(c for c in columns if c.name == "id")
        assert id_col.is_primary_key is True

        name_col = next(c for c in columns if c.name == "name")
        assert name_col.is_primary_key is False

    def test_column_unique(self, backend_with_tables):
        """Test unique column detection."""
        columns = backend_with_tables.introspector.list_columns("users")

        email_col = next(c for c in columns if c.name == "email")
        # email has unique index
        assert email_col.is_unique is True

    def test_column_auto_increment(self, backend_with_tables):
        """Test auto increment detection."""
        columns = backend_with_tables.introspector.list_columns("users")

        id_col = next(c for c in columns if c.name == "id")
        assert id_col.is_auto_increment is True

    def test_column_default_value(self, backend_with_tables):
        """Test default value detection."""
        columns = backend_with_tables.introspector.list_columns("posts")

        status_col = next(c for c in columns if c.name == "status")
        assert status_col.default_value is not None

    def test_column_charset_collation(self, backend_with_tables):
        """Test charset and collation detection."""
        columns = backend_with_tables.introspector.list_columns("users")

        name_col = next(c for c in columns if c.name == "name")
        assert name_col.charset is not None
        assert name_col.collation is not None

    def test_column_numeric_precision_scale(self, backend_with_tables):
        """Test numeric precision and scale detection."""
        backend_with_tables.executescript("""
            DROP TABLE IF EXISTS test_numeric;
            CREATE TABLE test_numeric (
                id INT PRIMARY KEY,
                amount DECIMAL(10, 2)
            );
        """)

        columns = backend_with_tables.introspector.list_columns("test_numeric")

        amount_col = next(c for c in columns if c.name == "amount")
        assert amount_col.numeric_precision == 10
        assert amount_col.numeric_scale == 2

        backend_with_tables.executescript("DROP TABLE IF EXISTS test_numeric;")

    def test_column_character_maximum_length(self, backend_with_tables):
        """Test character maximum length detection."""
        columns = backend_with_tables.introspector.list_columns("users")

        name_col = next(c for c in columns if c.name == "name")
        assert name_col.character_maximum_length == 100

    def test_enum_column_type(self, backend_with_tables):
        """Test ENUM column type detection."""
        columns = backend_with_tables.introspector.list_columns("posts")

        status_col = next(c for c in columns if c.name == "status")
        assert "enum" in status_col.data_type_full.lower()
        assert "draft" in status_col.data_type_full.lower()

    def test_text_column_type(self, backend_with_tables):
        """Test TEXT column type detection."""
        columns = backend_with_tables.introspector.list_columns("posts")

        content_col = next(c for c in columns if c.name == "content")
        assert content_col.data_type == "text"


class TestCompositePrimaryKey:
    """Tests for composite primary key detection."""

    def test_composite_primary_key(self, backend_with_tables):
        """Test composite primary key detection."""
        columns = backend_with_tables.introspector.list_columns("post_tags")

        pk_columns = [c for c in columns if c.is_primary_key]
        assert len(pk_columns) == 2

        pk_col_names = {c.name for c in pk_columns}
        assert "post_id" in pk_col_names
        assert "tag_id" in pk_col_names


class TestAsyncColumnIntrospection:
    """Async tests for column introspection."""

    @pytest.mark.asyncio
    async def test_async_list_columns(self, async_backend_with_tables):
        """Test async list_columns returns ColumnInfo objects."""
        columns = await async_backend_with_tables.introspector.list_columns("users")

        assert isinstance(columns, list)
        assert len(columns) > 0

        for col in columns:
            assert isinstance(col, ColumnInfo)

    @pytest.mark.asyncio
    async def test_async_get_column_info(self, async_backend_with_tables):
        """Test async get_column_info for existing column."""
        col = await async_backend_with_tables.introspector.get_column_info("users", "email")

        assert col is not None
        assert isinstance(col, ColumnInfo)
        assert col.name == "email"

    @pytest.mark.asyncio
    async def test_async_column_exists(self, async_backend_with_tables):
        """Test async column_exists returns True for existing column."""
        exists = await async_backend_with_tables.introspector.column_exists("users", "id")
        assert exists is True

    @pytest.mark.asyncio
    async def test_async_list_columns_caching(self, async_backend_with_tables):
        """Test that async column list is cached."""
        columns1 = await async_backend_with_tables.introspector.list_columns("users")
        columns2 = await async_backend_with_tables.introspector.list_columns("users")

        # Should return the same cached list
        assert columns1 is columns2
