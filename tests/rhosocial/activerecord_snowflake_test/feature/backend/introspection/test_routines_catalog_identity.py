# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_routines_catalog_identity.py
"""Routines, sequences, catalog objects and the identity audit.

Every test is offline. Rows are fabricated from the documented column names
and value domains; no Snowflake account is contacted, so a passing test pins
the statement and the parser, never the account's answer.

Documentation the expectations were written from:

* https://docs.snowflake.com/en/sql-reference/info-schema/functions
* https://docs.snowflake.com/en/sql-reference/info-schema/procedures
* https://docs.snowflake.com/en/sql-reference/info-schema/sequences
* https://docs.snowflake.com/en/sql-reference/info-schema/stages
* https://docs.snowflake.com/en/sql-reference/info-schema/file_formats
* https://docs.snowflake.com/en/sql-reference/info-schema/pipes
* https://docs.snowflake.com/en/sql-reference/sql/show-tasks
* https://docs.snowflake.com/en/sql-reference/sql/show-streams
* https://docs.snowflake.com/en/sql-reference/info-schema/columns
"""

import inspect
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression.introspection import (
    SnowflakeFileFormatListQueryStatement,
    SnowflakeFunctionListQueryStatement,
    SnowflakePipeListQueryStatement,
    SnowflakeProcedureListQueryStatement,
    SnowflakeSequenceListQueryStatement,
    SnowflakeStageListQueryStatement,
    SnowflakeStreamListQueryStatement,
    SnowflakeTaskListQueryStatement,
)
from rhosocial.activerecord.backend.impl.snowflake.introspection import (
    AsyncSnowflakeIntrospector,
    SnowflakeCatalogObjectInfo,
    SnowflakeIntrospector,
    SnowflakeIntrospectorMixin,
    SnowflakeRoutineInfo,
)
from rhosocial.activerecord.backend.introspection.executor import IntrospectorExecutor
from rhosocial.activerecord.backend.introspection.types import SequenceInfo

FUNCTIONS_SQL = (
    "SELECT FUNCTION_CATALOG, FUNCTION_SCHEMA, FUNCTION_NAME, FUNCTION_OWNER, "
    "ARGUMENT_SIGNATURE, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
    "CHARACTER_OCTET_LENGTH, NUMERIC_PRECISION, NUMERIC_PRECISION_RADIX, "
    "NUMERIC_SCALE, FUNCTION_LANGUAGE, FUNCTION_DEFINITION, "
    "VOLATILITY, IS_NULL_CALL, IS_SECURE, IS_MEMOIZABLE, IS_EXTERNAL, "
    "IS_DATA_METRIC, IS_AGGREGATE, RUNTIME_VERSION, HANDLER, PACKAGES, "
    "INSTALLED_PACKAGES, ARTIFACT_REPOSITORY, EXTERNAL_ACCESS_INTEGRATIONS, "
    "SECRETS, CREATED, LAST_ALTERED, COMMENT, OWNER_ROLE_TYPE "
    "FROM INFORMATION_SCHEMA.FUNCTIONS WHERE FUNCTION_SCHEMA = %s "
    "ORDER BY FUNCTION_NAME, ARGUMENT_SIGNATURE"
)

PROCEDURES_SQL = (
    "SELECT PROCEDURE_CATALOG, PROCEDURE_SCHEMA, PROCEDURE_NAME, PROCEDURE_OWNER, "
    "ARGUMENT_SIGNATURE, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
    "CHARACTER_OCTET_LENGTH, NUMERIC_PRECISION, NUMERIC_PRECISION_RADIX, "
    "NUMERIC_SCALE, PROCEDURE_LANGUAGE, PROCEDURE_DEFINITION, "
    "RUNTIME_VERSION, PACKAGES, INSTALLED_PACKAGES, ARTIFACT_REPOSITORY, "
    "EXTERNAL_ACCESS_INTEGRATIONS, SECRETS, CREATED, LAST_ALTERED, COMMENT, "
    "OWNER_ROLE_TYPE FROM INFORMATION_SCHEMA.PROCEDURES "
    "WHERE PROCEDURE_SCHEMA = %s ORDER BY PROCEDURE_NAME, ARGUMENT_SIGNATURE"
)

