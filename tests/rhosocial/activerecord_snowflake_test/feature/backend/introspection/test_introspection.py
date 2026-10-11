# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_introspection.py
"""Tests for Snowflake introspection system.

Tests cover:
- SnowflakeIntrospectionMixin format_*_query methods
- SnowflakeIntrospectorMixin _parse_* methods
- SyncSnowflakeIntrospector with mock backend
- AsyncSnowflakeIntrospector with mock backend
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Any, Dict, List, Optional

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import SnowflakeIntrospectionMixin
from rhosocial.activerecord.backend.impl.snowflake.introspection import (
    SnowflakeIntrospectorMixin,
    SyncSnowflakeIntrospector,
    AsyncSnowflakeIntrospector,
)
from rhosocial.activerecord.backend.introspection.types import (
    DatabaseInfo,
    TableInfo,
    TableType,
    ColumnInfo,
    ColumnNullable,
    IndexInfo,
    IndexColumnInfo,
    IndexType,
    ForeignKeyInfo,
    ReferentialAction,
    ViewInfo,
    TriggerInfo,
)
from rhosocial.activerecord.backend.introspection.executor import SyncIntrospectorExecutor


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


# ================================================================== #
# Tests for SnowflakeIntrospectionMixin (Dialect layer)
# ================================================================== #

class TestSnowflakeIntrospectionCapabilities:
    """Test Snowflake introspection capability detection."""

    def test_supports_introspection(self, dialect):
        assert dialect.supports_introspection() is True

    def test_supports_database_info(self, dialect):
        assert dialect.supports_database_info() is True

    def test_supports_table_introspection(self, dialect):
        assert dialect.supports_table_introspection() is True

    def test_supports_column_introspection(self, dialect):
        assert dialect.supports_column_introspection() is True

    def test_supports_index_introspection(self, dialect):
        assert dialect.supports_index_introspection() is True

    def test_supports_foreign_key_introspection(self, dialect):
        assert dialect.supports_foreign_key_introspection() is True

    def test_supports_view_introspection(self, dialect):
        assert dialect.supports_view_introspection() is True

    def test_does_not_support_trigger_introspection(self, dialect):
        assert dialect.supports_trigger_introspection() is False


class TestSnowflakeIntrospectionSQLGeneration:
    """Test SQL generation for introspection queries."""

    def test_format_database_info_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import DatabaseInfoExpression
        expr = DatabaseInfoExpression(dialect)
        sql, params = expr.to_sql()
        assert "CURRENT_DATABASE()" in sql
        assert "CURRENT_VERSION()" in sql
        assert params == ()

    def test_format_table_list_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import TableListExpression
        expr = TableListExpression(dialect)
        expr.schema("MY_SCHEMA")
        sql, params = expr.to_sql()
        assert "INFORMATION_SCHEMA.TABLES" in sql
        assert "TABLE_SCHEMA = %s" in sql
        assert params == ("MY_SCHEMA",)

    def test_format_table_list_query_no_views(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import TableListExpression
        expr = TableListExpression(dialect)
        expr.schema("MY_SCHEMA")
        # include_views defaults to True
        sql, params = expr.to_sql()
        # When include_views=True, no TABLE_TYPE filter should be present
        assert "TABLE_TYPE = 'BASE TABLE'" not in sql

    def test_format_column_info_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import ColumnInfoExpression
        expr = ColumnInfoExpression(dialect, table_name="users")
        expr.schema("MY_SCHEMA")
        sql, params = expr.to_sql()
        assert "INFORMATION_SCHEMA.COLUMNS" in sql
        assert params == ("MY_SCHEMA", "users")

    def test_format_index_info_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import IndexInfoExpression
        expr = IndexInfoExpression(dialect, table_name="users")
        expr.schema("MY_SCHEMA")
        sql, params = expr.to_sql()
        assert "INFORMATION_SCHEMA.TABLE_CONSTRAINTS" in sql
        assert "INFORMATION_SCHEMA.KEY_COLUMN_USAGE" in sql
        assert "CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE')" in sql
        assert params == ("MY_SCHEMA", "users")

    def test_format_foreign_key_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import ForeignKeyExpression
        expr = ForeignKeyExpression(dialect, table_name="orders")
        expr.schema("MY_SCHEMA")
        sql, params = expr.to_sql()
        assert "INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS" in sql
        assert "INFORMATION_SCHEMA.KEY_COLUMN_USAGE" in sql
        assert "REFERENCED_TABLE_NAME" in sql
        assert "REFERENCED_COLUMN_NAME" in sql
        assert params == ("MY_SCHEMA", "orders")

    def test_format_view_list_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import ViewListExpression
        expr = ViewListExpression(dialect)
        expr.schema("MY_SCHEMA")
        sql, params = expr.to_sql()
        assert "INFORMATION_SCHEMA.VIEWS" in sql
        assert params == ("MY_SCHEMA",)

    def test_format_view_info_query(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import ViewInfoExpression
        expr = ViewInfoExpression(dialect, view_name="my_view")
        expr.schema("MY_SCHEMA")
        sql, params = expr.to_sql()
        assert "INFORMATION_SCHEMA.VIEWS" in sql
        assert "TABLE_NAME = %s" in sql
        assert params == ("MY_SCHEMA", "my_view")

    def test_format_trigger_list_query_returns_empty(self, dialect):
        from rhosocial.activerecord.backend.expression.introspection import TriggerListExpression
        expr = TriggerListExpression(dialect)
        expr.schema("MY_SCHEMA")
        sql, params = expr.to_sql()
        assert "1 = 0" in sql


# ================================================================== #
# Tests for SnowflakeIntrospectorMixin (Parse methods)
# ================================================================== #

class TestSnowflakeIntrospectorParsing:
    """Test _parse_* methods for converting raw rows to data structures."""

    @pytest.fixture
    def introspector_mixin(self):
        """Create a minimal introspector mixin with mock backend."""

        class MockBackend:
            _version = (8, 32, 0)
            config = MagicMock()
            config.schema = "PUBLIC"

        mixin = SnowflakeIntrospectorMixin()
        mixin._backend = MockBackend()
        return mixin

    def test_parse_database_info(self, introspector_mixin):
        rows = [
            {"CATALOG_NAME": "MY_DB", "SERVER_VERSION": "8.32.0"},
        ]
        result = introspector_mixin._parse_database_info(rows)
        assert isinstance(result, DatabaseInfo)
        assert result.name == "MY_DB"
        assert result.vendor == "Snowflake"
        assert result.version_tuple == (8, 32, 0)

    def test_parse_database_info_empty_rows(self, introspector_mixin):
        result = introspector_mixin._parse_database_info([])
        assert isinstance(result, DatabaseInfo)
        assert result.vendor == "Snowflake"

    def test_parse_tables(self, introspector_mixin):
        rows = [
            {"TABLE_NAME": "users", "TABLE_TYPE": "BASE TABLE", "COMMENT": None},
            {"TABLE_NAME": "v_users", "TABLE_TYPE": "VIEW", "COMMENT": "user view"},
        ]
        result = introspector_mixin._parse_tables(rows, "PUBLIC")
        assert len(result) == 2
        assert result[0].name == "users"
        assert result[0].table_type == TableType.BASE_TABLE
        assert result[1].name == "v_users"
        assert result[1].table_type == TableType.VIEW
        assert result[1].comment == "user view"

    def test_parse_columns(self, introspector_mixin):
        rows = [
            {
                "COLUMN_NAME": "id",
                "ORDINAL_POSITION": 1,
                "COLUMN_DEFAULT": None,
                "IS_NULLABLE": "NO",
                "DATA_TYPE": "NUMBER",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "NUMERIC_PRECISION": 38,
                "NUMERIC_SCALE": 0,
                "COLLATION_NAME": None,
                "COMMENT": None,
            },
            {
                "COLUMN_NAME": "name",
                "ORDINAL_POSITION": 2,
                "COLUMN_DEFAULT": None,
                "IS_NULLABLE": "YES",
                "DATA_TYPE": "VARCHAR",
                "CHARACTER_MAXIMUM_LENGTH": 16777216,
                "NUMERIC_PRECISION": None,
                "NUMERIC_SCALE": None,
                "COLLATION_NAME": "utf-8",
                "COMMENT": "user name",
            },
        ]
        result = introspector_mixin._parse_columns(rows, "users", "PUBLIC")
        assert len(result) == 2

        assert result[0].name == "id"
        assert result[0].data_type == "number"
        assert result[0].nullable == ColumnNullable.NOT_NULL
        assert result[0].numeric_precision == 38

        assert result[1].name == "name"
        assert result[1].data_type == "varchar"
        assert result[1].nullable == ColumnNullable.NULLABLE
        assert result[1].character_maximum_length == 16777216
        assert result[1].comment == "user name"


# ================================================================== #
# The catalog row's SIZE reaches parse_type
#
# Snowflake splits one declared type across several INFORMATION_SCHEMA
# columns: DATA_TYPE is "the standard Snowflake data type of the column"
# and never carries a size, CHARACTER_MAXIMUM_LENGTH holds "Maximum length
# in characters of string columns", NUMERIC_PRECISION / NUMERIC_SCALE hold
# "Numeric precision of numeric columns" / "Scale of numeric columns".
# https://docs.snowflake.com/en/sql-reference/info-schema/columns
#
# So every test below builds the *catalog row Snowflake documents* and
# asserts the parsed DataType is **== to the declaration that produced
# that column** -- asserted, not inferred from the SQL. A VARCHAR(50)
# column used to answer 16777216, the documented default for an unsized
# VARCHAR, purely because the width never left the catalog; and a
# NUMBER(10, 2) column answered a bare DecimalType with both parameters
# dropped. Both are the same defect on two shapes.
# ================================================================== #

class TestSnowflakeCatalogSizeReachesParseType:
    """Declared -> catalog row -> parsed, compared with ``==``.

    The whole point of these is the assertion at the end of each: two
    ``DataType`` value objects that must be the same column. Matching
    rendered SQL would not prove it -- ``VARCHAR(50)`` and
    ``VARCHAR(16777216)`` are both real Snowflake SQL, and the differ
    compares the type objects, not the words.
    """

    @pytest.fixture
    def introspector_mixin(self):
        class MockBackend:
            _version = (10, 2, 0)
            config = MagicMock()
            config.schema = "PUBLIC"
            dialect = SnowflakeDialect(version=(10, 2, 0))

        mixin = SnowflakeIntrospectorMixin()
        mixin._backend = MockBackend()
        return mixin

    @staticmethod
    def _row(data_type, cml=None, precision=None, scale=None):
        """One ``INFORMATION_SCHEMA.COLUMNS`` row, as the manual describes it."""
        return {
            "COLUMN_NAME": "c",
            "ORDINAL_POSITION": 1,
            "COLUMN_DEFAULT": None,
            "IS_NULLABLE": "YES",
            "DATA_TYPE": data_type,
            "CHARACTER_MAXIMUM_LENGTH": cml,
            "NUMERIC_PRECISION": precision,
            "NUMERIC_SCALE": scale,
            "COLLATION_NAME": None,
            "COMMENT": None,
        }

    def _parsed(self, introspector_mixin, row):
        columns = introspector_mixin._parse_columns([row], "t", "PUBLIC")
        return columns[0].parsed_data_type

    @pytest.mark.parametrize("width", [1, 20, 50, 200, 134217728])
    def test_a_sized_varchar_column_keeps_its_own_width(self, introspector_mixin, width):
        """The defect: a ``VARCHAR(50)`` column answered ``16777216``.

        That is Snowflake's documented default for an *unsized* VARCHAR
        ("If no length is specified, the default is 16777216"), so the
        parser had answered honestly -- to a question nobody asked. The
        width was sitting unused in CHARACTER_MAXIMUM_LENGTH.
        """
        from rhosocial.activerecord.backend.expression.types import VarCharType

        declared = VarCharType(introspector_mixin._backend.dialect, length=width)
        parsed = self._parsed(
            introspector_mixin, self._row("VARCHAR", cml=width))
        assert parsed.length == width, (
            f"VARCHAR({width}) column introspected as width {parsed.length}"
        )
        assert parsed == declared

    def test_the_documented_default_width_is_what_an_unsized_varchar_gets(self, introspector_mixin):
        """A bare ``VarCharType`` and the column it produced must be one column.

        ``DESC TABLE`` renders a bare ``VARCHAR`` as ``VARCHAR(16777216)``,
        so the catalog reports that width back and the declaration has to
        agree -- which it does because the dialect declares the server's
        default in ``type_parameter_defaults()`` rather than the parser
        inventing one.
        """
        from rhosocial.activerecord.backend.expression.types import VarCharType

        declared = VarCharType(introspector_mixin._backend.dialect)
        assert declared.length == 16777216
        parsed = self._parsed(
            introspector_mixin, self._row("VARCHAR", cml=16777216))
        assert parsed == declared

    def test_a_legacy_text_data_type_word_still_keeps_the_width(self, introspector_mixin):
        """Before bundle BCR-1960, ``DATA_TYPE`` reads ``TEXT`` for every string.

        The bundle that would change it to ``VARCHAR`` is **postponed with
        no new release date**, so ``TEXT`` is what accounts report today.
        That word used to parse as the unbounded concept whatever the size
        was, so a ``VARCHAR(50)`` column lost its 50 -- the width is the
        defect, and it is what the manual settles: ``TEXT`` is "Synonymous
        with VARCHAR", so a *sized* TEXT is a sized VARCHAR.

        https://docs.snowflake.com/en/release-notes/bcr-bundles/un-bundled/bcr-1960
        """
        from rhosocial.activerecord.backend.expression.types import VarCharType

        dialect = introspector_mixin._backend.dialect
        parsed = self._parsed(introspector_mixin, self._row("TEXT", cml=50))
        assert parsed.length == 50
        assert parsed == VarCharType(dialect, length=50)

    def test_a_bare_text_word_is_still_the_unbounded_concept(self, introspector_mixin):
        """The other half of the rule: no size in, no size claimed.

        ``TextType`` carries no width at all, so the bare word is the only
        honest reading of a bare ``TEXT``.
        """
        from rhosocial.activerecord.backend.expression.types import TextType

        parsed = self._parsed(introspector_mixin, self._row("TEXT"))
        assert parsed == TextType(introspector_mixin._backend.dialect)

    @pytest.mark.parametrize("precision,scale", [(10, 2), (20, 2), (5, 5), (38, 37)])
    def test_a_sized_number_column_keeps_its_precision_and_scale(
        self, introspector_mixin, precision, scale
    ):
        """The second shape of the same defect, and the one item 4 of the brief.

        A ``NUMBER(10, 2)`` column used to answer a bare ``DecimalType``:
        ``NUMERIC_PRECISION`` and ``NUMERIC_SCALE`` were selected by the
        query, recorded on ``ColumnInfo``, and then never read.

        ``(38, 0)`` is deliberately **not** in this list: it is the
        documented default and therefore the bare form, which the next test
        covers. ``parse_type`` keeps both halves of it -- composing
        ``NUMBER(38)`` because a scale of ``0`` was read as absent would
        have been its own silent drop.
        """
        from rhosocial.activerecord.backend.expression.types import DecimalType

        dialect = introspector_mixin._backend.dialect
        declared = DecimalType(dialect, precision=precision, scale=scale)
        parsed = self._parsed(
            introspector_mixin,
            self._row("NUMBER", precision=precision, scale=scale),
        )
        assert (parsed.precision, parsed.scale) == (precision, scale)
        assert parsed == declared

    def test_a_bare_number_column_is_the_documented_default(self, introspector_mixin):
        """``NUMBER(38, 0)`` and a bare ``NUMBER`` are the same column.

        "By default, precision is 38, and scale is 0; that is, NUMBER(38, 0)"
        -- and ``DESC TABLE`` renders the bare ``NUMBER`` and an explicit
        ``NUMBER(38, 0)`` identically, so the catalog cannot tell them apart
        and neither should this backend invent a difference.  The catalog's two
        columns are composed into the explicit pair (the bare-word folding this
        method used to do was a stand-in for core resolution) and the parsed
        value compares equal to a bare declaration because core resolves the
        declared default onto ``DecimalType`` at read time.
        """
        from rhosocial.activerecord.backend.expression.types import DecimalType

        dialect = introspector_mixin._backend.dialect
        row = self._row("NUMBER", precision=38, scale=0)
        assert introspector_mixin._catalog_type_string(
            row, dialect) == "NUMBER(38, 0)"
        parsed = self._parsed(introspector_mixin, row)
        assert parsed == DecimalType(dialect)
        # and the declared default is where the resolution reads its number from
        assert dialect.type_parameter_defaults()["decimal"] == {
            "precision": 38, "scale": 0,
        }

    def test_the_length_is_not_fed_to_a_numeric_column(self, introspector_mixin):
        """Which column answers which shape, decided per type.

        CHARACTER_MAXIMUM_LENGTH is documented as "Maximum length in
        characters of **string** columns". A stray value there must not
        turn a NUMBER column into something with a width.
        """
        parsed = self._parsed(
            introspector_mixin,
            self._row("NUMBER", cml=50, precision=10, scale=2),
        )
        assert parsed.precision == 10
        assert parsed.scale == 2

    def test_precision_and_scale_are_not_fed_to_an_integer_column(self, introspector_mixin):
        """The integer names are documented as ``NUMBER(38, 0)``, not as
        ``NUMBER`` *with parameters*.

        "Synonymous with NUMBER, **except precision and scale can't be
        specified**" -- so the 38 the catalog reports for an ``INT`` column
        is the bare NUMBER those names are, not a declared precision.
        Composing it would turn every integer column into
        ``DecimalType(38, 0)`` and lose the integer concept entirely.
        """
        from rhosocial.activerecord.backend.expression.types import IntegerType

        dialect = introspector_mixin._backend.dialect
        parsed = self._parsed(
            introspector_mixin,
            self._row("INTEGER", precision=38, scale=0),
        )
        assert parsed == IntegerType(dialect)

    def test_the_float_family_takes_no_precision(self, introspector_mixin):
        """``FLOAT``'s precision is in binary digits, the catalog's is not.

        ``DESC TABLE`` renders ``DOUBLE``, ``DOUBLE PRECISION`` and
        ``REAL`` as a bare ``FLOAT`` with no precision, so there is nothing
        documented to compose -- and the column that would settle the unit,
        ``NUMERIC_PRECISION_RADIX``, is not selected by the query. Feeding a
        number whose unit is unresolved would be a guess, so the bare word
        is what the parser sees.
        """
        from rhosocial.activerecord.backend.expression.types import (
            DoubleType,
            FloatType,
        )

        dialect = introspector_mixin._backend.dialect
        for word, expected in (("FLOAT", FloatType), ("DOUBLE", DoubleType),
                               ("REAL", DoubleType)):
            parsed = self._parsed(
                introspector_mixin, self._row(word, precision=15, scale=None))
            assert parsed == expected(dialect), f"{word} -> {parsed!r}"

    def test_data_type_full_carries_the_size_and_data_type_does_not(self, introspector_mixin):
        """The two ``ColumnInfo`` fields finally differ, which is their purpose.

        ``data_type`` is the word core's differ falls back to when a type
        cannot be parsed; ``data_type_full`` is the spelling that says how
        wide the column is.
        """
        columns = introspector_mixin._parse_columns(
            [self._row("VARCHAR", cml=50)], "t", "PUBLIC")
        assert columns[0].data_type == "varchar"
        assert columns[0].data_type_full == "VARCHAR(50)"

    @pytest.mark.parametrize(
        "row",
        [
            # no length reported at all
            {"DATA_TYPE": "VARCHAR", "CHARACTER_MAXIMUM_LENGTH": None},
            # zero is not a column Snowflake can declare
            {"DATA_TYPE": "VARCHAR", "CHARACTER_MAXIMUM_LENGTH": 0},
            # a size the driver could not turn into a number
            {"DATA_TYPE": "VARCHAR", "CHARACTER_MAXIMUM_LENGTH": "wide"},
            # no precision reported for the exact numeric shape
            {"DATA_TYPE": "NUMBER", "NUMERIC_PRECISION": None},
        ],
    )
    def test_an_absent_size_composes_the_bare_word(self, introspector_mixin, row):
        """No size, no parentheses -- and no crash.

        The bare word is a legitimate answer rather than a fallback: it is
        what ``DATA_TYPE`` really contains, and ``parse_type`` already
        completes it from ``type_parameter_defaults()``.
        """
        from rhosocial.activerecord.backend.expression.types import (
            DecimalType,
            VarCharType,
        )

        full = {**self._row(None), **row}
        dialect = introspector_mixin._backend.dialect
        parsed = self._parsed(introspector_mixin, full)
        expected = (
            VarCharType(dialect) if row["DATA_TYPE"] == "VARCHAR"
            else DecimalType(dialect)
        )
        assert parsed == expected

    def test_an_unreadable_type_degrades_one_column_not_the_table(self, introspector_mixin):
        """``parsed_data_type is None`` means "could not be read", and only that.

        Core's differ branches on the field: when both sides carry a type it
        compares the objects, and only when one is ``None`` does it fall back
        to the ``data_type`` string. So one unreadable column must not abort
        ``list_columns`` for the whole table -- MariaDB's introspector already
        carries this guard for the same reason.
        """
        good = self._row("VARCHAR", cml=50)
        good["COLUMN_NAME"] = "good"
        with patch.object(
            type(introspector_mixin._backend.dialect),
            "parse_type",
            side_effect=ValueError("not a type this backend can read"),
        ):
            with pytest.warns(RuntimeWarning, match="could not read"):
                columns = introspector_mixin._parse_columns(
                    [good], "t", "PUBLIC")
        assert len(columns) == 1
        assert columns[0].parsed_data_type is None
        assert columns[0].data_type == "varchar"

    def test_the_width_column_is_never_a_byte_count(self):
        """The unit is part of the mapping, so it is pinned rather than assumed.

        ``CHARACTER_MAXIMUM_LENGTH`` is documented "in **characters**", and
        every concept fed from it is a character-counted string. Adding a
        byte-counted concept to that table without a column of its own would
        read a length in the wrong unit, which is worse than not reading it at
        all -- so the two sets are asserted disjoint.
        """
        width = SnowflakeIntrospectorMixin._SNOW_WIDTH_COLUMN
        assert set(width.values()) == {"CHARACTER_MAXIMUM_LENGTH"}
        byte_counted = set(SnowflakeIntrospectorMixin._SNOW_BYTE_COUNTED_CONCEPTS)
        assert byte_counted, "the byte-counted concepts must stay named"
        assert not byte_counted & set(width), (
            f"{byte_counted & set(width)} would be read in characters"
        )

    @pytest.mark.parametrize("word", ["BINARY", "VARBINARY"])
    def test_a_binary_column_is_left_at_the_bare_word(self, introspector_mixin, word):
        """Snowflake states BINARY's length in bytes and documents no column for it.

        ``CHARACTER_MAXIMUM_LENGTH`` is "in characters of **string** columns" and
        ``CHARACTER_OCTET_LENGTH`` is "in bytes of **string** columns", while the
        manual files BINARY under "Data types for **binary** strings" and says the
        length "is always measured in terms of bytes". So a character column is the
        wrong unit and no byte column is documented for it -- which means this
        backend does not claim to recover a binary width, and says so rather than
        reading the wrong number.
        https://docs.snowflake.com/en/sql-reference/data-types-text
        """
        from rhosocial.activerecord.backend.expression.types import BlobType

        dialect = introspector_mixin._backend.dialect
        # A length in *either* catalog column must not be adopted for binary.
        for cml in (None, 100, 8388608):
            row = self._row(word, cml=cml, precision=None, scale=None)
            composed = introspector_mixin._catalog_type_string(row, dialect)
            assert composed == word, f"{word} with CML={cml} composed {composed!r}"
            assert self._parsed(introspector_mixin, row) == BlobType(dialect)

    def test_parse_indexes_as_constraints(self, introspector_mixin):
        """Snowflake maps PK/unique constraints to IndexInfo."""
        rows = [
            {"CONSTRAINT_NAME": "PK_USERS", "CONSTRAINT_TYPE": "PRIMARY KEY", "COLUMN_NAME": "id", "ORDINAL_POSITION": 1},
            {"CONSTRAINT_NAME": "UK_USERS_EMAIL", "CONSTRAINT_TYPE": "UNIQUE", "COLUMN_NAME": "email", "ORDINAL_POSITION": 1},
        ]
        result = introspector_mixin._parse_indexes(rows, "users", "PUBLIC")
        assert len(result) == 2

        pk = next(i for i in result if i.is_primary)
        assert pk.name == "PK_USERS"
        assert pk.is_unique is True
        assert len(pk.columns) == 1
        assert pk.columns[0].name == "id"

        uk = next(i for i in result if not i.is_primary)
        assert uk.name == "UK_USERS_EMAIL"
        assert uk.is_unique is True
        assert uk.columns[0].name == "email"

    def test_parse_foreign_keys(self, introspector_mixin):
        rows = [
            {
                "CONSTRAINT_NAME": "FK_ORDERS_USER",
                "UPDATE_RULE": "NO ACTION",
                "DELETE_RULE": "CASCADE",
                "COLUMN_NAME": "user_id",
                "ORDINAL_POSITION": 1,
                "REFERENCED_TABLE_NAME": "users",
                "REFERENCED_COLUMN_NAME": "id",
            },
        ]
        result = introspector_mixin._parse_foreign_keys(rows, "orders", "PUBLIC")
        assert len(result) == 1
        assert result[0].name == "FK_ORDERS_USER"
        assert result[0].columns == ["user_id"]
        assert result[0].referenced_table == "users"
        assert result[0].referenced_columns == ["id"]
        assert result[0].on_delete == ReferentialAction.CASCADE
        assert result[0].on_update == ReferentialAction.NO_ACTION

    def test_parse_composite_foreign_key(self, introspector_mixin):
        rows = [
            {
                "CONSTRAINT_NAME": "FK_ORDER_ITEMS",
                "UPDATE_RULE": "NO ACTION",
                "DELETE_RULE": "RESTRICT",
                "COLUMN_NAME": "order_id",
                "ORDINAL_POSITION": 1,
                "REFERENCED_TABLE_NAME": "orders",
                "REFERENCED_COLUMN_NAME": "id",
            },
            {
                "CONSTRAINT_NAME": "FK_ORDER_ITEMS",
                "UPDATE_RULE": "NO ACTION",
                "DELETE_RULE": "RESTRICT",
                "COLUMN_NAME": "product_id",
                "ORDINAL_POSITION": 2,
                "REFERENCED_TABLE_NAME": "orders",
                "REFERENCED_COLUMN_NAME": "product_id",
            },
        ]
        result = introspector_mixin._parse_foreign_keys(rows, "order_items", "PUBLIC")
        assert len(result) == 1
        assert result[0].columns == ["order_id", "product_id"]
        assert result[0].referenced_columns == ["id", "product_id"]

    def test_parse_views(self, introspector_mixin):
        rows = [
            {
                "TABLE_NAME": "v_active_users",
                "VIEW_DEFINITION": "SELECT * FROM users WHERE active = TRUE",
                "CHECK_OPTION": "NONE",
                "IS_UPDATABLE": "NO",
            },
        ]
        result = introspector_mixin._parse_views(rows, "PUBLIC")
        assert len(result) == 1
        assert result[0].name == "v_active_users"
        assert result[0].definition == "SELECT * FROM users WHERE active = TRUE"
        assert result[0].is_updatable is False

    def test_parse_view_info(self, introspector_mixin):
        rows = [
            {
                "TABLE_NAME": "v_active_users",
                "VIEW_DEFINITION": "SELECT * FROM users WHERE active = TRUE",
                "CHECK_OPTION": "NONE",
                "IS_UPDATABLE": "NO",
            },
        ]
        result = introspector_mixin._parse_view_info(rows, "v_active_users", "PUBLIC")
        assert result is not None
        assert result.name == "v_active_users"

    def test_parse_view_info_not_found(self, introspector_mixin):
        result = introspector_mixin._parse_view_info([], "nonexistent", "PUBLIC")
        assert result is None

    def test_parse_triggers_always_empty(self, introspector_mixin):
        """Snowflake doesn't support triggers."""
        result = introspector_mixin._parse_triggers([], "PUBLIC")
        assert result == []


