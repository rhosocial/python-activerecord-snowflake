# tests/rhosocial/activerecord_snowflake_test/feature/backend/dml/test_dialect_security_integration.py
"""
Integration tests for Snowflake dialect SQL injection security fixes.

These tests verify that the security fixes work correctly when
SQL is actually executed against a Snowflake database.
"""
import pytest

from rhosocial.activerecord.backend.dialect.protocols import JSONSupport


def requires_json_table():
    """Decorator for tests requiring JSON_TABLE support (MySQL 8.0.4+)."""
    return pytest.mark.requires_protocol((JSONSupport, 'supports_json_table'))


class TestSnowflakeDialectSecurityIntegration:
    """Integration tests for Snowflake dialect security."""

    @pytest.fixture
    def test_table_with_special_chars(self, snowflake_backend):
        """Create a test table with special characters in defaults and comments."""
        snowflake_backend.execute("DROP TABLE IF EXISTS test_security_chars")
        snowflake_backend.execute("""
            CREATE TABLE test_security_chars (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) DEFAULT 'test''s value',
                description VARCHAR(255) COMMENT 'Test with ''quotes'''
            ) ENGINE=InnoDB
        """)
        yield "test_security_chars"
        snowflake_backend.execute("DROP TABLE IF EXISTS test_security_chars")

    def test_default_string_with_single_quote_insert_and_retrieve(self, snowflake_backend, test_table_with_special_chars):
        """Test that single quotes in DEFAULT are properly escaped and retrieved correctly."""
        # Insert a row with special characters
        snowflake_backend.execute(
            f"INSERT INTO {test_table_with_special_chars} (name) VALUES ('O''Brien')"
        )

        # Retrieve and verify - use fetch_one and access by column name
        row = snowflake_backend.fetch_one(
            f"SELECT name FROM {test_table_with_special_chars} WHERE id = 1"
        )
        # Access result by column name
        assert row["name"] == "O'Brien"

    def test_comment_with_single_quote_stored_correctly(self, snowflake_backend, test_table_with_special_chars):
        """Test that COMMENT with single quotes is stored correctly."""
        # Get the column comment
        result = snowflake_backend.fetch_one("""
            SELECT COLUMN_COMMENT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'test_security_chars'
            AND COLUMN_NAME = 'description'
        """)
        assert result is not None
        assert result["COLUMN_COMMENT"] == "Test with 'quotes'"

    @pytest.fixture
    def test_table_for_data_type(self, snowflake_backend):
        """Create a test table for data type security tests."""
        snowflake_backend.execute("DROP TABLE IF EXISTS test_data_type_security")
        yield "test_data_type_security"
        snowflake_backend.execute("DROP TABLE IF EXISTS test_data_type_security")

    def test_valid_data_type_works(self, snowflake_backend, test_table_for_data_type):
        """Test that valid data types work correctly."""
        # This should succeed with valid data type
        snowflake_backend.execute(f"""
            CREATE TABLE {test_table_for_data_type} (
                id INT PRIMARY KEY,
                data VARCHAR(255)
            )
        """)

        # Verify table was created
        result = snowflake_backend.fetch_all(f"DESCRIBE {test_table_for_data_type}")
        rows = list(result)
        assert len(rows) == 2

    def test_malicious_data_type_rejected_at_dialect_level(self, snowflake_backend):
        """Test that malicious data type is rejected at dialect level before DB execution."""
        from rhosocial.activerecord.backend.expression.statements import ColumnDefinition

        with pytest.raises(TypeError, match="data_type must be a DataType instance"):
            ColumnDefinition(
                name="test_col",
                data_type="VARCHAR(255); DROP TABLE users--",
            )


@requires_json_table()
class TestSnowflakeJSONTableSecurityIntegration:
    """Integration tests for JSON_TABLE security."""

    @pytest.fixture
    def json_table_name(self, snowflake_backend):
        """Create a test table with JSON data."""
        snowflake_backend.execute("DROP TABLE IF EXISTS test_json_security")
        snowflake_backend.execute("DROP TABLE IF EXISTS test_json_data")
        snowflake_backend.execute("""
            CREATE TABLE test_json_data (
                id INT PRIMARY KEY,
                data JSON
            )
        """)
        snowflake_backend.execute("""
            INSERT INTO test_json_data (id, data) VALUES
            (1, '{"name": "test''s value", "price": 100}')
        """)
        yield "test_json_data"
        snowflake_backend.execute("DROP TABLE IF EXISTS test_json_security")
        snowflake_backend.execute("DROP TABLE IF EXISTS test_json_data")

    def test_json_table_with_special_chars_in_path(self, snowflake_backend, json_table_name):
        """Test JSON_TABLE with special characters in path."""
        # Snowflake does not support JSON_TABLE function
        pytest.skip("Snowflake does not support JSON_TABLE function")