SEQUENCES_SQL = (
    "SELECT SEQUENCE_CATALOG, SEQUENCE_SCHEMA, SEQUENCE_NAME, SEQUENCE_OWNER, "
    "DATA_TYPE, NUMERIC_PRECISION, NUMERIC_PRECISION_RADIX, NUMERIC_SCALE, "
    "START_VALUE, MINIMUM_VALUE, MAXIMUM_VALUE, NEXT_VALUE, INCREMENT, "
    "CYCLE_OPTION, CREATED, LAST_ALTERED, ORDERED, COMMENT "
    "FROM INFORMATION_SCHEMA.SEQUENCES WHERE SEQUENCE_SCHEMA = %s "
    "ORDER BY SEQUENCE_NAME"
)

STAGES_SQL = (
    "SELECT STAGE_CATALOG, STAGE_SCHEMA, STAGE_NAME, STAGE_URL, STAGE_REGION, "
    "STAGE_TYPE, STAGE_OWNER, COMMENT, CREATED, LAST_ALTERED "
    "FROM INFORMATION_SCHEMA.STAGES WHERE STAGE_SCHEMA = %s "
    "ORDER BY STAGE_NAME"
)

FILE_FORMATS_SQL = (
    "SELECT FILE_FORMAT_CATALOG, FILE_FORMAT_SCHEMA, FILE_FORMAT_NAME, "
    "FILE_FORMAT_OWNER, FILE_FORMAT_TYPE, RECORD_DELIMITER, FIELD_DELIMITER, "
    "SKIP_HEADER, DATE_FORMAT, TIME_FORMAT, TIMESTAMP_FORMAT, BINARY_FORMAT, "
    "ESCAPE, ESCAPE_UNENCLOSED_FIELD, TRIM_SPACE, "
    "FIELD_OPTIONALLY_ENCLOSED_BY, NULL_IF, COMPRESSION, "
    "ERROR_ON_COLUMN_COUNT_MISMATCH, CREATED, LAST_ALTERED, COMMENT "
    "FROM INFORMATION_SCHEMA.FILE_FORMATS WHERE FILE_FORMAT_SCHEMA = %s "
    "ORDER BY FILE_FORMAT_NAME"
)

PIPES_SQL = (
    "SELECT PIPE_CATALOG, PIPE_SCHEMA, PIPE_NAME, PIPE_OWNER, DEFINITION, "
    "IS_AUTOINGEST_ENABLED, NOTIFICATION_CHANNEL_NAME, CREATED, LAST_ALTERED, "
    "COMMENT, PATTERN FROM INFORMATION_SCHEMA.PIPES "
    "WHERE PIPE_SCHEMA = %s ORDER BY PIPE_NAME"
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 32, 0))


@pytest.fixture
def mock_backend(dialect):
    backend = MagicMock()
    backend._version = (8, 32, 0)
    backend.config = MagicMock()
    backend.config.schema = "PUBLIC"
    backend.config.database = "MY_DB"
    backend.dialect = dialect
    return backend


@pytest.fixture
def sync_executor():
    return MagicMock(spec=IntrospectorExecutor)


@pytest.fixture
def sync_introspector(mock_backend, sync_executor):
    return SnowflakeIntrospector(mock_backend, sync_executor)


@pytest.fixture
def async_executor():
    return AsyncMock()


@pytest.fixture
def async_introspector(mock_backend, async_executor):
    return AsyncSnowflakeIntrospector(mock_backend, async_executor)


@pytest.fixture
def parser():
    return SnowflakeIntrospectorMixin.__new__(SnowflakeIntrospectorMixin)


def function_row(**overrides):
    row = {
        "FUNCTION_CATALOG": "MY_DB",
        "FUNCTION_SCHEMA": "PUBLIC",
        "FUNCTION_NAME": "ADD_ONE",
        "FUNCTION_OWNER": "SYSADMIN",
        "ARGUMENT_SIGNATURE": "(NUMBER)",
        "DATA_TYPE": "NUMBER",
        "FUNCTION_LANGUAGE": "SQL",
        "FUNCTION_DEFINITION": "SELECT N + 1",
        "VOLATILITY": "IMMUTABLE",
        "IS_NULL_CALL": "NO",
        "IS_SECURE": "NO",
        "IS_MEMOIZABLE": "NO",
        "IS_EXTERNAL": "NO",
        "IS_DATA_METRIC": "NO",
        "IS_AGGREGATE": "NO",
        "RUNTIME_VERSION": None,
        "HANDLER": None,
        "PACKAGES": None,
        "INSTALLED_PACKAGES": None,
        "ARTIFACT_REPOSITORY": None,
        "EXTERNAL_ACCESS_INTEGRATIONS": None,
        "SECRETS": None,
        "CREATED": datetime(2026, 1, 1),
        "LAST_ALTERED": datetime(2026, 1, 2),
        "COMMENT": "adds one",
        "OWNER_ROLE_TYPE": "ROLE",
    }
    row.update(overrides)
    return row


