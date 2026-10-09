# tests/rhosocial/activerecord_snowflake_test/feature/backend/types/test_column_types.py
"""Snowflake's column-type table, asserted against the rebuilt core protocol.

Everything asserted here is **文档（待云验）**: the table was built from
Snowflake's official documentation, and no Snowflake instance was reachable
while it was written. These tests therefore check that the backend *says* what
it means, and that the provisional cells stay visibly provisional -- they
cannot check that a server agrees, which is what the cloud probe is for.
"""
import datetime
import decimal
import enum
import inspect
import uuid

import pytest

from rhosocial.activerecord.backend.dialect.mixins import ColumnTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import ColumnTypeSupport
from rhosocial.activerecord.backend.expression.column_types import (
    ArrayColumn,
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    DateTimeColumn,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    UUIDColumn,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import column_type
from rhosocial.activerecord.backend.impl.snowflake.mixins.column_type import (
    SNOWFLAKE_COLUMN_TYPE_EVIDENCE,
    SNOWFLAKE_COLUMN_TYPES,
    SNOWFLAKE_PROVISIONAL_COLUMN_TYPES,
    SnowflakeColumnTypeMixin,
)
# The shared contract list: the common Python types every backend must answer
# for, in the testsuite's own words, so this file and the contract tests read
# the same list rather than two copies that can drift.
from rhosocial.activerecord.testsuite.feature.query.typed_column.column_helpers import (
    COMMON_TYPES,
    resolve_column_class,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


@pytest.fixture
def table(dialect):
    return dialect.suggested_column_types()


def _table_source():
    """The module source from the table's own leading comment onward.

    The table literal and the group comments attached to it are one block; the
    module docstring and the class around it carry markers of their own, and
    counting those as if they belonged to a cell would make a "one marker per
    group" assertion measure the wrong thing.
    """
    source = inspect.getsource(column_type)
    return source.split("#: Snowflake's full answer", 1)[-1]


# ---------------------------------------------------------------------------
# The protocol: the dialect composes the new mixin and answers through it
# ---------------------------------------------------------------------------


def test_the_dialect_composes_the_column_type_protocol(dialect):
    """The rebuilt protocol, composed and answered.

    ``ColumnTypeMixin`` is the core base (its ``suggested_column_types`` has no
    default and raises when not overridden), ``ColumnTypeSupport`` is the
    ``isinstance`` answer, and the mixin is the Snowflake half. All three have
    to hold for a model's ``Model.c.<field>`` to resolve on this backend.
    """
    assert issubclass(SnowflakeColumnTypeMixin, ColumnTypeMixin)
    assert isinstance(dialect, SnowflakeColumnTypeMixin)
    assert isinstance(dialect, ColumnTypeSupport)


def test_the_table_answers_every_entry_of_the_common_list(table):
    """A hole in the table is a definition-time failure, so it must be a test failure.

    The protocol forbids the answer that looks like an answer by being absent:
    every one of the shared list's entries must be a key, answered with a class
    or with a deliberate ``None``. This asserts the keys match the list
    exactly, in neither direction.
    """
    assert set(table) == set(COMMON_TYPES)
    assert len(COMMON_TYPES) == 18


def test_no_entry_is_refused(dialect, table):
    """Snowflake answers every entry with a column class.

    ``None`` is how the rebuilt protocol says "this backend genuinely has no
    column for this value family", and it is a last resort that has to carry
    its reason where the entry is written. Snowflake has no such entry:
    VARIANT carries a document and a native ILIKE carries a case-insensitive
    match, so every entry has somewhere to go. A future edit that answers
    ``None`` has to change this test on purpose, which is the point -- the gap
    becomes a declaration rather than a silent omission.
    """
    refused = [key for key, value in table.items() if value is None]
    assert refused == []
    assert all(value is not None for value in table.values())


def test_every_answer_is_a_column_class(table):
    """Each value must be a ``ColumnBase`` subclass, or resolution cannot build it."""
    for key, value in table.items():
        assert isinstance(value, type) and issubclass(value, ColumnBase), key


def test_the_dialect_resolves_every_entry_to_the_table_answer(dialect, table):
    """What a model builds is what this dialect's table says.

    The selection step is the model layer's own (the testsuite's
    ``resolve_column_class`` helper), which replaced the protocol's deleted
    ``column_class_for``. Table-relative on purpose: the answer may
    legitimately differ from another backend's (``list`` is a document here
    and a native array on PostgreSQL), and what may not differ is the model
    and the table disagreeing.
    """
    for entry in COMMON_TYPES:
        assert resolve_column_class(dialect, entry) is table[entry], entry


def test_the_table_is_a_copy_so_a_caller_cannot_corrupt_it(dialect):
    """Mutating the returned table must not change later resolutions."""
    first = dialect.suggested_column_types()
    first[int] = StringColumn
    assert dialect.suggested_column_types()[int] is IntegerColumn
    assert SNOWFLAKE_COLUMN_TYPES[int] is IntegerColumn


def test_the_backend_offers_no_extra_types(dialect):
    """The extras table is empty: Snowflake has no Python type of its own to add.

    The rebuilt protocol's second table exists for a backend's own vocabulary
    (a ``Point``, a ``complex``); the default is ``{}`` and that is the honest
    answer here. An entry added later would be a new vocabulary item and
    belongs in this test deliberately.
    """
    assert dialect.suggested_extra_column_types() == {}


# ---------------------------------------------------------------------------
# The per-entry answers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "annotation, expected",
    [
        (bool, BooleanColumn),
        (int, IntegerColumn),
        (float, NumericColumn),
        (decimal.Decimal, NumericColumn),
        (str, StringColumn),
        (bytes, BinaryColumn),
        (bytearray, BinaryColumn),
        (datetime.date, DateTimeColumn),
        (datetime.time, DateTimeColumn),
        (datetime.datetime, DateTimeColumn),
        (datetime.timedelta, NumericColumn),
        (uuid.UUID, UUIDColumn),
        (dict, JSONColumn),
        (list, JSONColumn),
        (tuple, JSONColumn),
        (set, JSONColumn),
        (frozenset, JSONColumn),
        (enum.Enum, StringColumn),
    ],
    ids=lambda v: getattr(v, "__name__", str(v)),
)
def test_the_documented_answer_per_entry(dialect, annotation, expected):
    """Each entry's answer, asserted one at a time so a change names the cell.

    ``float`` and ``decimal.Decimal`` both answering ``NumericColumn`` is the
    rebuilt core's doing, not a Snowflake finding: the numeric families were
    collapsed into one class because arithmetic on them is the same operation
    family, and the precision difference lives in the DDL layer's
    ``DataType``. See the group-2 comment in the mixin.

    ``timedelta -> NumericColumn`` is the one that reads like a mistake and is
    not: Snowflake *does* document twelve storable interval data types, but core
    declares no interval column class and Snowflake's interval storage is barred
    from VARIANT, clustered, dynamic and Iceberg tables, so it is not the
    portable default. See the group-5 comment in the mixin.

    ``date``/``time`` answering ``DateTimeColumn`` is likewise a core gap (no
    ``DateColumn``/``TimeColumn`` yet), not a claim that Snowflake conflates them
    -- it has three distinct ``TIMESTAMP_*`` types.
    """
    assert dialect.suggested_column_types()[annotation] is expected


def test_uuid_is_answered_the_same_on_both_sides_of_the_10_2_gate(dialect):
    """The native ``UUID`` type arrived in 10.2; the column answer did not change.

    ``UUIDColumn`` carries no UUID-specific operator -- portable SQL has none --
    so the version gate is a DDL spelling (``SNOWFLAKE_UUID_TYPE_MIN_VERSION``)
    and must not branch this table. A dialect that narrowed it below 10.2 would
    be refusing an operation that works on every version.
    """
    old = SnowflakeDialect(version=(10, 1, 0))
    new = SnowflakeDialect(version=(10, 2, 0))
    assert old.suggested_column_types()[uuid.UUID] is UUIDColumn
    assert new.suggested_column_types()[uuid.UUID] is UUIDColumn


# ---------------------------------------------------------------------------
# The provisional cells (议题 B: VARIANT / OBJECT / ARRAY)
# ---------------------------------------------------------------------------


def test_the_provisional_cells_are_the_five_semi_structured_entries():
    """The 🔶 cells are ``dict`` plus the four sequence types.

    Exported as a constant so the marking is checkable rather than only prose.
    """
    assert set(SNOWFLAKE_PROVISIONAL_COLUMN_TYPES) == {
        dict,
        list,
        tuple,
        set,
        frozenset,
    }


def test_the_provisional_cells_all_answer_json_column(dialect):
    """Document route for both a mapping and a sequence, pending 议题 B.

    Snowflake's ``ARRAY`` is a real type with a real function family, so this is
    not "Snowflake cannot do arrays" -- it is that ``dict`` and ``list`` both
    land inside one ``VARIANT`` document, which is the backend's parse choice,
    and 议题 B has not yet decided whether core should carry the three
    semi-structured concepts separately.
    """
    table = dialect.suggested_column_types()
    for entry in SNOWFLAKE_PROVISIONAL_COLUMN_TYPES:
        assert table[entry] is JSONColumn, entry


def test_list_is_not_answered_as_an_array_column(table):
    """The one cell that would contradict the current decision, pinned.

    ``ArrayColumn`` would say Snowflake's array surface is offered by default.
    It is not -- not until 议题 B, and not while core's ``ArrayColumn``
    operations render ``ARRAY_LENGTH``/``UNNEST``, which this server spells
    ``ARRAY_SIZE``/``FLATTEN``. The explicit
    ``UseColumnType(ArrayColumn)`` escape hatch remains available and is what a
    caller should reach for in the meantime.
    """
    assert table[list] is not ArrayColumn


def test_the_provisional_cells_are_documented_as_provisional():
    """The marking lives in the mixin's own prose, so the prose is what is checked.

    There is no machine-readable flag on a table entry, which is exactly why the
    provisional set is a separate exported constant -- and why this test asserts
    the source still says so. A later edit that silently reclassified a cell
    without a decision would have to delete or reword all of it.
    """
    source = _table_source()
    assert "PROVISIONAL" in source
    assert "议题 B" in source
    for entry in SNOWFLAKE_PROVISIONAL_COLUMN_TYPES:
        name = entry.__name__
        assert f"{name}: JSONColumn" in source, name


def test_the_three_semi_structured_types_are_described_as_distinct():
    """The mixin must state that VARIANT/OBJECT/ARRAY are three server types.

    This backend parses all three to one concept, and the docstrings have to say
    that the docs treat them as distinct -- otherwise a reader would take the
    parse choice for a statement about Snowflake. It is a design trade-off
    (议题 B), not a limitation the documentation imposes.
    """
    module_source = inspect.getsource(column_type)
    assert "three distinct server types" in module_source
    assert "data-types-semistructured" in module_source


# ---------------------------------------------------------------------------
# Evidence level: every entry is marked docs-only
# ---------------------------------------------------------------------------


def test_the_evidence_level_is_stated_once_and_is_docs_pending_cloud():
    """The table's evidence level is a value, not a sentence buried in a docstring.

    Exported as a constant so this test can assert it, and so that a later
    cloud-verified pass has one place to change.
    """
    assert SNOWFLAKE_COLUMN_TYPE_EVIDENCE == "文档（待云验）"


def test_every_entry_group_carries_the_marker_and_a_doc_url():
    """Each group in the table names the page it was read from, and marks 待云验.

    A citation that is present in the module docstring but absent from a group
    would let a reader believe a whole cell on the strength of an unrelated
    page, so the marker and at least one ``docs.snowflake.com`` URL are
    required *inside* the table body.
    """
    table_body = _table_source()
    assert table_body.count("文档（待云验）") == 9, "one marker per entry group"
    assert table_body.count("https://docs.snowflake.com/") == 9


def test_the_provisional_marker_appears_on_both_semi_structured_groups():
    """The 🔶 cells are marked where they are written, not only in the preamble."""
    table_body = _table_source()
    assert table_body.count("PROVISIONAL") >= 2
    assert "Group 7" in table_body
    assert "Group 8" in table_body
