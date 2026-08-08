"""Tests for Snowflake table DDL modifier support.

Covers CREATE OR REPLACE / TRANSIENT / TEMPORARY table modifiers,
DATA_RETENTION_TIME_IN_DAYS options, CLUSTER BY / DROP CLUSTERING KEY
and SEARCH OPTIMIZATION formatting.

Pure construction tests — no real Snowflake instance required.
"""

import pytest

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakeTableModifierSupport,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestSnowflakeTableModifierProtocol:
    """Dialect satisfies isinstance checks for the table modifier protocol."""

    def test_dialect_is_table_modifier_support(self, dialect):
        assert isinstance(dialect, SnowflakeTableModifierSupport)

    def test_supports_create_or_replace_table(self, dialect):
        assert dialect.supports_create_or_replace_table() is True

    def test_supports_transient_table(self, dialect):
        assert dialect.supports_transient_table() is True

    def test_supports_cluster_by(self, dialect):
        assert dialect.supports_cluster_by() is True

    def test_supports_search_optimization(self, dialect):
        assert dialect.supports_search_optimization() is True


class TestSnowflakeCreateTableModifiers:
    """CREATE OR REPLACE / TRANSIENT / TEMPORARY header modifier generation."""

    def test_modifier_none(self, dialect):
        assert dialect.format_create_table_modifier() == ""

    def test_modifier_or_replace(self, dialect):
        assert (
            dialect.format_create_table_modifier(or_replace=True)
            == "OR REPLACE"
        )

    def test_modifier_transient(self, dialect):
        assert (
            dialect.format_create_table_modifier(transient=True)
            == "TRANSIENT"
        )

    def test_modifier_temporary(self, dialect):
        assert (
            dialect.format_create_table_modifier(temporary=True)
            == "TEMPORARY"
        )

    def test_modifier_or_replace_transient(self, dialect):
        assert (
            dialect.format_create_table_modifier(
                or_replace=True, transient=True
            )
            == "OR REPLACE TRANSIENT"
        )

    def test_modifier_transient_temporary_mutually_exclusive(self, dialect):
        with pytest.raises(ValueError):
            dialect.format_create_table_modifier(
                transient=True, temporary=True
            )

    def test_compose_create_or_replace_transient_table(self, dialect):
        modifier = dialect.format_create_table_modifier(
            or_replace=True, transient=True
        )
        options = dialect.format_create_table_options(
            data_retention_time_in_days=1
        )
        sql = " ".join(
            part
            for part in ["CREATE", modifier, "TABLE t (c1 NUMBER)", options]
            if part
        )
        assert sql == (
            "CREATE OR REPLACE TRANSIENT TABLE t (c1 NUMBER) "
            "DATA_RETENTION_TIME_IN_DAYS = 1"
        )

    def test_compose_create_temporary_table(self, dialect):
        modifier = dialect.format_create_table_modifier(temporary=True)
        sql = " ".join(
            part
            for part in ["CREATE", modifier, "TABLE t (c1 NUMBER)", ""]
            if part
        )
        assert sql == "CREATE TEMPORARY TABLE t (c1 NUMBER)"

    def test_create_table_options_basic(self, dialect):
        assert (
            dialect.format_create_table_options(data_retention_time_in_days=1)
            == "DATA_RETENTION_TIME_IN_DAYS = 1"
        )

    def test_create_table_options_change_tracking(self, dialect):
        assert (
            dialect.format_create_table_options(change_tracking=True)
            == "CHANGE_TRACKING = TRUE"
        )

    def test_create_table_options_comment(self, dialect):
        assert (
            dialect.format_create_table_options(comment="hi")
            == "COMMENT = 'hi'"
        )

    def test_create_table_options_all(self, dialect):
        assert (
            dialect.format_create_table_options(
                data_retention_time_in_days=5,
                change_tracking=False,
                comment="c",
            )
            == "DATA_RETENTION_TIME_IN_DAYS = 5 CHANGE_TRACKING = FALSE "
            "COMMENT = 'c'"
        )

    def test_create_table_options_empty(self, dialect):
        assert dialect.format_create_table_options() == ""


class TestSnowflakeClusterBy:
    """ALTER TABLE CLUSTER BY / DROP CLUSTERING KEY generation."""

    def test_alter_table_cluster_by(self, dialect):
        assert (
            dialect.format_alter_table_cluster_by("t", ["c1"])
            == 'ALTER TABLE "t" CLUSTER BY ("c1")'
        )

    def test_alter_table_cluster_by_multiple(self, dialect):
        assert (
            dialect.format_alter_table_cluster_by("t", ["c1", "c2"])
            == 'ALTER TABLE "t" CLUSTER BY ("c1", "c2")'
        )

    def test_drop_clustering_key(self, dialect):
        assert (
            dialect.format_drop_clustering_key("t")
            == 'ALTER TABLE "t" DROP CLUSTERING KEY'
        )


class TestSnowflakeSearchOptimization:
    """ALTER TABLE ADD SEARCH OPTIMIZATION generation."""

    def test_add_search_optimization_on_equality(self, dialect):
        assert (
            dialect.format_add_search_optimization("t", on=["c1"])
            == 'ALTER TABLE "t" ADD SEARCH OPTIMIZATION ON EQUALITY("c1")'
        )

    def test_add_search_optimization_all_columns(self, dialect):
        assert (
            dialect.format_add_search_optimization("t")
            == 'ALTER TABLE "t" ADD SEARCH OPTIMIZATION'
        )

    def test_add_search_optimization_multiple_columns(self, dialect):
        assert (
            dialect.format_add_search_optimization("t", on=["c1", "c2"])
            == 'ALTER TABLE "t" ADD SEARCH OPTIMIZATION '
            'ON EQUALITY("c1", "c2")'
        )
