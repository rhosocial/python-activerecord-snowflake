"""Tests for SnowflakeDialect formatting and capability detection."""
import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeDialectFormatting:
    """Test SQL formatting methods."""

    def test_format_identifier(self, dialect):
        assert dialect.format_identifier("table_name") == '"table_name"'

    def test_format_identifier_special_chars(self, dialect):
        assert dialect.format_identifier("my-table") == '"my-table"'
        assert dialect.format_identifier("My Table") == '"My Table"'

    def test_get_parameter_placeholder(self, dialect):
        assert dialect.get_parameter_placeholder() == "%s"
        assert dialect.get_parameter_placeholder(0) == "%s"
        assert dialect.get_parameter_placeholder(5) == "%s"


class TestSnowflakeDialectCapabilities:
    """Test supports_* capability detection methods."""

    def test_supports_cte(self, dialect):
        assert dialect.supports_cte() is True

    def test_supports_recursive_cte(self, dialect):
        assert dialect.supports_recursive_cte() is True

    def test_supports_window_functions(self, dialect):
        assert dialect.supports_window_functions() is True

    def test_supports_json_operations(self, dialect):
        assert dialect.supports_json_operations() is True

    def test_supports_merge(self, dialect):
        assert dialect.supports_merge() is True

    def test_supports_qualify_clause(self, dialect):
        assert dialect.supports_qualify_clause() is True

    def test_supports_upsert(self, dialect):
        assert dialect.supports_upsert() is True

    def test_supports_lateral_join(self, dialect):
        assert dialect.supports_lateral_join() is True

    def test_supports_explain(self, dialect):
        assert dialect.supports_explain() is True

    def test_supports_advanced_grouping(self, dialect):
        assert dialect.supports_advanced_grouping() is True

    def test_supports_arrays(self, dialect):
        assert dialect.supports_arrays() is True

    def test_supports_schema(self, dialect):
        assert dialect.supports_schema() is True

    def test_supports_views(self, dialect):
        assert dialect.supports_views() is True

    def test_supports_introspection(self, dialect):
        assert dialect.supports_introspection() is True

    def test_does_not_support_returning(self, dialect):
        assert dialect.supports_returning_clause() is False


class TestSnowflakeSpecificCapabilities:
    """Test Snowflake-specific capability detection."""

    def test_supports_time_travel(self, dialect):
        assert dialect.supports_time_travel() is True

    def test_supports_variant_type(self, dialect):
        assert dialect.supports_variant_type() is True

    def test_supports_array_type(self, dialect):
        assert dialect.supports_array_type() is True

    def test_supports_clone(self, dialect):
        assert dialect.supports_clone() is True

    def test_supports_stages(self, dialect):
        assert dialect.supports_stages() is True


class TestSnowflakeSpecificFormatting:
    """Test Snowflake-specific SQL formatting."""

    def test_format_time_travel_at_timestamp(self, dialect):
        result = dialect.format_time_travel_at_timestamp("2024-01-01 00:00:00")
        assert result == "AT(TIMESTAMP => '2024-01-01 00:00:00')"

    def test_format_time_travel_at_offset(self, dialect):
        result = dialect.format_time_travel_at_offset(3600)
        assert result == "AT(OFFSET => 3600)"

    def test_format_time_travel_before_timestamp(self, dialect):
        result = dialect.format_time_travel_before_timestamp("2024-01-01 00:00:00")
        assert result == "BEFORE(TIMESTAMP => '2024-01-01 00:00:00')"

    def test_format_variant_path_access(self, dialect):
        result = dialect.format_variant_path_access("data", "key.nested")
        assert result == "data:key.nested"

    def test_format_variant_cast(self, dialect):
        result = dialect.format_variant_cast("data", "count", "NUMBER")
        assert result == "data:count::NUMBER"

    def test_format_array_construct(self, dialect):
        result = dialect.format_array_construct("1, 2, 3")
        assert result == "ARRAY_CONSTRUCT(1, 2, 3)"

    def test_format_array_access(self, dialect):
        result = dialect.format_array_access("my_array", "0")
        assert result == "my_array[0]"

    def test_format_clone_table(self, dialect):
        result = dialect.format_clone_table("new_table", "source_table")
        assert result == "CREATE TABLE new_table CLONE source_table"

    def test_format_copy_into_table(self, dialect):
        result = dialect.format_copy_into_table("my_table", "my_stage")
        assert result == "COPY INTO my_table FROM @my_stage"

    def test_format_copy_into_table_with_format(self, dialect):
        result = dialect.format_copy_into_table("my_table", "my_stage", "TYPE = 'CSV'")
        assert result == "COPY INTO my_table FROM @my_stage FILE_FORMAT = (TYPE = 'CSV')"


class TestSnowflakeDialectVersion:
    """Test version-aware behavior."""

    def test_default_version(self):
        d = SnowflakeDialect()
        assert d.version == (8, 0, 0)

    def test_custom_version(self):
        d = SnowflakeDialect(version=(7, 42, 1))
        assert d.version == (7, 42, 1)
