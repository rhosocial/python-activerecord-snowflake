# tests/rhosocial/activerecord_snowflake_test/feature/backend/schema/test_schema_diff.py
"""Tests for Snowflake schema diff."""

from datetime import datetime

from rhosocial.activerecord.backend.schema import (
    SchemaSnapshot, SchemaDiff,
)
from rhosocial.activerecord.backend.introspection.types import (
    ColumnInfo, ColumnNullable, TableInfo, TableType, DatabaseInfo,
)
from rhosocial.activerecord.backend.expression.types import IntegerType, VarCharType

from rhosocial.activerecord.backend.impl.snowflake.schema import SnowflakeSchemaDiffer


def _make_col(name, data_type, ordinal=1, nullable=ColumnNullable.NULLABLE,
              parsed_dt=None):
    return ColumnInfo(
        name=name,
        table_name="test",
        schema="PUBLIC",
        ordinal_position=ordinal,
        data_type=data_type.lower(),
        data_type_full=data_type,
        parsed_data_type=parsed_dt,
        nullable=nullable,
        default_value=None,
    )


def _make_snapshot(tables_dict):
    return SchemaSnapshot(
        dialect_class="SnowflakeDialect",
        captured_at=datetime.now(),
        database_info=DatabaseInfo(
            name="test", version="8.0.0",
            version_tuple=(8, 0, 0), vendor="Snowflake",
        ),
        tables=tables_dict,
    )


class TestSnowflakeSchemaDiffer:
    """Test SnowflakeSchemaDiffer compare method."""

    def test_no_changes(self):
        col = _make_col("id", "NUMBER", ordinal=1, parsed_dt=IntegerType())
        snap = _make_snapshot({"t": TableInfo(
            name="t", schema="PUBLIC", table_type=TableType.BASE_TABLE,
            columns=[col],
        )})
        differ = SnowflakeSchemaDiffer()
        diff = differ.compare(snap, snap)
        assert diff.is_empty

    def test_added_column(self):
        old_col = _make_col("id", "NUMBER", ordinal=1)
        new_col1 = _make_col("id", "NUMBER", ordinal=1)
        new_col2 = _make_col("name", "VARCHAR", ordinal=2)

        old_snap = _make_snapshot({"t": TableInfo(
            name="t", schema="PUBLIC", table_type=TableType.BASE_TABLE,
            columns=[old_col],
        )})
        new_snap = _make_snapshot({"t": TableInfo(
            name="t", schema="PUBLIC", table_type=TableType.BASE_TABLE,
            columns=[new_col1, new_col2],
        )})

        differ = SnowflakeSchemaDiffer()
        diff = differ.compare(old_snap, new_snap)

        assert "t" in diff.modified_tables
        td = diff.table_diffs["t"]
        added = [cd for cd in td.column_diffs if cd.is_added]
        assert len(added) == 1
        assert added[0].column_name == "name"

    def test_removed_column(self):
        old_col1 = _make_col("id", "NUMBER", ordinal=1)
        old_col2 = _make_col("name", "VARCHAR", ordinal=2)
        new_col = _make_col("id", "NUMBER", ordinal=1)

        old_snap = _make_snapshot({"t": TableInfo(
            name="t", schema="PUBLIC", table_type=TableType.BASE_TABLE,
            columns=[old_col1, old_col2],
        )})
        new_snap = _make_snapshot({"t": TableInfo(
            name="t", schema="PUBLIC", table_type=TableType.BASE_TABLE,
            columns=[new_col],
        )})

        differ = SnowflakeSchemaDiffer()
        diff = differ.compare(old_snap, new_snap)
        td = diff.table_diffs["t"]
        removed = [cd for cd in td.column_diffs if cd.is_removed]
        assert len(removed) == 1
        assert removed[0].column_name == "name"

    def test_modified_column_type(self):
        old_col = _make_col("name", "VARCHAR", ordinal=1,
                            parsed_dt=VarCharType(length=100))
        new_col = _make_col("name", "VARCHAR", ordinal=1,
                            parsed_dt=VarCharType(length=200))

        old_snap = _make_snapshot({"t": TableInfo(
            name="t", schema="PUBLIC", table_type=TableType.BASE_TABLE,
            columns=[old_col],
        )})
        new_snap = _make_snapshot({"t": TableInfo(
            name="t", schema="PUBLIC", table_type=TableType.BASE_TABLE,
            columns=[new_col],
        )})

        differ = SnowflakeSchemaDiffer()
        diff = differ.compare(old_snap, new_snap)
        td = diff.table_diffs["t"]
        modified = [cd for cd in td.column_diffs if cd.is_modified]
        assert len(modified) == 1
        assert modified[0].column_name == "name"

    def test_added_table(self):
        old_snap = _make_snapshot({})
        col = _make_col("id", "NUMBER", ordinal=1)
        new_snap = _make_snapshot({"new_table": TableInfo(
            name="new_table", schema="PUBLIC", table_type=TableType.BASE_TABLE,
            columns=[col],
        )})

        differ = SnowflakeSchemaDiffer()
        diff = differ.compare(old_snap, new_snap)
        assert "new_table" in diff.added_tables

    def test_removed_table(self):
        col = _make_col("id", "NUMBER", ordinal=1)
        old_snap = _make_snapshot({"old_table": TableInfo(
            name="old_table", schema="PUBLIC", table_type=TableType.BASE_TABLE,
            columns=[col],
        )})
        new_snap = _make_snapshot({})

        differ = SnowflakeSchemaDiffer()
        diff = differ.compare(old_snap, new_snap)
        assert "old_table" in diff.removed_tables
