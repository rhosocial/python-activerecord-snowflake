# tests/rhosocial/activerecord_snowflake_test/feature/backend/schema/test_schema_diff.py
"""Tests for Snowflake schema diff."""

from datetime import datetime

import pytest

from rhosocial.activerecord.backend.schema import (
    SchemaSnapshot, SchemaDiff,
)
from rhosocial.activerecord.backend.introspection.types import (
    ColumnInfo, ColumnNullable, TableInfo, TableType, DatabaseInfo,
)
from rhosocial.activerecord.backend.expression.types import (
    DecimalType, IntegerType, VarCharType,
)

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


def _introspected_column(name, declared_type, dialect):
    """One column as the *catalog* reports it, through the real introspector.

    Every other test in this file builds ``ColumnInfo`` by hand, which is right
    for testing the differ and wrong for testing the round trip: the whole
    question here is what the introspector hands the differ, so the column is
    built by running the declaration's catalog row through
    ``SnowflakeIntrospectorMixin._parse_columns`` and taking what comes out.
    """
    from unittest.mock import MagicMock

    from rhosocial.activerecord.backend.impl.snowflake.introspection import (
        SnowflakeIntrospectorMixin,
    )

    sql, _ = dialect.format_data_type(declared_type)
    word = sql.split("(")[0]
    arguments = sql[len(word):].strip("()")
    numbers = [int(n) for n in arguments.replace(",", " ").split() if n]

    # CHARACTER_MAXIMUM_LENGTH answers "string columns", NUMERIC_PRECISION and
    # NUMERIC_SCALE answer "numeric columns" — which is how the catalog splits
    # one declared type across three columns.
    # https://docs.snowflake.com/en/sql-reference/info-schema/columns
    is_string = declared_type.name in ("varchar", "char", "text",
                                       "snowflake_varchar")
    is_exact_numeric = declared_type.name in ("decimal", "snowflake_number")
    row = {
        "COLUMN_NAME": name,
        "ORDINAL_POSITION": 1,
        "COLUMN_DEFAULT": None,
        "IS_NULLABLE": "YES",
        "DATA_TYPE": "NUMBER" if is_exact_numeric else word,
        "CHARACTER_MAXIMUM_LENGTH": numbers[0] if (is_string and numbers) else None,
        "NUMERIC_PRECISION": numbers[0] if (is_exact_numeric and numbers) else None,
        "NUMERIC_SCALE": numbers[1] if (is_exact_numeric and len(numbers) > 1) else None,
        "COLLATION_NAME": None,
        "COMMENT": None,
    }
    # A bare NUMBER is stored as NUMBER(38, 0): "By default, precision is 38,
    # and scale is 0; that is, NUMBER(38, 0)".
    # https://docs.snowflake.com/en/sql-reference/data-types-numeric
    if is_exact_numeric and not numbers:
        row["NUMERIC_PRECISION"] = 38
        row["NUMERIC_SCALE"] = 0

    class MockBackend:
        config = MagicMock()
        config.schema = "PUBLIC"

    backend = MockBackend()
    backend.dialect = dialect
    mixin = SnowflakeIntrospectorMixin()
    mixin._backend = backend
    return mixin._parse_columns([row], "t", "PUBLIC")[0]


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