def procedure_row(**overrides):
    row = {
        "PROCEDURE_CATALOG": "MY_DB",
        "PROCEDURE_SCHEMA": "PUBLIC",
        "PROCEDURE_NAME": "LOAD_ORDERS",
        "PROCEDURE_OWNER": "SYSADMIN",
        "ARGUMENT_SIGNATURE": "(VARCHAR)",
        "DATA_TYPE": "VARCHAR",
        "PROCEDURE_LANGUAGE": "PYTHON",
        "PROCEDURE_DEFINITION": "def main(session, source): ...",
        "RUNTIME_VERSION": "3.11",
        "PACKAGES": "snowflake-snowpark-python",
        "INSTALLED_PACKAGES": "snowflake-snowpark-python,pandas",
        "ARTIFACT_REPOSITORY": None,
        "EXTERNAL_ACCESS_INTEGRATIONS": None,
        "SECRETS": None,
        "CREATED": datetime(2026, 1, 1),
        "LAST_ALTERED": datetime(2026, 1, 2),
        "COMMENT": "loads orders",
        "OWNER_ROLE_TYPE": "ROLE",
    }
    row.update(overrides)
    return row


def sequence_row(**overrides):
    row = {
        "SEQUENCE_CATALOG": "MY_DB",
        "SEQUENCE_SCHEMA": "PUBLIC",
        "SEQUENCE_NAME": "ORDERS_ID_SEQ",
        "SEQUENCE_OWNER": "SYSADMIN",
        "DATA_TYPE": "NUMBER",
        "NUMERIC_PRECISION": 38,
        "NUMERIC_PRECISION_RADIX": 10,
        "NUMERIC_SCALE": 0,
        "START_VALUE": "1",
        "MINIMUM_VALUE": None,
        "MAXIMUM_VALUE": None,
        "NEXT_VALUE": "4",
        "INCREMENT": "1",
        "CYCLE_OPTION": None,
        "CREATED": datetime(2026, 1, 1),
        "LAST_ALTERED": datetime(2026, 1, 2),
        "ORDERED": "YES",
        "COMMENT": "order ids",
    }
    row.update(overrides)
    return row


def stage_row(**overrides):
    row = {
        "STAGE_CATALOG": "MY_DB",
        "STAGE_SCHEMA": "PUBLIC",
        "STAGE_NAME": "ORDERS_STAGE",
        "STAGE_URL": "s3://bucket/path/",
        "STAGE_REGION": "us-east-1",
        "STAGE_TYPE": "External Named",
        "STAGE_OWNER": "SYSADMIN",
        "COMMENT": "order files",
        "CREATED": datetime(2026, 1, 1),
        "LAST_ALTERED": datetime(2026, 1, 2),
    }
    row.update(overrides)
    return row


def file_format_row(**overrides):
    row = {
        "FILE_FORMAT_CATALOG": "MY_DB",
        "FILE_FORMAT_SCHEMA": "PUBLIC",
        "FILE_FORMAT_NAME": "ORDERS_CSV",
        "FILE_FORMAT_OWNER": "SYSADMIN",
        "FILE_FORMAT_TYPE": "CSV",
        "RECORD_DELIMITER": "\\n",
        "FIELD_DELIMITER": ",",
        "SKIP_HEADER": 1,
        "DATE_FORMAT": "YYYY-MM-DD",
        "TIME_FORMAT": None,
        "TIMESTAMP_FORMAT": None,
        "BINARY_FORMAT": None,
        "ESCAPE": None,
        "ESCAPE_UNENCLOSED_FIELD": None,
        "TRIM_SPACE": "TRUE",
        "FIELD_OPTIONALLY_ENCLOSED_BY": '"',
        "NULL_IF": "NULL",
        "COMPRESSION": "AUTO",
        "ERROR_ON_COLUMN_COUNT_MISMATCH": "YES",
        "CREATED": datetime(2026, 1, 1),
        "LAST_ALTERED": datetime(2026, 1, 2),
        "COMMENT": "orders csv",
    }
    row.update(overrides)
    return row


def pipe_row(**overrides):
    row = {
        "PIPE_CATALOG": "MY_DB",
        "PIPE_SCHEMA": "PUBLIC",
        "PIPE_NAME": "ORDERS_PIPE",
        "PIPE_OWNER": "SYSADMIN",
        "DEFINITION": "COPY INTO ORDERS FROM @ORDERS_STAGE",
        "IS_AUTOINGEST_ENABLED": "YES",
        "NOTIFICATION_CHANNEL_NAME": "arn:aws:sqs:...",
        "CREATED": datetime(2026, 1, 1),
        "LAST_ALTERED": datetime(2026, 1, 2),
        "COMMENT": "loads orders",
        "PATTERN": ".*orders.*",
    }
    row.update(overrides)
    return row


