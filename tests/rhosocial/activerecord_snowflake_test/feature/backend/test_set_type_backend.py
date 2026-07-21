# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_set_type_backend.py
"""
Snowflake SET type integration tests using real database connection.

This module tests the Snowflake-specific SET type functionality with actual database operations.
"""
import pytest
import pytest_asyncio


class TestSnowflakeSetTypeBackend:
    """Synchronous tests for Snowflake SET type with real database."""

    def test_supports_set_type(self, snowflake_backend):
        """Test that SET type is supported."""
        dialect = snowflake_backend.dialect
        assert dialect.supports_set_type()

    def test_create_table_with_set_column(self, snowflake_backend):
        """Test creating table with SET column type."""
        snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_set_table (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tags SET('red', 'green', 'blue', 'yellow'),
                status SET('active', 'pending', 'archived')
            )
        """)

        snowflake_backend.execute(
            "INSERT INTO test_set_table (tags, status) VALUES ('red', 'active')"
        )

        result = snowflake_backend.execute(
            "SELECT tags, status FROM test_set_table WHERE id = 1"
        )

        assert len(result.data) == 1
        assert result.data[0]['tags'] == 'red'
        assert result.data[0]['status'] == 'active'

        snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_set_table")

    def test_insert_and_query_set_value(self, snowflake_backend):
        """Test inserting and querying SET values."""
        snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_set_insert (
                id INT AUTO_INCREMENT PRIMARY KEY,
                colors SET('red', 'green', 'blue')
            )
        """)

        snowflake_backend.execute(
            "INSERT INTO test_set_insert (colors) VALUES ('red')"
        )

        snowflake_backend.execute(
            "INSERT INTO test_set_insert (colors) VALUES ('red,green')"
        )

        snowflake_backend.execute(
            "INSERT INTO test_set_insert (colors) VALUES ('blue,red,green')"
        )

        result = snowflake_backend.execute(
            "SELECT colors FROM test_set_insert ORDER BY id"
        )

        assert result.data[0]['colors'] == 'red'
        assert result.data[1]['colors'] == 'red,green'
        assert result.data[2]['colors'] == 'red,green,blue'

        snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_set_insert")

    def test_find_in_set_function(self, snowflake_backend):
        """Test FIND_IN_SET function for SET columns."""
        snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_find_in_set (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tags SET('snowflake', 'python', 'database', 'backend')
            )
        """)

        snowflake_backend.execute(
            "INSERT INTO test_find_in_set (tags) VALUES ('mariadb,python')"
        )
        snowflake_backend.execute(
            "INSERT INTO test_find_in_set (tags) VALUES ('database')"
        )
        snowflake_backend.execute(
            "INSERT INTO test_find_in_set (tags) VALUES ('backend,mariadb')"
        )

        result = snowflake_backend.execute(
            "SELECT id, tags FROM test_find_in_set WHERE FIND_IN_SET('snowflake', tags) > 0"
        )

        assert len(result.data) == 2
        assert result.data[0]['id'] == 1
        assert result.data[1]['id'] == 3

        snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_find_in_set")

    def test_format_set_literal_integration(self, snowflake_backend):
        """Test format_set_literal with database execution."""
        snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_set_literal (
                id INT AUTO_INCREMENT PRIMARY KEY,
                colors SET('red', 'green', 'blue')
            )
        """)

        dialect = snowflake_backend.dialect
        sql_literal, params = dialect.format_set_literal(['red', 'blue'], ['red', 'green', 'blue'])

        snowflake_backend.execute(
            f"INSERT INTO test_set_literal (colors) VALUES ({sql_literal})",
            params
        )

        result = snowflake_backend.execute(
            "SELECT colors FROM test_set_literal WHERE id = 1"
        )

        assert result.data[0]['colors'] == 'red,blue'

        snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_set_literal")

    def test_format_find_in_set_integration(self, snowflake_backend):
        """Test format_find_in_set with database execution."""
        snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_find_format (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tags SET('a', 'b', 'c', 'd')
            )
        """)

        snowflake_backend.execute("INSERT INTO test_find_format (tags) VALUES ('a,b')")
        snowflake_backend.execute("INSERT INTO test_find_format (tags) VALUES ('c,d')")
        snowflake_backend.execute("INSERT INTO test_find_format (tags) VALUES ('a,c')")

        dialect = snowflake_backend.dialect
        condition, params = dialect.format_find_in_set('a', 'tags')

        result = snowflake_backend.execute(
            f"SELECT id, tags FROM test_find_format WHERE {condition}",
            params
        )

        assert len(result.data) == 2
        ids = [row['id'] for row in result.data]
        assert 1 in ids
        assert 3 in ids

        snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_find_format")

    def test_format_set_contains_integration(self, snowflake_backend):
        """Test format_set_contains with database execution."""
        snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_contains_format (
                id INT AUTO_INCREMENT PRIMARY KEY,
                permissions SET('read', 'write', 'execute', 'admin')
            )
        """)

        snowflake_backend.execute("INSERT INTO test_contains_format (permissions) VALUES ('read,write')")
        snowflake_backend.execute("INSERT INTO test_contains_format (permissions) VALUES ('read,execute')")
        snowflake_backend.execute("INSERT INTO test_contains_format (permissions) VALUES ('read,write,admin')")

        dialect = snowflake_backend.dialect
        condition, params = dialect.format_set_contains('permissions', ['read', 'write'])

        result = snowflake_backend.execute(
            f"SELECT id, permissions FROM test_contains_format WHERE {condition}",
            params
        )

        assert len(result.data) == 2
        permissions_values = [row['permissions'] for row in result.data]
        assert 'read,write' in permissions_values
        assert 'read,write,admin' in permissions_values

        snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_contains_format")

    def test_set_with_null_value(self, snowflake_backend):
        """Test SET column with NULL values."""
        snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_set_null (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tags SET('a', 'b', 'c') NULL
            )
        """)

        snowflake_backend.execute("INSERT INTO test_set_null (tags) VALUES (NULL)")
        snowflake_backend.execute("INSERT INTO test_set_null (tags) VALUES ('a,b')")

        result = snowflake_backend.execute(
            "SELECT tags FROM test_set_null ORDER BY id"
        )

        assert result.data[0]['tags'] is None
        assert result.data[1]['tags'] == 'a,b'

        snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_set_null")

    def test_set_count_function(self, snowflake_backend):
        """Test counting SET values."""
        snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_set_count (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tags SET('a', 'b', 'c', 'd')
            )
        """)

        snowflake_backend.execute("INSERT INTO test_set_count (tags) VALUES ('a')")
        snowflake_backend.execute("INSERT INTO test_set_count (tags) VALUES ('a,b')")
        snowflake_backend.execute("INSERT INTO test_set_count (tags) VALUES ('a,b,c,d')")

        result = snowflake_backend.execute(
            "SELECT COUNT(*) as cnt FROM test_set_count WHERE FIND_IN_SET('a', tags) > 0"
        )

        assert result.data[0]['cnt'] == 3

        snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_set_count")