# ================================================================== #
# Tests for SyncSnowflakeIntrospector with mock executor
# ================================================================== #

class TestSyncSnowflakeIntrospector:
    """Test SyncSnowflakeIntrospector end-to-end with mock executor."""

    @pytest.fixture
    def mock_backend(self):
        backend = MagicMock()
        backend._version = (8, 32, 0)
        backend.config = MagicMock()
        backend.config.schema = "PUBLIC"
        backend.config.database = "MY_DB"
        backend.dialect = SnowflakeDialect(version=(8, 32, 0))
        return backend

    @pytest.fixture
    def mock_executor(self):
        return MagicMock(spec=SyncIntrospectorExecutor)

    @pytest.fixture
    def introspector(self, mock_backend, mock_executor):
        return SyncSnowflakeIntrospector(mock_backend, mock_executor)

    def test_get_default_schema(self, introspector):
        assert introspector._get_default_schema() == "PUBLIC"

    def test_get_database_info(self, introspector, mock_executor):
        mock_executor.execute.return_value = [
            {"CATALOG_NAME": "MY_DB", "SERVER_VERSION": "8.32.0"},
        ]
        info = introspector.get_database_info()
        assert isinstance(info, DatabaseInfo)
        assert info.vendor == "Snowflake"
        assert info.name == "MY_DB"
        mock_executor.execute.assert_called_once()

    def test_list_tables(self, introspector, mock_executor):
        mock_executor.execute.return_value = [
            {"TABLE_NAME": "users", "TABLE_TYPE": "BASE TABLE", "COMMENT": None},
        ]
        tables = introspector.list_tables()
        assert len(tables) == 1
        assert tables[0].name == "users"

    def test_list_columns(self, introspector, mock_executor):
        mock_executor.execute.return_value = [
            {
                "COLUMN_NAME": "id",
                "ORDINAL_POSITION": 1,
                "COLUMN_DEFAULT": None,
                "IS_NULLABLE": "NO",
                "DATA_TYPE": "NUMBER",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "NUMERIC_PRECISION": 38,
                "NUMERIC_SCALE": 0,
                "COLLATION_NAME": None,
                "COMMENT": None,
            },
        ]
        columns = introspector.list_columns("users")
        assert len(columns) == 1
        assert columns[0].name == "id"

    def test_caching(self, introspector, mock_executor):
        """Test that results are cached and not re-queried."""
        mock_executor.execute.return_value = [
            {"CATALOG_NAME": "MY_DB", "SERVER_VERSION": "8.32.0"},
        ]
        # First call
        introspector.get_database_info()
        # Second call should use cache
        introspector.get_database_info()
        # Executor should only be called once
        assert mock_executor.execute.call_count == 1