def task_row(**overrides):
    """A ``SHOW TASKS`` row, in the lowercase shape the page documents."""
    row = {
        "created_on": datetime(2026, 1, 1),
        "name": "REFRESH_ORDERS",
        "id": "1",
        "database_name": "MY_DB",
        "schema_name": "PUBLIC",
        "owner": "SYSADMIN",
        "comment": "refresh",
        "warehouse": "COMPUTE_WH",
        "schedule": "5 MINUTE",
        "scheduling_mode": "FIXED",
        "target_completion_interval": None,
        "predecessors": "[]",
        "state": "started",
        "definition": "CALL LOAD_ORDERS()",
        "condition": None,
        "allow_overlapping_execution": "false",
        "error_integration": None,
        "success_integration": None,
        "last_committed_on": None,
        "last_suspended_on": None,
        "last_suspended_reason": None,
        "owner_role_type": "ROLE",
        "config": None,
        "task_relations": '{"Predecessors":[]}',
        "execute_as_user": None,
        "overlap_policy": "NO_OVERLAP",
    }
    row.update(overrides)
    return row


def stream_row(**overrides):
    """A ``SHOW STREAMS`` row, in the lowercase shape the page documents."""
    row = {
        "created_on": datetime(2026, 1, 1),
        "name": "ORDERS_STREAM",
        "database_name": "MY_DB",
        "schema_name": "PUBLIC",
        "owner": "SYSADMIN",
        "comment": "orders changes",
        "table_name": "ORDERS",
        "source_type": "Table",
        "base_tables": None,
        "type": "DELTA",
        "stale": "false",
        "mode": "DEFAULT",
        "stale_after": datetime(2026, 2, 1),
        "invalid_reason": "N/A",
        "owner_role_type": "ROLE",
    }
    row.update(overrides)
    return row


# ================================================================== #
# SQL text -- the rendered tree, pinned
# ================================================================== #


class TestCatalogFamilySQL:
    @pytest.mark.parametrize(
        "statement, expected_sql",
        [
            (SnowflakeFunctionListQueryStatement, FUNCTIONS_SQL),
            (SnowflakeProcedureListQueryStatement, PROCEDURES_SQL),
            (SnowflakeSequenceListQueryStatement, SEQUENCES_SQL),
            (SnowflakeStageListQueryStatement, STAGES_SQL),
            (SnowflakeFileFormatListQueryStatement, FILE_FORMATS_SQL),
            (SnowflakePipeListQueryStatement, PIPES_SQL),
        ],
    )
    def test_the_listing_is_exact(self, dialect, statement, expected_sql):
        assert statement(dialect, schema="PUBLIC").to_sql() == (
            expected_sql,
            ("PUBLIC",),
        )

    def test_the_schema_is_a_bind_value_not_an_identifier(self, dialect):
        sql, params = SnowflakeFunctionListQueryStatement(
            dialect, schema="PUBLIC'); DROP TABLE users;--"
        ).to_sql()
        assert params == ("PUBLIC'); DROP TABLE users;--",)
        assert "DROP TABLE" not in sql

    def test_tasks_and_streams_use_show_with_a_schema_scope(self, dialect):
        assert SnowflakeTaskListQueryStatement(dialect, schema="PUBLIC").to_sql() == (
            'SHOW TASKS IN SCHEMA "PUBLIC"',
            (),
        )
        assert SnowflakeStreamListQueryStatement(
            dialect, schema="PUBLIC"
        ).to_sql() == ('SHOW STREAMS IN SCHEMA "PUBLIC"', ())

    def test_tasks_and_streams_keep_the_bare_show_without_a_schema(self, dialect):
        assert SnowflakeTaskListQueryStatement(dialect).to_sql() == (
            "SHOW TASKS",
            (),
        )
        assert SnowflakeStreamListQueryStatement(dialect).to_sql() == (
            "SHOW STREAMS",
            (),
        )

    @pytest.mark.parametrize(
        "statement",
        [
            SnowflakeFunctionListQueryStatement,
            SnowflakeProcedureListQueryStatement,
            SnowflakeSequenceListQueryStatement,
            SnowflakeStageListQueryStatement,
            SnowflakeFileFormatListQueryStatement,
            SnowflakePipeListQueryStatement,
            SnowflakeTaskListQueryStatement,
            SnowflakeStreamListQueryStatement,
        ],
    )
    def test_every_statement_names_a_dialect_formatter(self, dialect, statement):
        method = statement(dialect, schema="PUBLIC").format_method
        assert method.endswith("_query_statement")
        assert callable(getattr(dialect, method)), statement.__name__


