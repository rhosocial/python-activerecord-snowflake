# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_crud_backend.py
"""
Snowflake backend CRUD tests using real database connection.

This module tests basic CRUD operations using Snowflake backend with real database.
Each test has sync and async versions for complete coverage.
"""
import pytest
import pytest_asyncio
from decimal import Decimal


class TestMySQLCRUDBackend:
    """Synchronous CRUD tests for Snowflake backend."""

    @pytest.fixture
    def test_table(self, snowflake_backend):
        """Create a test table."""
        snowflake_backend.execute("DROP TABLE IF EXISTS test_crud_table")
        snowflake_backend.execute("""
            CREATE TABLE test_crud_table (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                age INT,
                balance DECIMAL(10, 2)
            )
        """)
        yield "test_crud_table"
        snowflake_backend.execute("DROP TABLE IF EXISTS test_crud_table")

    def test_insert_and_fetch(self, snowflake_backend, test_table):
        """Test inserting data and fetching it back."""
        result = snowflake_backend.execute(
            "INSERT INTO test_crud_table (name, age, balance) VALUES (%s, %s, %s)",
            ("Alice", 25, Decimal("100.50"))
        )
        assert result.affected_rows == 1

        row = snowflake_backend.fetch_one(
            "SELECT * FROM test_crud_table WHERE name = %s",
            ("Alice",)
        )
        assert row is not None
        assert row["name"] == "Alice"
        assert row["age"] == 25
        assert row["balance"] == Decimal("100.50")

    def test_update_and_verify(self, snowflake_backend, test_table):
        """Test updating data and verifying the change."""
        snowflake_backend.execute(
            "INSERT INTO test_crud_table (name, age, balance) VALUES (%s, %s, %s)",
            ("Bob", 30, Decimal("200.00"))
        )

        result = snowflake_backend.execute(
            "UPDATE test_crud_table SET age = %s, balance = %s WHERE name = %s",
            (31, Decimal("250.75"), "Bob")
        )
        assert result.affected_rows == 1

        row = snowflake_backend.fetch_one(
            "SELECT age, balance FROM test_crud_table WHERE name = %s",
            ("Bob",)
        )
        assert row["age"] == 31
        assert row["balance"] == Decimal("250.75")

    def test_delete_and_confirm(self, snowflake_backend, test_table):
        """Test deleting data and confirming removal."""
        snowflake_backend.execute(
            "INSERT INTO test_crud_table (name, age, balance) VALUES (%s, %s, %s)",
            ("Charlie", 35, Decimal("300.00"))
        )

        result = snowflake_backend.execute(
            "DELETE FROM test_crud_table WHERE name = %s",
            ("Charlie",)
        )
        assert result.affected_rows == 1

        row = snowflake_backend.fetch_one(
            "SELECT * FROM test_crud_table WHERE name = %s",
            ("Charlie",)
        )
        assert row is None

    def test_fetch_all(self, snowflake_backend, test_table):
        """Test fetching multiple rows."""
        for i in range(3):
            snowflake_backend.execute(
                "INSERT INTO test_crud_table (name, age, balance) VALUES (%s, %s, %s)",
                (f"User{i}", 20 + i, Decimal(f"{100 + i * 50}"))
            )

        rows = snowflake_backend.fetch_all(
            "SELECT name FROM test_crud_table ORDER BY name"
        )
        assert len(rows) == 3
        assert rows[0]["name"] == "User0"
        assert rows[1]["name"] == "User1"
        assert rows[2]["name"] == "User2"

    def test_transaction_via_context_manager(self, snowflake_backend, test_table):
        """Test transaction using context manager."""
        with snowflake_backend.transaction() as tx:
            snowflake_backend.execute(
                "INSERT INTO test_crud_table (name, age, balance) VALUES (%s, %s, %s)",
                ("TransactionTest", 40, Decimal("500.00"))
            )

        row = snowflake_backend.fetch_one(
            "SELECT * FROM test_crud_table WHERE name = %s",
            ("TransactionTest",)
        )
        assert row is not None
        assert row["balance"] == Decimal("500.00")

    def test_fetch_none(self, snowflake_backend, test_table):
        """Test fetching when no results exist."""
        row = snowflake_backend.fetch_one(
            "SELECT * FROM test_crud_table WHERE name = %s",
            ("NonExistent",)
        )
        assert row is None