# ================================================================== #
# Tests for AsyncSnowflakeIntrospector with mock executor
# ================================================================== #

class TestAsyncSnowflakeIntrospector:
    """Test AsyncSnowflakeIntrospector with mock async executor."""

    @pytest.fixture
    def mock_backend(self):
        backend = MagicMock()
        backend._version = (8, 32, 0)
        backend.config = MagicMock()
        backend.config.schema = "PUBLIC"
        backend.config.database = "MY_DB"
        backend.dialect = SnowflakeDialect(version=(8, 32, 0))
        return backend

    @pytest.fixture
    def mock_executor(self):
        executor = MagicMock()
        executor.execute = AsyncMock(return_value=[
            {"CATALOG_NAME": "MY_DB", "SERVER_VERSION": "8.32.0"},
        ])
        return executor

    @pytest.fixture
    def introspector(self, mock_backend, mock_executor):
        return AsyncSnowflakeIntrospector(mock_backend, mock_executor)

    @pytest.mark.asyncio
    async def test_get_database_info(self, introspector, mock_executor):
        info = await introspector.get_database_info()
        assert isinstance(info, DatabaseInfo)
        assert info.vendor == "Snowflake"

    @pytest.mark.asyncio
    async def test_list_tables(self, introspector, mock_executor):
        mock_executor.execute.return_value = [
            {"TABLE_NAME": "users", "TABLE_TYPE": "BASE TABLE", "COMMENT": None},
        ]
        tables = await introspector.list_tables()
        assert len(tables) == 1

    @pytest.mark.asyncio
    async def test_caching(self, introspector, mock_executor):
        """Test async caching works the same as sync."""
        await introspector.get_database_info()
        await introspector.get_database_info()
        assert mock_executor.execute.call_count == 1