# ================================================================== #
# Routines and sequences
# ================================================================== #


class TestRoutineParsing:
    def test_a_function_row_maps_to_the_routine_shape(self, parser):
        [routine] = parser.parse_routines([function_row()], "FUNCTION", "PUBLIC")
        assert routine == SnowflakeRoutineInfo(
            name="ADD_ONE",
            kind="FUNCTION",
            schema="PUBLIC",
            catalog="MY_DB",
            language="SQL",
            argument_signature="(NUMBER)",
            return_type="NUMBER",
            owner="SYSADMIN",
            comment="adds one",
            created=datetime(2026, 1, 1),
            last_altered=datetime(2026, 1, 2),
            definition="SELECT N + 1",
            extra={
                "character_maximum_length": None,
                "character_octet_length": None,
                "numeric_precision": None,
                "numeric_precision_radix": None,
                "numeric_scale": None,
                "volatility": "IMMUTABLE",
                "is_null_call": False,
                "is_secure": False,
                "is_memoizable": False,
                "is_external": False,
                "is_data_metric": False,
                "is_aggregate": False,
                "runtime_version": None,
                "handler": None,
                "packages": None,
                "installed_packages": None,
                "artifact_repository": None,
                "external_access_integrations": None,
                "secrets": None,
                "owner_role_type": "ROLE",
            },
        )

    def test_a_procedure_row_maps_to_the_same_shape(self, parser):
        [routine] = parser.parse_routines([procedure_row()], "PROCEDURE", "PUBLIC")
        assert routine.name == "LOAD_ORDERS"
        assert routine.kind == "PROCEDURE"
        assert routine.language == "PYTHON"
        assert routine.argument_signature == "(VARCHAR)"
        assert routine.return_type == "VARCHAR"
        assert routine.definition.startswith("def main")
        assert routine.extra["runtime_version"] == "3.11"
        assert routine.extra["packages"] == "snowflake-snowpark-python"

    def test_function_only_columns_are_absent_on_a_procedure(self, parser):
        """The stable shape keeps the key; the value is ``None``, not a KeyError."""
        [routine] = parser.parse_routines([procedure_row()], "PROCEDURE", "PUBLIC")
        assert routine.extra["volatility"] is None
        assert routine.extra["is_aggregate"] is None

    def test_routine_keys_are_case_insensitive(self, parser):
        row = {key.lower(): value for key, value in function_row().items()}
        [routine] = parser.parse_routines([row], "FUNCTION", "PUBLIC")
        assert routine.name == "ADD_ONE"

    def test_an_unknown_routine_kind_reads_the_prefix_it_is_given(self, parser):
        [routine] = parser.parse_routines(
            [{"FUNCTION_NAME": "F", "FUNCTION_SCHEMA": "PUBLIC"}], "FUNCTION", "PUBLIC"
        )
        assert routine.kind == "FUNCTION"
        assert routine.name == "F"


class TestSequenceParsing:
    def test_a_sequence_row_uses_core_sequence_info_plus_extras(self, parser):
        [sequence] = parser.parse_sequences([sequence_row()], "PUBLIC")
        assert sequence == SequenceInfo(
            name="ORDERS_ID_SEQ",
            schema="PUBLIC",
            data_type="NUMBER",
            start_value=1,
            minimum_value=None,
            maximum_value=None,
            increment=1,
            cycle=None,
            cache_size=None,
            last_value=None,
            extra={
                "snowflake_catalog": "MY_DB",
                "snowflake_owner": "SYSADMIN",
                "snowflake_next_value": 4,
                "snowflake_ordered": True,
                "snowflake_numeric_precision": 38,
                "snowflake_numeric_precision_radix": 10,
                "snowflake_numeric_scale": 0,
                "snowflake_created": datetime(2026, 1, 1),
                "snowflake_last_altered": datetime(2026, 1, 2),
                "snowflake_comment": "order ids",
            },
        )

    def test_next_value_is_not_mislabelled_last_value(self, parser):
        [sequence] = parser.parse_sequences([sequence_row()], "PUBLIC")
        assert sequence.last_value is None
        assert sequence.extra["snowflake_next_value"] == 4

    def test_the_documented_not_applicable_fields_stay_none(self, parser):
        [sequence] = parser.parse_sequences(
            [
                sequence_row(
                    MINIMUM_VALUE="not-a-number",
                    MAXIMUM_VALUE="not-a-number",
                    CYCLE_OPTION="not-applicable",
                )
            ],
            "PUBLIC",
        )
        assert sequence.minimum_value is None
        assert sequence.maximum_value is None
        assert sequence.cycle is None

    def test_a_hypothetical_cycle_flag_still_reads(self, parser):
        [sequence] = parser.parse_sequences(
            [sequence_row(CYCLE_OPTION="NO")], "PUBLIC"
        )
        assert sequence.cycle is False