class TestAsyncSnowflakeSetTypeBackend:
    """Asynchronous tests for Snowflake SET type with real database."""

    @pytest.mark.asyncio
    async def test_async_supports_set_type(self, async_snowflake_backend):
        """Test that SET type is supported (async)."""
        dialect = async_snowflake_backend.dialect
        assert dialect.supports_set_type()

    @pytest.mark.asyncio
    async def test_async_create_table_with_set_column(self, async_snowflake_backend):
        """Test creating table with SET column type (async)."""
        await async_snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_async_set_table (
                id INT AUTO_INCREMENT PRIMARY KEY,
                categories SET('news', 'sports', 'tech', 'entertainment')
            )
        """)

        await async_snowflake_backend.execute(
            "INSERT INTO test_async_set_table (categories) VALUES ('news,sports')"
        )

        result = await async_snowflake_backend.execute(
            "SELECT categories FROM test_async_set_table WHERE id = 1"
        )

        assert len(result.data) == 1
        assert result.data[0]['categories'] == 'news,sports'

        await async_snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_set_table")

    @pytest.mark.asyncio
    async def test_async_insert_and_query_set_value(self, async_snowflake_backend):
        """Test inserting and querying SET values (async)."""
        await async_snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_async_set_insert (
                id INT AUTO_INCREMENT PRIMARY KEY,
                colors SET('red', 'green', 'blue')
            )
        """)

        await async_snowflake_backend.execute(
            "INSERT INTO test_async_set_insert (colors) VALUES ('red')"
        )

        await async_snowflake_backend.execute(
            "INSERT INTO test_async_set_insert (colors) VALUES ('green,blue')"
        )

        result = await async_snowflake_backend.execute(
            "SELECT colors FROM test_async_set_insert ORDER BY id"
        )

        assert result.data[0]['colors'] == 'red'
        assert result.data[1]['colors'] == 'green,blue'

        await async_snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_set_insert")

    @pytest.mark.asyncio
    async def test_async_find_in_set_function(self, async_snowflake_backend):
        """Test FIND_IN_SET function for SET columns (async)."""
        await async_snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_async_find (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tags SET('snowflake', 'python', 'database')
            )
        """)

        await async_snowflake_backend.execute(
            "INSERT INTO test_async_find (tags) VALUES ('mariadb,python')"
        )
        await async_snowflake_backend.execute(
            "INSERT INTO test_async_find (tags) VALUES ('database')"
        )

        result = await async_snowflake_backend.execute(
            "SELECT id, tags FROM test_async_find WHERE FIND_IN_SET('snowflake', tags) > 0"
        )

        assert len(result.data) == 1
        assert result.data[0]['id'] == 1

        await async_snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_find")

    @pytest.mark.asyncio
    async def test_async_format_set_literal_integration(self, async_snowflake_backend):
        """Test format_set_literal with database execution (async)."""
        await async_snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_async_set_literal (
                id INT AUTO_INCREMENT PRIMARY KEY,
                colors SET('red', 'green', 'blue')
            )
        """)

        dialect = async_snowflake_backend.dialect
        sql_literal, params = dialect.format_set_literal(['green', 'red'], ['red', 'green', 'blue'])

        await async_snowflake_backend.execute(
            f"INSERT INTO test_async_set_literal (colors) VALUES ({sql_literal})",
            params
        )

        result = await async_snowflake_backend.execute(
            "SELECT colors FROM test_async_set_literal WHERE id = 1"
        )

        assert result.data[0]['colors'] == 'red,green'

        await async_snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_set_literal")

    @pytest.mark.asyncio
    async def test_async_format_find_in_set_integration(self, async_snowflake_backend):
        """Test format_find_in_set with database execution (async)."""
        await async_snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_async_find_format (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tags SET('x', 'y', 'z')
            )
        """)

        await async_snowflake_backend.execute("INSERT INTO test_async_find_format (tags) VALUES ('x,y')")
        await async_snowflake_backend.execute("INSERT INTO test_async_find_format (tags) VALUES ('z')")

        dialect = async_snowflake_backend.dialect
        condition, params = dialect.format_find_in_set('x', 'tags')

        result = await async_snowflake_backend.execute(
            f"SELECT id, tags FROM test_async_find_format WHERE {condition}",
            params
        )

        assert len(result.data) == 1
        assert result.data[0]['id'] == 1

        await async_snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_find_format")

    @pytest.mark.asyncio
    async def test_async_format_set_contains_integration(self, async_snowflake_backend):
        """Test format_set_contains with database execution (async)."""
        await async_snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_async_contains (
                id INT AUTO_INCREMENT PRIMARY KEY,
                roles SET('admin', 'user', 'guest', 'moderator')
            )
        """)

        await async_snowflake_backend.execute("INSERT INTO test_async_contains (roles) VALUES ('admin,user')")
        await async_snowflake_backend.execute("INSERT INTO test_async_contains (roles) VALUES ('guest')")
        await async_snowflake_backend.execute("INSERT INTO test_async_contains (roles) VALUES ('admin,moderator')")

        dialect = async_snowflake_backend.dialect
        condition, params = dialect.format_set_contains('roles', ['admin'])

        result = await async_snowflake_backend.execute(
            f"SELECT id, roles FROM test_async_contains WHERE {condition}",
            params
        )

        assert len(result.data) == 2
        ids = [row['id'] for row in result.data]
        assert 1 in ids
        assert 3 in ids

        await async_snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_contains")

    @pytest.mark.asyncio
    async def test_async_set_with_null_value(self, async_snowflake_backend):
        """Test SET column with NULL values (async)."""
        await async_snowflake_backend.execute("""
            CREATE TEMPORARY TABLE test_async_set_null (
                id INT AUTO_INCREMENT PRIMARY KEY,
                status SET('active', 'inactive') NULL
            )
        """)

        await async_snowflake_backend.execute("INSERT INTO test_async_set_null (status) VALUES (NULL)")
        await async_snowflake_backend.execute("INSERT INTO test_async_set_null (status) VALUES ('active')")

        result = await async_snowflake_backend.execute(
            "SELECT status FROM test_async_set_null ORDER BY id"
        )

        assert result.data[0]['status'] is None
        assert result.data[1]['status'] == 'active'

        await async_snowflake_backend.execute("DROP TEMPORARY TABLE IF EXISTS test_async_set_null")
