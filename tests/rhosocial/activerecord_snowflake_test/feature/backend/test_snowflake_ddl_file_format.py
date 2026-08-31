"""Tests for Snowflake FILE FORMAT DDL support.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeFileFormatSupport,
)
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeAlterFileFormatExpression,
    SnowflakeCreateFileFormatExpression,
    SnowflakeDropFileFormatExpression,
    SnowflakeFileFormatType,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeFileFormatProtocol:
    """Dialect satisfies isinstance checks for the file format protocol."""

    def test_dialect_is_file_format_support(self, dialect):
        assert isinstance(dialect, SnowflakeFileFormatSupport)

    def test_supports_file_formats(self, dialect):
        assert dialect.supports_file_formats() is True


class TestSnowflakeCreateFileFormat:
    """CREATE [OR REPLACE] FILE FORMAT statement generation."""

    def test_create_file_format_basic(self, dialect):
        expr = SnowflakeCreateFileFormatExpression(
            dialect, "my_csv", type_=SnowflakeFileFormatType.CSV
        )
        sql, params = expr.to_sql()
        assert sql == 'CREATE FILE FORMAT "my_csv" TYPE = CSV'
        assert params == ()

    def test_create_file_format_full_options(self, dialect):
        expr = SnowflakeCreateFileFormatExpression(
            dialect,
            "my_csv",
            type_=SnowflakeFileFormatType.CSV,
            options={
                "FIELD_DELIMITER": ",",
                "SKIP_HEADER": 1,
                "NULL_IF": ("NULL",),
            },
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE FILE FORMAT "my_csv" '
            "TYPE = CSV "
            "FIELD_DELIMITER = ',' "
            "SKIP_HEADER = 1 "
            "NULL_IF = ('NULL')"
        )

    def test_create_file_format_or_replace(self, dialect):
        expr = SnowflakeCreateFileFormatExpression(
            dialect,
            "my_json",
            or_replace=True,
            type_=SnowflakeFileFormatType.JSON,
            options={"STRIP_OUTER_ARRAY": True},
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE OR REPLACE FILE FORMAT "my_json" '
            "TYPE = JSON STRIP_OUTER_ARRAY = TRUE"
        )

    def test_create_file_format_parquet(self, dialect):
        expr = SnowflakeCreateFileFormatExpression(
            dialect, "my_pq", type_="PARQUET"
        )
        sql, _ = expr.to_sql()
        assert sql == 'CREATE FILE FORMAT "my_pq" TYPE = PARQUET'

    def test_create_file_format_all_types_accepted(self, dialect):
        for t in SnowflakeFileFormatType:
            expr = SnowflakeCreateFileFormatExpression(
                dialect, "fmt", type_=t
            )
            sql, _ = expr.to_sql()
            assert f"TYPE = {t.value}" in sql

    def test_create_file_format_string_escaped(self, dialect):
        expr = SnowflakeCreateFileFormatExpression(
            dialect,
            "my_csv",
            type_=SnowflakeFileFormatType.CSV,
            options={"FIELD_DELIMITER": "it's"},
        )
        sql, _ = expr.to_sql()
        assert "FIELD_DELIMITER = 'it''s'" in sql


class TestSnowflakeAlterFileFormat:
    """ALTER FILE FORMAT ... SET statement generation."""

    def test_alter_file_format_set(self, dialect):
        expr = SnowflakeAlterFileFormatExpression(
            dialect, "my_csv", options={"SKIP_HEADER": 2}
        )
        sql, params = expr.to_sql()
        assert sql == 'ALTER FILE FORMAT "my_csv" SET SKIP_HEADER = 2'
        assert params == ()

    def test_alter_file_format_set_comment(self, dialect):
        expr = SnowflakeAlterFileFormatExpression(
            dialect, "my_csv", comment="updated"
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'ALTER FILE FORMAT "my_csv" SET COMMENT = \'updated\''
        )

    def test_alter_file_format_without_property_raises(self, dialect):
        expr = SnowflakeAlterFileFormatExpression(dialect, "my_csv")
        with pytest.raises(ValueError):
            expr.to_sql()


class TestSnowflakeDropFileFormat:
    """DROP FILE FORMAT statement generation."""

    def test_drop_file_format(self, dialect):
        expr = SnowflakeDropFileFormatExpression(dialect, "my_csv")
        sql, params = expr.to_sql()
        assert sql == 'DROP FILE FORMAT "my_csv"'
        assert params == ()

    def test_drop_file_format_if_exists(self, dialect):
        expr = SnowflakeDropFileFormatExpression(
            dialect, "my_csv", if_exists=True
        )
        sql, _ = expr.to_sql()
        assert sql == 'DROP FILE FORMAT IF EXISTS "my_csv"'