# ================================================================== #
# The catalog objects: stages, file formats, pipes, tasks, streams
# ================================================================== #


class TestCatalogObjectParsing:
    def test_stage_row_maps_to_the_catalog_shape(self, parser):
        [stage] = parser.parse_stages([stage_row()], "PUBLIC")
        assert stage == SnowflakeCatalogObjectInfo(
            name="ORDERS_STAGE",
            kind="STAGE",
            catalog="MY_DB",
            schema="PUBLIC",
            owner="SYSADMIN",
            comment="order files",
            created=datetime(2026, 1, 1),
            last_altered=datetime(2026, 1, 2),
            extra={
                "stage_url": "s3://bucket/path/",
                "stage_region": "us-east-1",
                "stage_type": "External Named",
            },
        )

    def test_file_format_row_keeps_its_options(self, parser):
        [file_format] = parser.parse_file_formats([file_format_row()], "PUBLIC")
        assert file_format.kind == "FILE FORMAT"
        assert file_format.extra["file_format_type"] == "CSV"
        assert file_format.extra["field_delimiter"] == ","
        assert file_format.extra["skip_header"] == 1
        assert file_format.extra["trim_space"] is True
        assert file_format.extra["error_on_column_count_mismatch"] is True

    def test_pipe_row_keeps_the_copy_definition_and_pattern(self, parser):
        [pipe] = parser.parse_pipes([pipe_row()], "PUBLIC")
        assert pipe.kind == "PIPE"
        assert pipe.extra["definition"].startswith("COPY INTO")
        assert pipe.extra["is_autoingest_enabled"] is True
        assert pipe.extra["pattern"] == ".*orders.*"

    def test_task_row_maps_lowercase_keys(self, parser):
        [task] = parser.parse_tasks([task_row()])
        assert task == SnowflakeCatalogObjectInfo(
            name="REFRESH_ORDERS",
            kind="TASK",
            catalog="MY_DB",
            schema="PUBLIC",
            owner="SYSADMIN",
            comment="refresh",
            created=datetime(2026, 1, 1),
            last_altered=None,
            extra={
                "id": "1",
                "warehouse": "COMPUTE_WH",
                "schedule": "5 MINUTE",
                "scheduling_mode": "FIXED",
                "target_completion_interval": None,
                "predecessors": "[]",
                "state": "started",
                "definition": "CALL LOAD_ORDERS()",
                "condition": None,
                "allow_overlapping_execution": False,
                "error_integration": None,
                "success_integration": None,
                "last_committed_on": None,
                "last_suspended_on": None,
                "last_suspended_reason": None,
                "task_relations": '{"Predecessors":[]}',
                "execute_as_user": None,
                "overlap_policy": "NO_OVERLAP",
                "owner_role_type": "ROLE",
                "config": None,
            },
        )

    def test_stream_row_reports_staleness(self, parser):
        [stream] = parser.parse_streams([stream_row()])
        assert stream.kind == "STREAM"
        assert stream.extra["table_name"] == "ORDERS"
        assert stream.extra["stale"] is False
        assert stream.extra["stale_after"] == datetime(2026, 2, 1)
        assert stream.extra["mode"] == "DEFAULT"

    def test_stale_true_reads_as_true(self, parser):
        [stream] = parser.parse_streams([stream_row(stale="TRUE")])
        assert stream.extra["stale"] is True

    def test_show_values_are_not_forced_into_datetimes(self, parser):
        """The driver may hand back text; the parser must not crash on it."""
        [task] = parser.parse_tasks([task_row(created_on="2026-01-01T00:00:00Z")])
        assert task.created == "2026-01-01T00:00:00Z"


# ================================================================== #
# Identity audit
# ================================================================== #


