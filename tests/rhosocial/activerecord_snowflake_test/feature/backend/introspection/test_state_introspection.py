# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_state_introspection.py
"""The neutral object-state API on Snowflake's introspectors.

Every test is offline. Rows are fabricated from the documented column names and
value domains; no Snowflake account is contacted, so a passing test pins the
statement and the parser, never the account's answer.

Documentation the expectations were written from:

* https://docs.snowflake.com/en/sql-reference/info-schema/tables
* https://docs.snowflake.com/en/sql-reference/info-schema/sequences
* https://docs.snowflake.com/en/sql-reference/info-schema/schemata
"""

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import ProtocolNotImplementedError
from rhosocial.activerecord.backend.impl.snowflake.cli.introspect import (
    INTROSPECT_TYPES,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression.introspection import (
    SnowflakeObjectExistsQueryStatement,
    SnowflakeTableStateQueryStatement,
)
from rhosocial.activerecord.backend.impl.snowflake.introspection import (
    AsyncSnowflakeIntrospector,
    SnowflakeIntrospector,
    SnowflakeIntrospectorMixin,
)
from rhosocial.activerecord.backend.introspection.base import (
    AbstractIntrospector,
    AsyncAbstractIntrospector,
)
from rhosocial.activerecord.backend.introspection.errors import ObjectNotFoundError
from rhosocial.activerecord.backend.introspection.executor import IntrospectorExecutor
from rhosocial.activerecord.backend.introspection.types import (
    ItemKind,
    PartitionState,
    SequenceState,
)

TABLE_STATE_SQL = (
    "SELECT TABLE_NAME, TABLE_TYPE, IS_TRANSIENT, IS_TEMPORARY, CLUSTERING_KEY, "
    "AUTO_CLUSTERING_ON, COMMENT FROM INFORMATION_SCHEMA.TABLES "
    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
    "AND NOT (TABLE_TYPE IN ('VIEW', 'MATERIALIZED VIEW'))"
)

SCHEMA_NAMES_SQL = (
    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
    "WHERE SCHEMA_NAME = %s LIMIT %s"
)

TABLE_EXISTS_SQL = (
    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = %s "
    "AND TABLE_SCHEMA = %s AND NOT (TABLE_TYPE IN ('VIEW', 'MATERIALIZED VIEW')) "
    "LIMIT %s"
)

SEQUENCE_EXISTS_SQL = (
    "SELECT SEQUENCE_NAME FROM INFORMATION_SCHEMA.SEQUENCES "
    "WHERE SEQUENCE_NAME = %s AND SEQUENCE_SCHEMA = %s LIMIT %s"
)

FUNCTION_EXISTS_SQL = (
    "SELECT FUNCTION_NAME FROM INFORMATION_SCHEMA.FUNCTIONS "
    "WHERE FUNCTION_NAME = %s AND FUNCTION_SCHEMA = %s LIMIT %s"
)

SEQUENCE_STATES_SQL = (
    "SELECT SEQUENCE_CATALOG, SEQUENCE_SCHEMA, SEQUENCE_NAME, SEQUENCE_OWNER, "
    "DATA_TYPE, NUMERIC_PRECISION, NUMERIC_PRECISION_RADIX, NUMERIC_SCALE, "
    "START_VALUE, MINIMUM_VALUE, MAXIMUM_VALUE, NEXT_VALUE, INCREMENT, "
    "CYCLE_OPTION, CREATED, LAST_ALTERED, ORDERED, COMMENT "
    "FROM INFORMATION_SCHEMA.SEQUENCES WHERE SEQUENCE_SCHEMA = %s "
    "ORDER BY SEQUENCE_NAME"
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


def table_row(**overrides):
    row = {
        "TABLE_NAME": "ORDERS",
        "TABLE_TYPE": "BASE TABLE",
        "IS_TRANSIENT": "NO",
        "IS_TEMPORARY": "NO",
        "CLUSTERING_KEY": None,
        "AUTO_CLUSTERING_ON": False,
        "COMMENT": None,
    }
    row.update(overrides)
    return row


def schema_row(**overrides):
    row = {
        "CATALOG_NAME": "MY_DB",
        "SCHEMA_NAME": "PUBLIC",
        "SCHEMA_OWNER": "SYSADMIN",
        "IS_TRANSIENT": "NO",
        "IS_MANAGED_ACCESS": "NO",
        "RETENTION_TIME": 1,
        "CREATED": None,
        "LAST_ALTERED": None,
        "COMMENT": None,
    }
    row.update(overrides)
    return row


def sequence_row(**overrides):
    row = {
        "SEQUENCE_CATALOG": "MY_DB",
        "SEQUENCE_SCHEMA": "PUBLIC",
        "SEQUENCE_NAME": "ORDER_SEQ",
        "SEQUENCE_OWNER": "SYSADMIN",
        "DATA_TYPE": "NUMBER",
        "NUMERIC_PRECISION": 38,
        "NUMERIC_PRECISION_RADIX": 10,
        "NUMERIC_SCALE": 0,
        "START_VALUE": "1",
        "MINIMUM_VALUE": None,
        "MAXIMUM_VALUE": None,
        "NEXT_VALUE": "7",
        "INCREMENT": "2",
        "CYCLE_OPTION": None,
        "CREATED": None,
        "LAST_ALTERED": None,
        "ORDERED": "NO",
        "COMMENT": None,
    }
    row.update(overrides)
    return row


# ================================================================== #
# Statements
# ================================================================== #


class TestStateStatements:
    def test_table_state_sql_is_exact(self, dialect):
        sql, params = SnowflakeTableStateQueryStatement(
            dialect, table_name="ORDERS", schema="PUBLIC"
        ).to_sql()
        assert sql == TABLE_STATE_SQL
        assert params == ("PUBLIC", "ORDERS")

    @pytest.mark.parametrize(
        "kind, name, schema, expected_sql",
        (
            (ItemKind.SCHEMA, "PUBLIC", None, SCHEMA_NAMES_SQL),
            (ItemKind.TABLE, "ORDERS", "PUBLIC", TABLE_EXISTS_SQL),
            (ItemKind.SEQUENCE, "ORDER_SEQ", "PUBLIC", SEQUENCE_EXISTS_SQL),
            (ItemKind.FUNCTION, "ADD_ONE", "PUBLIC", FUNCTION_EXISTS_SQL),
        ),
    )
    def test_object_exists_sql_is_exact(self, dialect, kind, name, schema, expected_sql):
        sql, params = SnowflakeObjectExistsQueryStatement(
            dialect, kind=kind, name=name, schema=schema
        ).to_sql()
        assert sql == expected_sql
        assert params[0] == name
        assert params[-1] == 1

    def test_schema_kind_takes_no_schema_filter(self, dialect):
        sql, params = SnowflakeObjectExistsQueryStatement(
            dialect, kind=ItemKind.SCHEMA, name="PUBLIC", schema="IGNORED"
        ).to_sql()
        assert "SCHEMA_SCHEMA" not in sql
        assert params == ("PUBLIC", 1)

    def test_table_kind_excludes_the_view_spellings(self, dialect):
        sql, _ = SnowflakeObjectExistsQueryStatement(
            dialect, kind=ItemKind.TABLE, name="ORDERS", schema="PUBLIC"
        ).to_sql()
        assert "NOT (TABLE_TYPE IN ('VIEW', 'MATERIALIZED VIEW'))" in sql

    def test_a_kind_without_a_catalogue_refuses(self, dialect):
        for kind in (
            ItemKind.TYPE,
            ItemKind.DOMAIN,
            ItemKind.EXTENSION,
            ItemKind.TABLESPACE,
            ItemKind.PARTITION_FUNCTION,
            ItemKind.PARTITION_SCHEME,
            ItemKind.FULLTEXT_CATALOG,
        ):
            statement = SnowflakeObjectExistsQueryStatement(
                dialect, kind=kind, name="X", schema="PUBLIC"
            )
            with pytest.raises(ProtocolNotImplementedError) as caught:
                statement.to_sql()
            assert "item_exists" in str(caught.value)

    def test_a_catalogue_word_is_stored_as_the_word(self, dialect):
        statement = SnowflakeObjectExistsQueryStatement(
            dialect, kind="sequence", name="ORDER_SEQ", schema="PUBLIC"
        )
        assert statement.kind == "sequence"
        assert ItemKind(statement.kind) is ItemKind.SEQUENCE

    def test_both_statements_name_a_dialect_formatter(self, dialect):
        for statement in (
            SnowflakeTableStateQueryStatement(dialect, table_name="ORDERS"),
            SnowflakeObjectExistsQueryStatement(
                dialect, kind=ItemKind.TABLE, name="ORDERS"
            ),
        ):
            method = statement.format_method
            assert method.endswith("_query_statement")
            assert callable(getattr(dialect, method))


# ================================================================== #
# Parsing
# ================================================================== #


class TestParseTableState:
    def test_regular_table(self, parser):
        state = parser.parse_table_state([table_row()], "ORDERS", "PUBLIC")
        assert state.name == "ORDERS"
        assert state.schema == "PUBLIC"
        assert state.kind == "regular"
        assert state.traits == ()
        assert state.comment is None
        assert state.raw["snowflake_table_type"] == "BASE TABLE"

    def test_transient_table(self, parser):
        state = parser.parse_table_state(
            [table_row(IS_TRANSIENT="YES")], "ORDERS", "PUBLIC"
        )
        assert state.kind == "transient"
        assert state.raw["snowflake_is_transient"] is True

    def test_temporary_table_reads_the_flag(self, parser):
        state = parser.parse_table_state(
            [table_row(IS_TEMPORARY="YES")], "ORDERS", "PUBLIC"
        )
        assert state.kind == "temporary"

    def test_temporary_table_reads_the_catalogue_spelling(self, parser):
        """A temporary table whose flag is not reported is still temporary."""
        state = parser.parse_table_state(
            [table_row(TABLE_TYPE="TEMPORARY TABLE")], "ORDERS", "PUBLIC"
        )
        assert state.kind == "temporary"

    def test_temporary_wins_over_transient(self, parser):
        state = parser.parse_table_state(
            [table_row(IS_TRANSIENT="YES", IS_TEMPORARY="YES")], "ORDERS", "PUBLIC"
        )
        assert state.kind == "temporary"

    def test_clustering_is_a_trait_and_the_text_is_raw(self, parser):
        key = "LINEAR(TO_DATE(ORDER_DATE))"
        state = parser.parse_table_state(
            [
                table_row(CLUSTERING_KEY=key, AUTO_CLUSTERING_ON=True, COMMENT="orders")
            ],
            "ORDERS",
            "PUBLIC",
        )
        assert state.traits == ("clustered", "auto_clustering")
        assert state.raw["snowflake_clustering_key"] == key
        assert state.comment == "orders"

    def test_a_vendor_kind_spelling_is_kept(self, parser):
        state = parser.parse_table_state(
            [table_row(TABLE_TYPE="HYBRID TABLE")], "ORDERS", "PUBLIC"
        )
        assert state.kind == "regular"
        assert state.raw["snowflake_table_type"] == "HYBRID TABLE"

    def test_an_empty_answer_raises_named_object_not_found(self, parser):
        with pytest.raises(ObjectNotFoundError) as caught:
            parser.parse_table_state([], "MISSING", "PUBLIC")
        assert "MISSING" in str(caught.value)
        assert "PUBLIC" in str(caught.value)


class TestParseSequenceStates:
    def test_projects_onto_the_neutral_shape(self, parser):
        [state] = parser.parse_sequence_states([sequence_row()], "PUBLIC")
        assert isinstance(state, SequenceState)
        assert state.name == "ORDER_SEQ"
        assert state.schema == "PUBLIC"
        assert state.start == 1
        assert state.increment == 2
        assert state.raw["snowflake_owner"] == "SYSADMIN"
        assert state.raw["snowflake_next_value"] == 7

    def test_owned_by_is_none_because_the_owner_is_a_role(self, parser):
        [state] = parser.parse_sequence_states([sequence_row()], "PUBLIC")
        assert state.owned_by is None


# ================================================================== #
# Manager methods
# ================================================================== #


class TestTableStateMethod:
    def test_reads_one_catalogue_row(self, sync_introspector, sync_executor):
        sync_executor.execute.return_value = [
            table_row(IS_TRANSIENT="YES", COMMENT="orders")
        ]
        state = sync_introspector.get_table_state("ORDERS")
        sql, params = sync_executor.execute.call_args.args
        assert sql == TABLE_STATE_SQL
        assert params == ("PUBLIC", "ORDERS")
        assert state.kind == "transient"
        assert state.comment == "orders"

    def test_partitioning_is_an_explicit_no_scheme_answer(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [table_row()]
        state = sync_introspector.get_table_state("ORDERS")
        assert isinstance(state.partitioning, PartitionState)
        assert state.partitioning.scheme is None
        assert state.partitioning.bounds == ()

    def test_a_second_read_is_a_cache_hit(self, sync_introspector, sync_executor):
        sync_executor.execute.return_value = [table_row()]
        sync_introspector.get_table_state("ORDERS")
        sync_introspector.get_table_state("ORDERS")
        assert sync_executor.execute.call_count == 1

    def test_a_missing_table_raises_and_is_not_cached(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = []
        with pytest.raises(ObjectNotFoundError):
            sync_introspector.get_table_state("MISSING")
        assert sync_executor.execute.call_count == 1
        assert len(sync_introspector.cache) == 0

    async def test_awaiting_reads_one_catalogue_row(self, async_introspector):
        async_introspector._executor.execute.return_value = [
            table_row(IS_TEMPORARY="YES")
        ]
        state = await async_introspector.get_table_state("ORDERS")
        assert state.kind == "temporary"
        assert isinstance(state.partitioning, PartitionState)
        assert state.partitioning.scheme is None


class TestPartitionStateMethod:
    def test_answers_a_state_with_no_scheme(self, sync_introspector):
        state = sync_introspector.get_partition_state("ORDERS")
        assert isinstance(state, PartitionState)
        assert state.scheme is None
        assert state.bounds == ()
        assert state.has_default is False
        assert state.raw["snowflake_addressable_partitions"] is False

    def test_include_stats_does_not_query_anything(
        self, sync_introspector, sync_executor
    ):
        sync_introspector.get_partition_state("ORDERS", include_stats=True)
        sync_executor.execute.assert_not_called()

    def test_no_catalogue_read_is_performed(self, sync_introspector, sync_executor):
        sync_introspector.get_partition_state("MISSING")
        sync_executor.execute.assert_not_called()

    async def test_awaiting_answers_the_same_state(self, async_introspector):
        state = await async_introspector.get_partition_state("ORDERS")
        assert state.scheme is None
        assert state.bounds == ()
        async_introspector._executor.execute.assert_not_called()


class TestNeutralSchemas:
    def test_returns_the_names_of_the_current_database(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [
            schema_row(),
            schema_row(SCHEMA_NAME="ANALYTICS"),
        ]
        assert sync_introspector.list_schemas() == ["PUBLIC", "ANALYTICS"]
        sync_executor.execute.assert_called_once()

    def test_the_complete_answer_keeps_its_record(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [schema_row()]
        infos = sync_introspector.list_schema_infos()
        assert infos[0].name == "PUBLIC"

    def test_the_two_answers_do_not_share_a_cache_entry(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [schema_row()]
        sync_introspector.list_schemas()
        sync_introspector.list_schema_infos()
        # The neutral names and the complete records are two entries; the
        # second call of either is served from the cache.
        assert len(sync_introspector.cache) == 2

    async def test_awaiting_returns_the_names(self, async_introspector):
        async_introspector._executor.execute.return_value = [schema_row()]
        assert await async_introspector.list_schemas() == ["PUBLIC"]


class TestSequenceStatesMethod:
    def test_returns_neutral_states(self, sync_introspector, sync_executor):
        sync_executor.execute.return_value = [sequence_row()]
        [state] = sync_introspector.list_sequence_states()
        sql, params = sync_executor.execute.call_args.args
        assert sql == SEQUENCE_STATES_SQL
        assert params == ("PUBLIC",)
        assert isinstance(state, SequenceState)

    async def test_awaiting_returns_neutral_states(self, async_introspector):
        async_introspector._executor.execute.return_value = [sequence_row()]
        [state] = await async_introspector.list_sequence_states()
        assert state.name == "ORDER_SEQ"


class TestItemExists:
    def test_true_and_false_come_from_the_rows(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.side_effect = [
            [{"SEQUENCE_NAME": "ORDER_SEQ"}],
            [],
        ]
        assert sync_introspector.item_exists(ItemKind.SEQUENCE, "ORDER_SEQ") is True
        assert sync_introspector.item_exists(ItemKind.SEQUENCE, "OTHER") is False

    def test_the_catalogue_word_is_accepted(self, sync_introspector, sync_executor):
        sync_executor.execute.return_value = [{"SEQUENCE_NAME": "ORDER_SEQ"}]
        assert sync_introspector.item_exists("sequence", "ORDER_SEQ") is True

    @pytest.mark.parametrize(
        "kind",
        (
            ItemKind.TYPE,
            ItemKind.DOMAIN,
            ItemKind.EXTENSION,
            ItemKind.TABLESPACE,
            ItemKind.PARTITION_FUNCTION,
            ItemKind.PARTITION_SCHEME,
            ItemKind.FULLTEXT_CATALOG,
        ),
    )
    def test_kinds_without_a_catalogue_refuse(
        self, sync_introspector, sync_executor, kind
    ):
        with pytest.raises(ProtocolNotImplementedError) as caught:
            sync_introspector.item_exists(kind, "X")
        message = str(caught.value)
        assert "item_exists" in message
        assert "Snowflake" in message
        sync_executor.execute.assert_not_called()

    def test_answers_are_not_cached(self, sync_introspector, sync_executor):
        sync_executor.execute.return_value = [{"SEQUENCE_NAME": "ORDER_SEQ"}]
        sync_introspector.item_exists(ItemKind.SEQUENCE, "ORDER_SEQ")
        sync_introspector.item_exists(ItemKind.SEQUENCE, "ORDER_SEQ")
        assert sync_executor.execute.call_count == 2

    def test_schema_kind_uses_schemata_without_a_schema_filter(
        self, sync_introspector, sync_executor
    ):
        sync_executor.execute.return_value = [{"SCHEMA_NAME": "PUBLIC"}]
        assert sync_introspector.item_exists(ItemKind.SCHEMA, "PUBLIC") is True
        sql, params = sync_executor.execute.call_args.args
        assert sql == SCHEMA_NAMES_SQL
        assert params == ("PUBLIC", 1)

    @pytest.mark.parametrize(
        "kind, expected_sql",
        (
            (ItemKind.TABLE, TABLE_EXISTS_SQL),
            (ItemKind.SEQUENCE, SEQUENCE_EXISTS_SQL),
            (ItemKind.FUNCTION, FUNCTION_EXISTS_SQL),
        ),
    )
    def test_schema_scoped_kinds_filter_by_the_schema(
        self, sync_introspector, sync_executor, kind, expected_sql
    ):
        sync_executor.execute.return_value = []
        sync_introspector.item_exists(kind, "X")
        sql, params = sync_executor.execute.call_args.args
        assert sql == expected_sql
        assert params[0] == "X"
        assert params[1] == "PUBLIC"

    async def test_awaiting_answers_from_the_rows(self, async_introspector):
        async_introspector._executor.execute.side_effect = [
            [{"FUNCTION_NAME": "ADD_ONE"}],
            [],
        ]
        assert (
            await async_introspector.item_exists(ItemKind.FUNCTION, "ADD_ONE")
            is True
        )
        assert (
            await async_introspector.item_exists(ItemKind.FUNCTION, "OTHER")
            is False
        )


# ================================================================== #
# Surface
# ================================================================== #


class TestSurface:
    def test_sync_and_await_signatures_match(self):
        for name in (
            "get_table_state",
            "get_partition_state",
            "list_sequence_states",
            "list_schemas",
            "item_exists",
        ):
            assert inspect.signature(
                getattr(SnowflakeIntrospector, name)
            ) == inspect.signature(getattr(AsyncSnowflakeIntrospector, name)), name

    def test_no_partition_listing_exists(self):
        for manager in (
            SnowflakeIntrospector,
            AsyncSnowflakeIntrospector,
            AbstractIntrospector,
            AsyncAbstractIntrospector,
        ):
            assert not hasattr(manager, "list_partitions"), manager.__name__

    def test_the_cli_offers_no_partitions_family(self):
        assert "partitions" not in INTROSPECT_TYPES
        assert "partition-metadata" not in INTROSPECT_TYPES