# ================================================================== #
# Tests for _SnowflakeAsyncIntrospectorExecutor
# ================================================================== #

class TestSnowflakeAsyncExecutor:
    """Test the custom async executor that wraps sync cursor operations."""

    @pytest.mark.asyncio
    async def test_execute_returns_rows(self):
        from rhosocial.activerecord.backend.impl.snowflake.introspection.introspector import (
            _SnowflakeAsyncIntrospectorExecutor,
        )

        mock_cursor = MagicMock()
        mock_cursor.description = [("COL1",), ("COL2",)]
        mock_cursor.fetchall.return_value = [(1, "a"), (2, "b")]
        mock_cursor.close = MagicMock()

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_backend = MagicMock()
        mock_backend._connection = mock_connection
        mock_backend._executor = None

        executor = _SnowflakeAsyncIntrospectorExecutor(mock_backend)
        result = await executor.execute("SELECT * FROM t", ())

        assert len(result) == 2
        assert result[0] == {"COL1": 1, "COL2": "a"}
        assert result[1] == {"COL1": 2, "COL2": "b"}
        mock_cursor.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_no_description(self):
        from rhosocial.activerecord.backend.impl.snowflake.introspection.introspector import (
            _SnowflakeAsyncIntrospectorExecutor,
        )

        mock_cursor = MagicMock()
        mock_cursor.description = None
        mock_cursor.close = MagicMock()

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_backend = MagicMock()
        mock_backend._connection = mock_connection
        mock_backend._executor = None

        executor = _SnowflakeAsyncIntrospectorExecutor(mock_backend)
        result = await executor.execute("INSERT INTO t VALUES (1)", ())

        assert result == []
        mock_cursor.close.assert_called_once()