class TestSnowflakeSchemaDifferRoundTrip:
    """The harm the introspector defect caused, end to end.

    A declared value that does not survive the round trip is not cosmetic:
    the differ compares the *type objects*, so a ``VARCHAR(50)`` column
    introspected as ``VarCharType(16777216)`` is reported as **modified**
    against the declaration that created it — a change on a column nobody
    touched, which is what this class asserts does not happen.

    These go through the real ``_parse_columns``, not a hand-built
    ``ColumnInfo``, because the type the differ sees is the one the
    introspector composed.
    """

    @pytest.fixture
    def dialect(self):
        from rhosocial.activerecord.backend.impl.snowflake.dialect import (
            SnowflakeDialect,
        )
        return SnowflakeDialect(version=(10, 2, 0))

    def _table(self, *columns):
        return TableInfo(
            name="t", schema="PUBLIC", table_type=TableType.BASE_TABLE,
            columns=list(columns),
        )

    def _snapshot_of(self, *columns):
        return _make_snapshot({"t": self._table(*columns)})

    def _modified_names(self, diff):
        table = diff.table_diffs.get("t")
        if table is None:
            return []
        return [d.column_name for d in table.column_diffs if d.is_modified]

    @pytest.mark.parametrize("width", [1, 20, 50, 200, 1000])
    def test_a_sized_varchar_column_is_not_reported_as_changed(self, dialect, width):
        declared = VarCharType(dialect, length=width)
        introspected = _introspected_column("name", declared, dialect)
        # The declaration side is the type the caller wrote.
        declaration = _make_col("name", "VARCHAR", parsed_dt=declared)

        diff = SnowflakeSchemaDiffer().compare(
            self._snapshot_of(declaration),
            self._snapshot_of(introspected),
        )

        assert introspected.parsed_data_type == declared
        assert self._modified_names(diff) == [], (
            f"VARCHAR({width}) reported as modified"
        )
        assert diff.is_empty

    def test_an_unsized_varchar_column_is_not_reported_as_changed(self, dialect):
        """The bare form's half of the round trip.

        An unsized ``VARCHAR`` on Snowflake *is* ``VARCHAR(16777216)``, so the
        catalog reports that width back and the bare declaration has to agree —
        which it does because the dialect declares the server's default rather
        than the parser inventing one.
        """
        declared = VarCharType(dialect)
        introspected = _introspected_column("name", declared, dialect)
        declaration = _make_col("name", "VARCHAR", parsed_dt=declared)

        diff = SnowflakeSchemaDiffer().compare(
            self._snapshot_of(declaration),
            self._snapshot_of(introspected),
        )

        assert declared.length == 16777216
        assert introspected.parsed_data_type == declared
        assert diff.is_empty

    @pytest.mark.parametrize("precision,scale", [(10, 2), (20, 2), (5, 5)])
    def test_a_sized_number_column_is_not_reported_as_changed(
        self, dialect, precision, scale
    ):
        """The numeric half: ``NUMERIC_PRECISION``/``NUMERIC_SCALE`` were dropped.

        A ``NUMBER(10, 2)`` column introspected as a bare ``DecimalType``, so
        every sized numeric column in the schema was reported as modified on
        every run.
        """
        declared = DecimalType(dialect, precision=precision, scale=scale)
        introspected = _introspected_column("amount", declared, dialect)
        declaration = _make_col("amount", "NUMBER", parsed_dt=declared)

        diff = SnowflakeSchemaDiffer().compare(
            self._snapshot_of(declaration),
            self._snapshot_of(introspected),
        )

        assert (introspected.parsed_data_type.precision,
                introspected.parsed_data_type.scale) == (precision, scale)
        assert introspected.parsed_data_type == declared
        assert diff.is_empty

    def test_an_unsized_number_column_is_not_reported_as_changed(self, dialect):
        """``NUMBER(38, 0)`` is the bare ``NUMBER``, so the pair must not
        become a difference.

        The catalog reports 38/0 for a bare ``NUMBER`` because that is what the
        server stores it as.  The introspected side carries those two numbers
        explicitly and the declared side resolves them from the dialect's
        declaration, so ``==`` calls the two one column and no change is
        reported — the two routes meet on the same pair rather than one having
        to be folded back to a bare word.
        """
        declared = DecimalType(dialect)
        introspected = _introspected_column("amount", declared, dialect)
        declaration = _make_col("amount", "NUMBER", parsed_dt=declared)

        diff = SnowflakeSchemaDiffer().compare(
            self._snapshot_of(declaration),
            self._snapshot_of(introspected),
        )

        assert introspected.parsed_data_type == declared
        assert (introspected.parsed_data_type.precision,
                introspected.parsed_data_type.scale) == (38, 0)
        assert diff.is_empty

    def test_a_genuine_width_change_is_still_reported(self, dialect):
        """The counterpart: the fix must not have gone blind.

        Composing the size is only useful if a *real* change still shows up.
        """
        old = _introspected_column(
            "name", VarCharType(dialect, length=50), dialect)
        new = _introspected_column(
            "name", VarCharType(dialect, length=200), dialect)

        diff = SnowflakeSchemaDiffer().compare(
            _make_snapshot({"t": self._table(old)}),
            _make_snapshot({"t": self._table(new)}),
        )

        modified = [d for d in diff.table_diffs["t"].column_diffs if d.is_modified]
        assert len(modified) == 1
        assert modified[0].column_name == "name"

    def test_a_genuine_precision_change_is_still_reported(self, dialect):
        old = _introspected_column(
            "amount", DecimalType(dialect, precision=10, scale=2), dialect)
        new = _introspected_column(
            "amount", DecimalType(dialect, precision=12, scale=2), dialect)

        diff = SnowflakeSchemaDiffer().compare(
            _make_snapshot({"t": self._table(old)}),
            _make_snapshot({"t": self._table(new)}),
        )

        modified = [d for d in diff.table_diffs["t"].column_diffs if d.is_modified]
        assert len(modified) == 1
        assert modified[0].column_name == "amount"

    def test_a_scale_change_is_still_reported(self, dialect):
        """Scale alone is a real change: it changes the storage.

        "the same value stored in a column of type NUMBER(10,5) consumes more
        space than NUMBER(5,0)".
        https://docs.snowflake.com/en/sql-reference/data-types-numeric
        """
        old = _introspected_column(
            "amount", DecimalType(dialect, precision=10, scale=2), dialect)
        new = _introspected_column(
            "amount", DecimalType(dialect, precision=10, scale=4), dialect)

        diff = SnowflakeSchemaDiffer().compare(
            _make_snapshot({"t": self._table(old)}),
            _make_snapshot({"t": self._table(new)}),
        )

        modified = [d for d in diff.table_diffs["t"].column_diffs if d.is_modified]
        assert len(modified) == 1
        assert modified[0].column_name == "amount"
