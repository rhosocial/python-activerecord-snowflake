"""Basic fakesnow connection tests (Layer 3).

Validates that SnowflakeBackend can connect to fakesnow and
execute basic SQL operations including CRUD.
"""
import pytest

from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


@pytest.mark.fakesnow
class TestFakesnowConnection:
    """Verify SnowflakeBackend + fakesnow basic connectivity."""

    def test_connect_and_disconnect(self, fs_backend):
        assert fs_backend._connected

    def test_execute_select(self, fs_backend):
        result = fs_backend.execute(
            "SELECT 1 AS val", (),
            options=ExecutionOptions(stmt_type=StatementType.DQL),
        )
        assert result is not None
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0].get("VAL") == 1 or result.data[0].get("val") == 1

    def test_create_table(self, fs_backend):
        fs_backend.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100)
            )
        """, ())

    def test_insert_and_select(self, fs_backend):
        fs_backend.execute("""
            CREATE TABLE test_insert (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100)
            )
        """, ())
        fs_backend.execute(
            "INSERT INTO test_insert (id, name) VALUES (%s, %s)",
            (1, "hello"),
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )
        result = fs_backend.execute(
            "SELECT * FROM test_insert WHERE id = %s", (1,),
            options=ExecutionOptions(stmt_type=StatementType.DQL),
        )
        assert result is not None
        assert result.data is not None
        assert len(result.data) == 1
        name_val = result.data[0].get("NAME") or result.data[0].get("name")
        assert name_val == "hello"

    def test_update(self, fs_backend):
        fs_backend.execute("""
            CREATE TABLE test_update (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100)
            )
        """, ())
        fs_backend.execute(
            "INSERT INTO test_update (id, name) VALUES (%s, %s)",
            (1, "before"),
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )
        fs_backend.execute(
            "UPDATE test_update SET name = %s WHERE id = %s",
            ("after", 1),
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )
        result = fs_backend.execute(
            "SELECT name FROM test_update WHERE id = %s", (1,),
            options=ExecutionOptions(stmt_type=StatementType.DQL),
        )
        assert result.data is not None
        assert len(result.data) == 1
        name_val = result.data[0].get("NAME") or result.data[0].get("name")
        assert name_val == "after"

    def test_delete(self, fs_backend):
        fs_backend.execute("""
            CREATE TABLE test_delete (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100)
            )
        """, ())
        fs_backend.execute(
            "INSERT INTO test_delete (id, name) VALUES (%s, %s)",
            (1, "deleteme"),
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )
        fs_backend.execute(
            "DELETE FROM test_delete WHERE id = %s", (1,),
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )
        result = fs_backend.execute(
            "SELECT * FROM test_delete", (),
            options=ExecutionOptions(stmt_type=StatementType.DQL),
        )
        assert result.data is not None
        assert len(result.data) == 0

    def test_parameterized_query(self, fs_backend):
        fs_backend.execute("""
            CREATE TABLE test_param (
                id INTEGER PRIMARY KEY,
                value INTEGER
            )
        """, ())
        fs_backend.execute(
            "INSERT INTO test_param (id, value) VALUES (%s, %s)",
            (1, 10),
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )
        fs_backend.execute(
            "INSERT INTO test_param (id, value) VALUES (%s, %s)",
            (2, 20),
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )
        result = fs_backend.execute(
            "SELECT * FROM test_param WHERE value > %s", (15,),
            options=ExecutionOptions(stmt_type=StatementType.DQL),
        )
        assert result.data is not None
        assert len(result.data) == 1

    def test_transaction_commit(self, fs_backend):
        fs_backend.execute("""
            CREATE TABLE test_txn_commit (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100)
            )
        """, ())
        fs_backend.execute("BEGIN", ())
        fs_backend.execute(
            "INSERT INTO test_txn_commit (id, name) VALUES (%s, %s)",
            (1, "txn_row"),
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )
        fs_backend.execute("COMMIT", ())
        result = fs_backend.execute(
            "SELECT * FROM test_txn_commit", (),
            options=ExecutionOptions(stmt_type=StatementType.DQL),
        )
        assert result.data is not None
        assert len(result.data) == 1

    def test_transaction_rollback(self, fs_backend):
        fs_backend.execute("""
            CREATE TABLE test_txn_rollback (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100)
            )
        """, ())
        fs_backend.execute(
            "INSERT INTO test_txn_rollback (id, name) VALUES (%s, %s)",
            (1, "existing"),
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )
        fs_backend.execute("BEGIN", ())
        fs_backend.execute(
            "INSERT INTO test_txn_rollback (id, name) VALUES (%s, %s)",
            (2, "should_disappear"),
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )
        fs_backend.execute("ROLLBACK", ())
        result = fs_backend.execute(
            "SELECT * FROM test_txn_rollback", (),
            options=ExecutionOptions(stmt_type=StatementType.DQL),
        )
        assert result.data is not None
        assert len(result.data) == 1

    def test_create_sequence(self, fs_backend):
        """Verify fakesnow supports CREATE SEQUENCE for SnowflakePKMixin tests."""
        fs_backend.execute(
            "CREATE SEQUENCE test_seq START = 1000 INCREMENT = 1", ()
        )
        result = fs_backend.execute(
            "SELECT test_seq.NEXTVAL AS next_id", (),
            options=ExecutionOptions(stmt_type=StatementType.DQL),
        )
        assert result is not None
        assert result.data is not None
