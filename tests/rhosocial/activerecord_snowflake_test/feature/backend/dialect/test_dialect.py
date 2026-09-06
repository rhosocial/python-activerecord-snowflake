# tests/rhosocial/activerecord_snowflake_test/feature/backend/dialect/test_dialect.py
"""Tests for SnowflakeDialect formatting and capability detection."""
import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression.types import (
    SnowflakeVarcharType,
    SnowflakeNumberType,
    SnowflakeBooleanType,
    SnowflakeTimestampLtzType,
    SnowflakeTimestampNtzType,
    SnowflakeTimestampTzType,
    SnowflakeDateType,
    SnowflakeTimeType,
    SnowflakeBinaryType,
    SnowflakeVariantType,
    SnowflakeArrayType,
    SnowflakeObjectType,
    SnowflakeGeographyType,
    SnowflakeGeometryType,
)


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


class TestSnowflakeQualifyClauseAssembly:
    """Test QUALIFY clause rendering within QueryExpression."""

    def test_qualify_before_order_by(self, dialect):
        """QUALIFY must be emitted once and placed before ORDER BY."""
        from rhosocial.activerecord.backend.expression import (
            Column,
            FunctionCall,
            Literal,
            OrderByClause,
            QualifyClause,
            QueryExpression,
            TableExpression,
        )

        query = QueryExpression(
            dialect,
            select=[Column(dialect, "id"), Column(dialect, "name")],
            from_=TableExpression(dialect, "users"),
            qualify=QualifyClause(
                dialect,
                FunctionCall(dialect, "ROW_NUMBER") <= Literal(dialect, 3),
            ),
            order_by=OrderByClause(
                dialect, expressions=[(Column(dialect, "id"), "ASC")]
            ),
        )
        sql, params = query.to_sql()
        assert sql.count("QUALIFY") == 1
        assert sql.index("QUALIFY") < sql.index("ORDER BY")
        assert "QUALIFY ROW_NUMBER() <= %s ORDER BY" in sql
        assert params == (3,)


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

    def test_supports_filter_clause(self, dialect):
        assert dialect.supports_filter_clause() is True

    def test_supports_indexes(self, dialect):
        assert dialect.supports_indexes() is True

    def test_supports_constraints(self, dialect):
        assert dialect.supports_constraints() is True

    def test_supports_sequences(self, dialect):
        assert dialect.supports_sequences() is True

    def test_supports_explicit_inner_join(self, dialect):
        assert dialect.supports_explicit_inner_join() is True

    def test_supports_modify_column(self, dialect):
        assert dialect.supports_modify_column() is True

    def test_returning_clause_version_dependent(self, dialect):
        """RETURNING support depends on Snowflake server version."""
        assert dialect.supports_returning_clause() is True
        assert dialect.supports_returning_insert() is True
        assert dialect.supports_returning_update() is True
        assert dialect.supports_returning_delete() is True

        old_dialect = SnowflakeDialect(version=(7, 31, 0))
        assert old_dialect.supports_returning_clause() is False
        assert old_dialect.supports_returning_insert() is False

        boundary_dialect = SnowflakeDialect(version=(7, 32, 0))
        assert boundary_dialect.supports_returning_clause() is True

    def test_supports_offset_without_limit(self, dialect):
        assert dialect.supports_offset_without_limit() is True

    def test_supports_for_update(self, dialect):
        assert dialect.supports_for_update() is False

    def test_supports_union(self, dialect):
        assert dialect.supports_union() is True

    def test_supports_intersect(self, dialect):
        assert dialect.supports_intersect() is True

    def test_supports_except(self, dialect):
        assert dialect.supports_except() is True

    def test_supports_set_operation_order_by(self, dialect):
        assert dialect.supports_set_operation_order_by() is True

    def test_supports_set_operation_limit_offset(self, dialect):
        assert dialect.supports_set_operation_limit_offset() is True

    def test_supports_set_operation_for_update(self, dialect):
        assert dialect.supports_set_operation_for_update() is False


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


