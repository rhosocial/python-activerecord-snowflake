"""Basic fakesnow connection tests (Layer 3).

Validates that SnowflakeBackend can connect to fakesnow and
execute basic SQL operations. AR model integration tests will
be added as SnowflakeBackend insert/update/query support matures.
"""
import pytest


@pytest.mark.fakesnow
class TestFakesnowConnection:
    """Verify SnowflakeBackend + fakesnow basic connectivity."""

    def test_connect_and_disconnect(self, fs_backend):
        assert fs_backend._connected

    def test_execute_select(self, fs_backend):
        result = fs_backend.execute("SELECT 1 AS val", ())
        assert result is not None

    def test_create_table(self, fs_backend):
        fs_backend.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100)
            )
        """, ())

    @pytest.mark.skip(reason="get_default_adapter_suggestions() not implemented yet")
    def test_insert_and_select(self, fs_backend):
        fs_backend.execute("""
            CREATE TABLE test_insert (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100)
            )
        """, ())
        fs_backend.execute("INSERT INTO test_insert (id, name) VALUES (%s, %s)", (1, "hello"))
        result = fs_backend.execute("SELECT * FROM test_insert WHERE id = %s", (1,))
        assert result is not None

    def test_create_sequence(self, fs_backend):
        """Verify fakesnow supports CREATE SEQUENCE for SnowflakePKMixin tests."""
        fs_backend.execute(
            "CREATE SEQUENCE test_seq START = 1000 INCREMENT = 1", ()
        )
        result = fs_backend.execute("SELECT test_seq.NEXTVAL AS next_id", ())
        assert result is not None