def column_row(**overrides):
    row = {
        "COLUMN_NAME": "id",
        "ORDINAL_POSITION": 1,
        "COLUMN_DEFAULT": None,
        "IS_NULLABLE": "NO",
        "DATA_TYPE": "NUMBER",
        "NUMERIC_PRECISION": 38,
        "NUMERIC_SCALE": 0,
        "IS_IDENTITY": "NO",
        "IDENTITY_GENERATION": None,
        "IDENTITY_START": None,
        "IDENTITY_INCREMENT": None,
        "IDENTITY_ORDERED": None,
        "KIND": "COLUMN",
        "EXPRESSION": None,
    }
    row.update(overrides)
    return row


class TestIdentityAudit:
    @pytest.fixture
    def mixin(self, mock_backend):
        mixin = SnowflakeIntrospectorMixin()
        mixin._backend = mock_backend
        return mixin

    def test_an_identity_column_reports_is_auto_increment(self, mixin):
        [column] = mixin.parse_columns(
            [
                column_row(
                    IS_IDENTITY="YES",
                    IDENTITY_GENERATION="BY DEFAULT",
                    IDENTITY_START="1",
                    IDENTITY_INCREMENT="1",
                    IDENTITY_ORDERED="YES",
                )
            ],
            "orders",
            "PUBLIC",
        )
        assert column.is_auto_increment is True
        assert column.extra["snowflake_auto_increment_source"] == "identity"
        assert column.extra["snowflake_identity"] is True
        assert column.extra["snowflake_identity_generation"] == "BY DEFAULT"
        assert column.extra["snowflake_identity_start"] == 1
        assert column.extra["snowflake_identity_increment"] == 1
        assert column.extra["snowflake_identity_ordered"] is True

    def test_a_plain_column_is_not_auto_increment(self, mixin):
        [column] = mixin.parse_columns([column_row()], "orders", "PUBLIC")
        assert column.is_auto_increment is False
        assert column.extra["snowflake_auto_increment_source"] is None

    def test_a_sequence_backed_default_is_reported(self, mixin):
        [column] = mixin.parse_columns(
            [column_row(COLUMN_DEFAULT="ORDERS_ID_SEQ.NEXTVAL")],
            "orders",
            "PUBLIC",
        )
        assert column.is_auto_increment is True
        assert column.extra["snowflake_auto_increment_source"] == "sequence_default"
        assert column.extra["snowflake_sequence_backed"] is True

    def test_identity_wins_over_the_default_when_both_are_present(self, mixin):
        [column] = mixin.parse_columns(
            [
                column_row(
                    IS_IDENTITY="YES",
                    COLUMN_DEFAULT="ORDERS_ID_SEQ.NEXTVAL",
                )
            ],
            "orders",
            "PUBLIC",
        )
        assert column.extra["snowflake_auto_increment_source"] == "identity"

    def test_a_virtual_column_reports_its_expression(self, mixin):
        [column] = mixin.parse_columns(
            [column_row(KIND="VIRTUAL_COLUMN", EXPRESSION="AMOUNT * 2")],
            "orders",
            "PUBLIC",
        )
        assert column.is_generated is True
        assert column.generated_expression == "AMOUNT * 2"

    def test_a_regular_column_has_no_generated_expression(self, mixin):
        [column] = mixin.parse_columns(
            [column_row(KIND="COLUMN", EXPRESSION="IGNORED")],
            "orders",
            "PUBLIC",
        )
        assert column.is_generated is False
        assert column.generated_expression is None

    def test_identity_spelling_is_case_insensitive(self, mixin):
        [column] = mixin.parse_columns(
            [column_row(IS_IDENTITY=" yes ")], "orders", "PUBLIC"
        )
        assert column.is_auto_increment is True

    def test_a_default_without_nextval_is_not_sequence_backed(self, mixin):
        [column] = mixin.parse_columns(
            [column_row(COLUMN_DEFAULT="0")], "orders", "PUBLIC"
        )
        assert column.is_auto_increment is False
        assert column.extra["snowflake_sequence_backed"] is False


# ================================================================== #
# Sync public API
# ================================================================== #