class TestSnowflakeDataTypeFormatting:
    """Test Snowflake-specific DataType subclass formatting."""

    def test_varchar_type(self, dialect):
        t = SnowflakeVarcharType(length=256)
        sql, params = dialect.format_data_type(t)
        assert sql == "VARCHAR(256)"
        assert params == ()

    def test_varchar_type_default(self, dialect):
        t = SnowflakeVarcharType()
        sql, params = dialect.format_data_type(t)
        assert sql == "VARCHAR"
        assert params == ()

    def test_number_type(self, dialect):
        t = SnowflakeNumberType(precision=38, scale=2)
        sql, params = dialect.format_data_type(t)
        assert sql == "NUMBER(38, 2)"

    def test_number_type_precision_only(self, dialect):
        t = SnowflakeNumberType(precision=10)
        sql, params = dialect.format_data_type(t)
        assert sql == "NUMBER(10)"

    def test_number_type_default(self, dialect):
        t = SnowflakeNumberType()
        sql, params = dialect.format_data_type(t)
        assert sql == "NUMBER"

    def test_boolean_type(self, dialect):
        t = SnowflakeBooleanType()
        sql, params = dialect.format_data_type(t)
        assert sql == "BOOLEAN"

    def test_timestamp_ltz(self, dialect):
        t = SnowflakeTimestampLtzType()
        sql, params = dialect.format_data_type(t)
        assert sql == "TIMESTAMP_LTZ"

    def test_timestamp_ltz_with_precision(self, dialect):
        t = SnowflakeTimestampLtzType(precision=3)
        sql, params = dialect.format_data_type(t)
        assert sql == "TIMESTAMP_LTZ(3)"

    def test_timestamp_ntz(self, dialect):
        t = SnowflakeTimestampNtzType()
        sql, params = dialect.format_data_type(t)
        assert sql == "TIMESTAMP_NTZ"

    def test_timestamp_tz(self, dialect):
        t = SnowflakeTimestampTzType()
        sql, params = dialect.format_data_type(t)
        assert sql == "TIMESTAMP_TZ"

    def test_date_type(self, dialect):
        t = SnowflakeDateType()
        sql, params = dialect.format_data_type(t)
        assert sql == "DATE"

    def test_time_type(self, dialect):
        t = SnowflakeTimeType(precision=6)
        sql, params = dialect.format_data_type(t)
        assert sql == "TIME(6)"

    def test_time_type_default(self, dialect):
        t = SnowflakeTimeType()
        sql, params = dialect.format_data_type(t)
        assert sql == "TIME"

    def test_binary_type(self, dialect):
        t = SnowflakeBinaryType()
        sql, params = dialect.format_data_type(t)
        assert sql == "BINARY"

    def test_binary_type_with_length(self, dialect):
        t = SnowflakeBinaryType(length=1024)
        sql, params = dialect.format_data_type(t)
        assert sql == "BINARY(1024)"

    def test_variant_type(self, dialect):
        t = SnowflakeVariantType()
        sql, params = dialect.format_data_type(t)
        assert sql == "VARIANT"

    def test_array_type(self, dialect):
        t = SnowflakeArrayType()
        sql, params = dialect.format_data_type(t)
        assert sql == "ARRAY"

    def test_object_type(self, dialect):
        t = SnowflakeObjectType()
        sql, params = dialect.format_data_type(t)
        assert sql == "OBJECT"

    def test_geography_type(self, dialect):
        t = SnowflakeGeographyType()
        sql, params = dialect.format_data_type(t)
        assert sql == "GEOGRAPHY"

    def test_geometry_type(self, dialect):
        t = SnowflakeGeometryType()
        sql, params = dialect.format_data_type(t)
        assert sql == "GEOMETRY"

    def test_supports_data_types(self, dialect):
        result = dialect.supports_data_types()
        assert len(result) == 14
        names = [name for _, name in result]
        assert "VARCHAR" in names
        assert "NUMBER" in names
        assert "BOOLEAN" in names
        assert "TIMESTAMP_LTZ" in names
        assert "TIMESTAMP_NTZ" in names
        assert "TIMESTAMP_TZ" in names
        assert "VARIANT" in names
        assert "ARRAY" in names
        assert "OBJECT" in names
        assert "GEOGRAPHY" in names
        assert "GEOMETRY" in names
        assert "DATE" in names
        assert "TIME" in names
        assert "BINARY" in names


class TestSnowflakeDialectVersion:
    """Test version-aware behavior."""

    def test_default_version(self):
        d = SnowflakeDialect()
        assert d.version == (8, 0, 0)

    def test_custom_version(self):
        d = SnowflakeDialect(version=(7, 42, 1))
        assert d.version == (7, 42, 1)
