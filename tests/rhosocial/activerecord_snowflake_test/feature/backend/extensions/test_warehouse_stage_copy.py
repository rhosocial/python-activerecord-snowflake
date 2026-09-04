# tests/rhosocial/activerecord_snowflake_test/feature/backend/extensions/test_warehouse_stage_copy.py
"""Tests for Snowflake WAREHOUSE / STAGE / COPY INTO DDL support.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeStageSupport,
    SnowflakeWarehouseSupport,
)
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeAlterWarehouseExpression,
    SnowflakeAlterWarehouseMode,
    SnowflakeAlterStageExpression,
    SnowflakeCopyIntoExpression,
    SnowflakeCopyIntoMode,
    SnowflakeCreateStageExpression,
    SnowflakeCreateWarehouseExpression,
    SnowflakeDropStageExpression,
    SnowflakeDropWarehouseExpression,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeProtocolConformance:
    """Dialect satisfies isinstance checks for the new protocols."""

    def test_dialect_is_warehouse_support(self, dialect):
        assert isinstance(dialect, SnowflakeWarehouseSupport)

    def test_dialect_is_stage_support(self, dialect):
        assert isinstance(dialect, SnowflakeStageSupport)

    def test_supports_warehouse(self, dialect):
        assert dialect.supports_warehouse() is True

    def test_supports_stages(self, dialect):
        assert dialect.supports_stages() is True


class TestSnowflakeCreateWarehouse:
    """CREATE WAREHOUSE statement generation."""

    def test_create_warehouse_basic(self, dialect):
        expr = SnowflakeCreateWarehouseExpression(dialect, "my_wh")
        sql, params = expr.to_sql()
        assert sql == 'CREATE WAREHOUSE "my_wh"'
        assert params == ()

    def test_create_warehouse_full_options(self, dialect):
        expr = SnowflakeCreateWarehouseExpression(
            dialect,
            "my_wh",
            or_replace=True,
            warehouse_size="X-SMALL",
            max_cluster_count=2,
            min_cluster_count=1,
            scaling_policy="STANDARD",
            auto_suspend=300,
            auto_resume=True,
            initially_suspended=True,
            comment="my comment",
        )
        sql, params = expr.to_sql()
        assert sql == (
            'CREATE OR REPLACE WAREHOUSE "my_wh" WITH '
            "WAREHOUSE_SIZE = 'X-SMALL' "
            "MAX_CLUSTER_COUNT = 2 "
            "MIN_CLUSTER_COUNT = 1 "
            "SCALING_POLICY = 'STANDARD' "
            "AUTO_SUSPEND = 300 "
            "AUTO_RESUME = TRUE "
            "INITIALLY_SUSPENDED = TRUE "
            "COMMENT = 'my comment'"
        )
        assert params == ()

    def test_create_warehouse_string_escaped(self, dialect):
        expr = SnowflakeCreateWarehouseExpression(
            dialect, "my_wh", comment="it's quoted"
        )
        sql, _ = expr.to_sql()
        assert "COMMENT = 'it''s quoted'" in sql


class TestSnowflakeAlterWarehouse:
    """ALTER WAREHOUSE SUSPEND / RESUME / SET / RENAME generation."""

    def test_alter_warehouse_suspend(self, dialect):
        expr = SnowflakeAlterWarehouseExpression(
            dialect, "my_wh", mode=SnowflakeAlterWarehouseMode.SUSPEND
        )
        sql, params = expr.to_sql()
        assert sql == 'ALTER WAREHOUSE "my_wh" SUSPEND'
        assert params == ()

    def test_alter_warehouse_resume(self, dialect):
        expr = SnowflakeAlterWarehouseExpression(
            dialect, "my_wh", mode=SnowflakeAlterWarehouseMode.RESUME
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER WAREHOUSE "my_wh" RESUME'

    def test_alter_warehouse_set(self, dialect):
        expr = SnowflakeAlterWarehouseExpression(
            dialect,
            "my_wh",
            mode=SnowflakeAlterWarehouseMode.SET,
            warehouse_size="MEDIUM",
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER WAREHOUSE "my_wh" SET WAREHOUSE_SIZE = \'MEDIUM\''

    def test_alter_warehouse_set_multiple(self, dialect):
        expr = SnowflakeAlterWarehouseExpression(
            dialect,
            "my_wh",
            mode=SnowflakeAlterWarehouseMode.SET,
            max_cluster_count=3,
            auto_suspend=False,
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER WAREHOUSE "my_wh" SET MAX_CLUSTER_COUNT = 3 AUTO_SUSPEND = FALSE'

    def test_alter_warehouse_rename(self, dialect):
        expr = SnowflakeAlterWarehouseExpression(
            dialect,
            "my_wh",
            mode=SnowflakeAlterWarehouseMode.RENAME,
            new_name="new_wh",
        )
        sql, _ = expr.to_sql()
        assert sql == 'ALTER WAREHOUSE "my_wh" RENAME TO "new_wh"'

    def test_alter_warehouse_set_without_property_raises(self, dialect):
        expr = SnowflakeAlterWarehouseExpression(
            dialect, "my_wh", mode=SnowflakeAlterWarehouseMode.SET
        )
        with pytest.raises(ValueError):
            expr.to_sql()


class TestSnowflakeDropWarehouse:
    """DROP WAREHOUSE statement generation."""

    def test_drop_warehouse(self, dialect):
        expr = SnowflakeDropWarehouseExpression(dialect, "my_wh")
        sql, params = expr.to_sql()
        assert sql == 'DROP WAREHOUSE "my_wh"'
        assert params == ()

    def test_drop_warehouse_if_exists(self, dialect):
        expr = SnowflakeDropWarehouseExpression(dialect, "my_wh", if_exists=True)
        sql, _ = expr.to_sql()
        assert sql == 'DROP WAREHOUSE IF EXISTS "my_wh"'


class TestSnowflakeCreateStage:
    """CREATE STAGE statement generation."""

    def test_create_stage_basic(self, dialect):
        expr = SnowflakeCreateStageExpression(dialect, "my_stage")
        sql, params = expr.to_sql()
        assert sql == 'CREATE STAGE "my_stage"'
        assert params == ()

    def test_create_stage_or_replace_temporary(self, dialect):
        expr = SnowflakeCreateStageExpression(
            dialect, "my_stage", or_replace=True, temporary=True
        )
        sql, _ = expr.to_sql()
        assert sql == 'CREATE OR REPLACE TEMPORARY STAGE "my_stage"'

    def test_create_stage_full_options(self, dialect):
        expr = SnowflakeCreateStageExpression(
            dialect,
            "my_stage",
            url="s3://bucket/path",
            storage_integration="si",
            file_format="my_fmt",
            encryption={"TYPE": "SSE_S3"},
            directory=True,
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'CREATE STAGE "my_stage" '
            "URL = 's3://bucket/path' "
            'STORAGE_INTEGRATION = "si" '
            'FILE_FORMAT = "my_fmt" '
            "ENCRYPTION = (TYPE = 'SSE_S3') "
            "DIRECTORY = (ENABLE = TRUE)"
        )

    def test_create_stage_encryption_string_fragment(self, dialect):
        expr = SnowflakeCreateStageExpression(
            dialect, "my_stage", encryption="TYPE = 'SSE_S3'"
        )
        sql, _ = expr.to_sql()
        assert "ENCRYPTION = (TYPE = 'SSE_S3')" in sql


class TestSnowflakeAlterDropStage:
    """ALTER / DROP STAGE statement generation."""

    def test_alter_stage_set_file_format(self, dialect):
        expr = SnowflakeAlterStageExpression(dialect, "my_stage", file_format="csv")
        sql, params = expr.to_sql()
        assert sql == 'ALTER STAGE "my_stage" SET FILE_FORMAT = "csv"'
        assert params == ()

    def test_alter_stage_set_url(self, dialect):
        expr = SnowflakeAlterStageExpression(
            dialect, "my_stage", url="azure://container/path"
        )
        sql, _ = expr.to_sql()
        assert sql == (
            'ALTER STAGE "my_stage" SET URL = \'azure://container/path\''
        )

    def test_alter_stage_without_property_raises(self, dialect):
        expr = SnowflakeAlterStageExpression(dialect, "my_stage")
        with pytest.raises(ValueError):
            expr.to_sql()

    def test_drop_stage(self, dialect):
        expr = SnowflakeDropStageExpression(dialect, "my_stage")
        sql, params = expr.to_sql()
        assert sql == 'DROP STAGE "my_stage"'
        assert params == ()

    def test_drop_stage_if_exists(self, dialect):
        expr = SnowflakeDropStageExpression(dialect, "my_stage", if_exists=True)
        sql, _ = expr.to_sql()
        assert sql == 'DROP STAGE IF EXISTS "my_stage"'


class TestSnowflakeStageListRemove:
    """LIST / REMOVE stage file operations."""

    def test_list_stage(self, dialect):
        assert dialect.format_list_stage("my_stage") == "LIST @my_stage"

    def test_remove_stage(self, dialect):
        assert (
            dialect.format_remove_stage("my_stage", "file.csv")
            == "REMOVE @my_stage/file.csv"
        )


class TestSnowflakeCopyIntoLoad:
    """COPY INTO <table> FROM @<stage> (load direction)."""

    def test_copy_into_load_basic(self, dialect):
        expr = SnowflakeCopyIntoExpression(
            dialect,
            mode=SnowflakeCopyIntoMode.LOAD,
            table="t",
            stage="my_stage",
        )
        sql, params = expr.to_sql()
        assert sql == "COPY INTO t FROM @my_stage"
        assert params == ()

    def test_copy_into_load_full_options(self, dialect):
        expr = SnowflakeCopyIntoExpression(
            dialect,
            mode=SnowflakeCopyIntoMode.LOAD,
            table="t",
            stage="my_stage",
            files=["f1.csv", "f2.csv"],
            pattern=r".*\.csv",
            file_format={"FORMAT_NAME": "my_fmt"},
            on_error="SKIP_FILE",
            force=True,
            purge=True,
            validation_mode="RETURN_ERRORS",
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "COPY INTO t FROM @my_stage "
            "FILES = ('f1.csv', 'f2.csv') "
            r"PATTERN = '.*\.csv' "
            "FILE_FORMAT = (FORMAT_NAME = my_fmt) "
            "ON_ERROR = 'SKIP_FILE' "
            "FORCE = TRUE "
            "PURGE = TRUE "
            "VALIDATION_MODE = 'RETURN_ERRORS'"
        )

    def test_copy_into_load_file_format_string_fragment(self, dialect):
        expr = SnowflakeCopyIntoExpression(
            dialect,
            mode=SnowflakeCopyIntoMode.LOAD,
            table="t",
            stage="my_stage",
            file_format="TYPE = 'CSV'",
        )
        sql, _ = expr.to_sql()
        assert sql == "COPY INTO t FROM @my_stage FILE_FORMAT = (TYPE = 'CSV')"


class TestSnowflakeCopyIntoUnload:
    """COPY INTO @<stage> FROM <table> (unload direction)."""

    def test_copy_into_unload_basic(self, dialect):
        expr = SnowflakeCopyIntoExpression(
            dialect,
            mode=SnowflakeCopyIntoMode.UNLOAD,
            table="t",
            stage="out_stage",
        )
        sql, params = expr.to_sql()
        assert sql == "COPY INTO @out_stage FROM t"
        assert params == ()

    def test_copy_into_unload_full_options(self, dialect):
        expr = SnowflakeCopyIntoExpression(
            dialect,
            mode=SnowflakeCopyIntoMode.UNLOAD,
            table="t",
            stage="out_stage",
            partition_by=["c1"],
            file_format={"TYPE": "PARQUET"},
            header=True,
            overwrite=True,
            single=True,
        )
        sql, _ = expr.to_sql()
        assert sql == (
            "COPY INTO @out_stage FROM t "
            "PARTITION BY (c1) "
            "FILE_FORMAT = (TYPE = PARQUET) "
            "HEADER = TRUE "
            "OVERWRITE = TRUE "
            "SINGLE = TRUE"
        )


class TestSnowflakeCopyIntoBackwardCompat:
    """The legacy format_copy_into_table signature is preserved."""

    def test_format_copy_into_table(self, dialect):
        assert (
            dialect.format_copy_into_table("my_table", "my_stage")
            == "COPY INTO my_table FROM @my_stage"
        )

    def test_format_copy_into_table_with_format(self, dialect):
        assert (
            dialect.format_copy_into_table(
                "my_table", "my_stage", "TYPE = 'CSV'"
            )
            == "COPY INTO my_table FROM @my_stage FILE_FORMAT = (TYPE = 'CSV')"
        )