class TestSyncCatalogIntrospection:
    def test_list_routines_reads_both_views_and_sorts(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.side_effect = [
            [function_row(FUNCTION_NAME="Z_FN")],
            [procedure_row(PROCEDURE_NAME="A_PROC")],
        ]
        routines = sync_introspector.list_routines()

        assert [routine.name for routine in routines] == ["Z_FN", "A_PROC"]
        assert [routine.kind for routine in routines] == ["FUNCTION", "PROCEDURE"]
        sync_executor.execute.assert_any_call(FUNCTIONS_SQL, ("PUBLIC",))
        sync_executor.execute.assert_any_call(PROCEDURES_SQL, ("PUBLIC",))

    def test_list_routines_second_call_is_a_cache_hit(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.side_effect = [[function_row()], [procedure_row()]]
        first = sync_introspector.list_routines()
        second = sync_introspector.list_routines()
        assert first is second
        assert sync_executor.execute.call_count == 2

    def test_list_sequences_uses_the_configured_schema_and_caches(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [sequence_row()]
        first = sync_introspector.list_sequences()
        second = sync_introspector.list_sequences()
        assert first is second
        assert first[0].name == "ORDERS_ID_SEQ"
        sync_executor.execute.assert_called_once_with(SEQUENCES_SQL, ("PUBLIC",))

    @pytest.mark.parametrize(
        "method, statement, expected_sql",
        [
            ("list_stages", SnowflakeStageListQueryStatement, STAGES_SQL),
            (
                "list_file_formats",
                SnowflakeFileFormatListQueryStatement,
                FILE_FORMATS_SQL,
            ),
            ("list_pipes", SnowflakePipeListQueryStatement, PIPES_SQL),
        ],
    )
    def test_catalog_view_families_execute_their_statement(
        self, sync_introspector, sync_executor, method, statement, expected_sql
    ):
        sync_executor.execute.return_value = []
        getattr(sync_introspector, method)()
        sync_executor.execute.assert_called_once_with(expected_sql, ("PUBLIC",))

    def test_tasks_and_streams_execute_scoped_show(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = []
        sync_introspector.list_tasks()
        sync_executor.execute.assert_called_with(
            'SHOW TASKS IN SCHEMA "PUBLIC"', ()
        )
        sync_introspector.list_streams()
        sync_executor.execute.assert_called_with(
            'SHOW STREAMS IN SCHEMA "PUBLIC"', ()
        )

    def test_catalog_families_do_not_share_cache_entries(
        self, sync_introspector, sync_executor
    ):
        """The family name is part of the key, so five scope-sharing families
        cannot answer each other's questions."""
        sync_executor.execute.return_value = [stage_row()]
        sync_introspector.list_stages()
        sync_introspector.list_pipes()
        sync_introspector.list_tasks()
        assert sync_executor.execute.call_count == 3


# ================================================================== #
# Async public API
# ================================================================== #


class TestAsyncCatalogIntrospection:
    async def test_async_methods_await_the_same_statements(
        self, async_introspector, async_executor
    ):
        async_executor.execute.side_effect = [
            [function_row()],
            [procedure_row()],
            [sequence_row()],
            [stage_row()],
            [file_format_row()],
            [pipe_row()],
            [task_row()],
            [stream_row()],
        ]

        routines = await async_introspector.list_routines()
        sequences = await async_introspector.list_sequences()
        stages = await async_introspector.list_stages()
        file_formats = await async_introspector.list_file_formats()
        pipes = await async_introspector.list_pipes()
        tasks = await async_introspector.list_tasks()
        streams = await async_introspector.list_streams()

        assert len(routines) == 2
        assert sequences[0].name == "ORDERS_ID_SEQ"
        assert stages[0].kind == "STAGE"
        assert file_formats[0].kind == "FILE FORMAT"
        assert pipes[0].kind == "PIPE"
        assert tasks[0].kind == "TASK"
        assert streams[0].kind == "STREAM"
        assert async_executor.execute.await_count == 8

    async def test_async_catalog_listing_second_call_is_a_cache_hit(
        self, async_introspector, async_executor
    ):
        async_executor.execute.return_value = [stage_row()]
        first = await async_introspector.list_stages()
        second = await async_introspector.list_stages()
        assert first is second
        assert async_executor.execute.await_count == 1


# ================================================================== #
# Value semantics and sync/async symmetry
# ================================================================== #


class TestCatalogValueSemantics:
    def test_routine_and_catalog_values_are_frozen(self):
        from dataclasses import FrozenInstanceError

        with pytest.raises(FrozenInstanceError):
            SnowflakeRoutineInfo(name="F", kind="FUNCTION").name = "G"  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            SnowflakeCatalogObjectInfo(name="S", kind="STAGE").kind = "PIPE"  # type: ignore[misc]

    @pytest.mark.parametrize(
        "method",
        [
            "list_routines",
            "list_sequences",
            "list_stages",
            "list_file_formats",
            "list_pipes",
            "list_tasks",
            "list_streams",
        ],
    )
    def test_sync_and_async_methods_have_identical_signatures(self, method):
        assert inspect.signature(
            getattr(SnowflakeIntrospector, method)
        ) == inspect.signature(getattr(AsyncSnowflakeIntrospector, method))