class TestAsyncMySQLCRUDBackend:
    """Asynchronous CRUD tests for Snowflake backend."""

    @pytest_asyncio.fixture
    async def async_test_table(self, async_snowflake_backend):
        """Create a test table."""
        await async_snowflake_backend.execute("DROP TABLE IF EXISTS test_crud_table")
        await async_snowflake_backend.execute("""
            CREATE TABLE test_crud_table (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255),
                age INT,
                balance DECIMAL(10, 2)
            )
        """)
        yield "test_crud_table"
        await async_snowflake_backend.execute("DROP TABLE IF EXISTS test_crud_table")

    async def test_insert_and_fetch_async(self, async_snowflake_backend, async_test_table):
        """Test inserting data and fetching it back (async)."""
        result = await async_snowflake_backend.execute(
            "INSERT INTO test_crud_table (name, age, balance) VALUES (%s, %s, %s)",
            ("Alice", 25, Decimal("100.50"))
        )
        assert result.affected_rows == 1

        row = await async_snowflake_backend.fetch_one(
            "SELECT * FROM test_crud_table WHERE name = %s",
            ("Alice",)
        )
        assert row is not None
        assert row["name"] == "Alice"
        assert row["age"] == 25

    async def test_update_and_verify_async(self, async_snowflake_backend, async_test_table):
        """Test updating data and verifying the change (async)."""
        await async_snowflake_backend.execute(
            "INSERT INTO test_crud_table (name, age, balance) VALUES (%s, %s, %s)",
            ("Bob", 30, Decimal("200.00"))
        )

        result = await async_snowflake_backend.execute(
            "UPDATE test_crud_table SET age = %s, balance = %s WHERE name = %s",
            (31, Decimal("250.75"), "Bob")
        )
        assert result.affected_rows == 1

        row = await async_snowflake_backend.fetch_one(
            "SELECT age, balance FROM test_crud_table WHERE name = %s",
            ("Bob",)
        )
        assert row["age"] == 31
        assert row["balance"] == Decimal("250.75")

    async def test_delete_and_confirm_async(self, async_snowflake_backend, async_test_table):
        """Test deleting data and confirming removal (async)."""
        await async_snowflake_backend.execute(
            "INSERT INTO test_crud_table (name, age, balance) VALUES (%s, %s, %s)",
            ("Charlie", 35, Decimal("300.00"))
        )

        result = await async_snowflake_backend.execute(
            "DELETE FROM test_crud_table WHERE name = %s",
            ("Charlie",)
        )
        assert result.affected_rows == 1

        row = await async_snowflake_backend.fetch_one(
            "SELECT * FROM test_crud_table WHERE name = %s",
            ("Charlie",)
        )
        assert row is None

    async def test_fetch_all_async(self, async_snowflake_backend, async_test_table):
        """Test fetching multiple rows (async)."""
        for i in range(3):
            await async_snowflake_backend.execute(
                "INSERT INTO test_crud_table (name, age, balance) VALUES (%s, %s, %s)",
                (f"User{i}", 20 + i, Decimal(f"{100 + i * 50}"))
            )

        rows = await async_snowflake_backend.fetch_all(
            "SELECT name FROM test_crud_table ORDER BY name"
        )
        assert len(rows) == 3
        assert rows[0]["name"] == "User0"
        assert rows[1]["name"] == "User1"
        assert rows[2]["name"] == "User2"

    async def test_async_transaction_via_context_manager(self, async_snowflake_backend, async_test_table):
        """Test transaction using context manager (async)."""
        async with async_snowflake_backend.transaction() as tx:
            await async_snowflake_backend.execute(
                "INSERT INTO test_crud_table (name, age, balance) VALUES (%s, %s, %s)",
                ("TransactionTest", 40, Decimal("500.00"))
            )

        row = await async_snowflake_backend.fetch_one(
            "SELECT * FROM test_crud_table WHERE name = %s",
            ("TransactionTest",)
        )
        assert row is not None
        assert row["balance"] == Decimal("500.00")

    async def test_async_fetch_none(self, async_snowflake_backend, async_test_table):
        """Test fetching when no results exist (async)."""
        row = await async_snowflake_backend.fetch_one(
            "SELECT * FROM test_crud_table WHERE name = %s",
            ("NonExistent",)
        )
        assert row is None
