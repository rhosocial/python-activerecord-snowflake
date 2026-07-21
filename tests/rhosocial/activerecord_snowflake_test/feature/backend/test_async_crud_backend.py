# tests/rhosocial/activerecord_snowflake_test/feature/backend/test_async_crud.py
from datetime import datetime
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def setup_test_table(async_snowflake_backend):
    await async_snowflake_backend.execute("DROP TABLE IF EXISTS test_table")
    await async_snowflake_backend.execute("""
        CREATE TABLE test_table (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255),
            age INT,
            created_at DATETIME
        )
    """)
    yield
    await async_snowflake_backend.execute("DROP TABLE IF EXISTS test_table")


@pytest.mark.asyncio
async def test_insert_success(async_snowflake_backend, setup_test_table):
    """Test successful insertion"""
    sql = "INSERT INTO test_table (name, age, created_at) VALUES (%s, %s, %s)"
    params = ("test", 20, datetime.now())
    result = await async_snowflake_backend.execute(sql, params)
    assert result.affected_rows == 1
    assert result.last_insert_id is not None


@pytest.mark.asyncio
async def test_insert_with_invalid_data(async_snowflake_backend, setup_test_table):
    """Test inserting invalid data"""
    with pytest.raises(Exception):  # Specific exception type depends on implementation
        sql = "INSERT INTO test_table (invalid_column) VALUES (%s)"
        params = ("value",)
        await async_snowflake_backend.execute(sql, params)


@pytest.mark.asyncio
async def test_fetch_one(async_snowflake_backend, setup_test_table):
    """Test querying a single record"""
    sql = "INSERT INTO test_table (name, age) VALUES (%s, %s)"
    params = ("test", 20)
    await async_snowflake_backend.execute(sql, params)
    row = await async_snowflake_backend.fetch_one("SELECT * FROM test_table WHERE name = %s", ("test",))
    assert row is not None
    assert row["name"] == "test"
    assert row["age"] == 20


@pytest.mark.asyncio
async def test_fetch_all(async_snowflake_backend, setup_test_table):
    """Test querying multiple records"""
    sql = "INSERT INTO test_table (name, age) VALUES (%s, %s)"
    params1 = ("test1", 20)
    params2 = ("test2", 30)
    await async_snowflake_backend.execute(sql, params1)
    await async_snowflake_backend.execute(sql, params2)
    rows = await async_snowflake_backend.fetch_all("SELECT * FROM test_table ORDER BY age")
    assert len(rows) == 2
    assert rows[0]["age"] == 20
    assert rows[1]["age"] == 30


@pytest.mark.asyncio
async def test_update(async_snowflake_backend, setup_test_table):
    """Test updating a record"""
    sql = "INSERT INTO test_table (name, age) VALUES (%s, %s)"
    params = ("test", 20)
    await async_snowflake_backend.execute(sql, params)

    sql = "UPDATE test_table SET age = %s WHERE name = %s"
    params = (21, "test")
    result = await async_snowflake_backend.execute(sql, params)
    assert result.affected_rows == 1

    row = await async_snowflake_backend.fetch_one("SELECT * FROM test_table WHERE name = %s", ("test",))
    assert row["age"] == 21


@pytest.mark.asyncio
async def test_delete(async_snowflake_backend, setup_test_table):
    """Test deleting a record"""
    sql = "INSERT INTO test_table (name, age) VALUES (%s, %s)"
    params = ("test", 20)
    await async_snowflake_backend.execute(sql, params)

    sql = "DELETE FROM test_table WHERE name = %s"
    params = ("test",)
    result = await async_snowflake_backend.execute(sql, params)
    assert result.affected_rows == 1

    row = await async_snowflake_backend.fetch_one("SELECT * FROM test_table WHERE name = %s", ("test",))
    assert row is None


@pytest.mark.asyncio
async def test_execute_many(async_snowflake_backend, setup_test_table):
    """Test batch insertion"""
    data = [
        ("name1", 20),
        ("name2", 30),
        ("name3", 40)
    ]
    result = await async_snowflake_backend.execute_many(
        "INSERT INTO test_table (name, age) VALUES (%s, %s)",
        data
    )
    assert result.affected_rows == 3
    rows = await async_snowflake_backend.fetch_all("SELECT * FROM test_table ORDER BY age")
    assert len(rows) == 3