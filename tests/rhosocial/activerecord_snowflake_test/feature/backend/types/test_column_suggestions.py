# tests/rhosocial/activerecord_snowflake_test/feature/backend/types/test_column_suggestions.py
"""Snowflake's column-type suggestion table, and the capability narrowing it declares.

Everything asserted here is **文档（待云验）**: the table was built from
Snowflake's official documentation, and no Snowflake instance was reachable
while it was written. These tests therefore check that the backend *says* what
it means, and that the two provisional cells stay visibly provisional -- they
cannot check that a server agrees, which is what the cloud probe is for.
"""
import datetime
import decimal
import enum
import inspect
import uuid

import pytest

from rhosocial.activerecord.backend.expression.column_suggestions import (
    COLUMN_TYPE_ENTRIES,
    UNSUPPORTED,
)
from rhosocial.activerecord.backend.expression.column_types import (
    BinaryColumn,
    BooleanColumn,
    ColumnBase,
    DateTimeColumn,
    DecimalColumn,
    FloatColumn,
    IntegerColumn,
    JSONColumn,
    NumericColumn,
    StringColumn,
    UUIDColumn,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.mixins import column_suggestion
from rhosocial.activerecord.backend.impl.snowflake.mixins.column_suggestion import (
    SNOWFLAKE_COLUMN_SUGGESTION_EVIDENCE,
    SNOWFLAKE_PROVISIONAL_COLUMN_SUGGESTIONS,
    SnowflakeColumnSuggestionMixin,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


@pytest.fixture
def table(dialect):
    return dialect.suggested_column_types()


def _class_source():
    """The mixin's own source, with the capability method's text removed.

    ``COLUMN_TYPE_SUGGESTIONS`` and its group comments are one block; the
    ``supports_column_operation`` docstring below them carries markers of its
    own, and counting those as if they belonged to a cell would make a
    "one marker per group" assertion measure the wrong thing.
    """
    source = inspect.getsource(SnowflakeColumnSuggestionMixin)
    return source.split("def supports_column_operation", 1)[0]


def _table_source():
    """The table literal and the group comments attached to it.

    Group 1's comment sits above the attribute rather than inside the literal,
    so the split starts at the class docstring's end rather than at the
    attribute's name.
    """
    return _class_source().split('"""', 2)[-1]


# ---------------------------------------------------------------------------
# Completeness: every entry of the closed core list is answered
# ---------------------------------------------------------------------------


def test_the_table_answers_every_entry_of_the_closed_list(table):
    """A hole in the table is a definition-time failure, so it must be a test failure.

    The protocol forbids both answers that look like an answer: leaving an entry
    out and answering ``None``. So this asserts the keys match the core list
    exactly, in neither direction.
    """
    assert set(table) == set(COLUMN_TYPE_ENTRIES)
    assert len(COLUMN_TYPE_ENTRIES) == 18


def test_no_entry_is_unsupported(dialect, table):
    """Snowflake answers every entry with a column class.

    ``UNSUPPORTED`` is how a backend says "this entry has no column class here",
    and it exists for backends with real gaps (Firebird has no JSON functions
    at all). Snowflake has none: VARIANT carries a document and ILIKE carries
    a case-insensitive match, so every entry has somewhere to go. A future edit
    that introduces ``UNSUPPORTED`` has to change this test on purpose, which is
    the point -- the gap becomes a declaration rather than a silent omission.
    """
    refused = [key for key, value in table.items() if value is UNSUPPORTED]
    assert refused == []
    assert all(value is not None for value in table.values())


def test_every_answer_is_a_column_class(table):
    """Each value must be a ``ColumnBase`` subclass, or resolution cannot build it."""
    for key, value in table.items():
        assert isinstance(value, type) and issubclass(value, ColumnBase), key


def test_the_dialect_resolves_every_entry_to_the_table_answer(dialect, table):
    """What a model builds is what this dialect's table says.

    Table-relative on purpose: the answer may legitimately differ from another
    backend's (``list`` is a document here and a native array on PostgreSQL),
    and what may not differ is the model and the table disagreeing.
    """
    for entry in COLUMN_TYPE_ENTRIES:
        assert dialect.column_class_for(entry) is table[entry], entry


def test_the_table_is_a_copy_so_a_caller_cannot_corrupt_it(dialect):
    """Mutating the returned table must not change later resolutions."""
    first = dialect.suggested_column_types()
    first[int] = StringColumn
    assert dialect.suggested_column_types()[int] is IntegerColumn
    assert SnowflakeColumnSuggestionMixin.COLUMN_TYPE_SUGGESTIONS[int] is IntegerColumn


# ---------------------------------------------------------------------------
# The per-entry answers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "annotation, expected",
    [
        (bool, BooleanColumn),
        (int, IntegerColumn),
        (float, FloatColumn),
        (decimal.Decimal, DecimalColumn),
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
# The two provisional cells (议题 B: VARIANT / OBJECT / ARRAY)
# ---------------------------------------------------------------------------


def test_the_provisional_cells_are_the_five_semi_structured_entries():
    """The 🔶 cells are ``dict`` plus the four sequence types.

    Exported as a constant so the marking is checkable rather than only prose.
    """
    assert set(SNOWFLAKE_PROVISIONAL_COLUMN_SUGGESTIONS) == {
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
    for entry in SNOWFLAKE_PROVISIONAL_COLUMN_SUGGESTIONS:
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
    from rhosocial.activerecord.backend.expression.column_types import ArrayColumn

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
    for entry in SNOWFLAKE_PROVISIONAL_COLUMN_SUGGESTIONS:
        name = entry.__name__
        assert f"{name}: JSONColumn" in source, name


def test_the_three_semi_structured_types_are_described_as_distinct():
    """The mixin must state that VARIANT/OBJECT/ARRAY are three server types.

    This backend parses all three to one concept, and the docstrings have to say
    that the docs treat them as distinct -- otherwise a reader would take the
    parse choice for a statement about Snowflake. It is a design trade-off
    (议题 B), not a limitation the documentation imposes.
    """
    module_source = inspect.getsource(column_suggestion)
    assert "three distinct server types" in module_source
    assert "data-types-semistructured" in module_source


# ---------------------------------------------------------------------------
# Capability narrowing: docs-only, and it narrows nothing
# ---------------------------------------------------------------------------


def test_ilike_is_not_narrowed(dialect):
    """Snowflake has a native ``[ NOT ] ILIKE``, so narrowing it would be wrong.

    Five of the ten backends synthesise ``LOWER(x) LIKE LOWER(y)`` and pay for
    it; this one has the operator, with its own ``ESCAPE`` clause. Narrowing
    would refuse a query that works, which is the direction the protocol says
    not to be wrong in.
    """
    assert dialect.supports_column_operation("StringColumn", "ilike") is True
    assert dialect.supports_ilike() is True


def test_the_json_path_operations_are_not_narrowed(dialect):
    """``GET_PATH`` and ``:`` take a VARIANT/OBJECT/ARRAY column, so both path
    operations are available on a ``JSONColumn`` here."""
    assert dialect.supports_column_operation("JSONColumn", "json_path") is True
    assert dialect.supports_column_operation("JSONColumn", "json_value") is True
    assert dialect.supports_json_operations() is True


def test_nothing_is_narrowed_on_this_backend(dialect):
    """A docs-only pass found nothing to narrow; this pins that verdict.

    Not an aspiration -- a statement about the documentation read. If a later
    pass cites a page saying an operation does not exist, this test is where the
    narrowing is added deliberately, with its evidence.
    """
    pairs = [
        ("StringColumn", op)
        for op in ("like", "ilike", "concat", "lower", "upper", "length", "substr")
    ] + [
        ("IntegerColumn", op) for op in ("__add__", "__sub__", "__mul__")
    ] + [("JSONColumn", op) for op in ("json_path", "json_value", "cast")]
    for column_name, op in pairs:
        assert dialect.supports_column_operation(column_name, op) is True, (column_name, op)


def test_the_open_array_operation_probe_is_recorded_rather_than_guessed():
    """``ARRAY_LENGTH``/``UNNEST`` are left unanswered, and that is written down.

    Core's ``ArrayColumn`` renders those two names; Snowflake documents
    ``ARRAY_SIZE`` and the ``FLATTEN`` table function, and neither name appears
    in its function index. Absence from an index is not proof of absence, and
    the protocol requires narrowing to be backed by a real server -- so the
    probe is recorded as 待云验 rather than answered. This test keeps the record
    from being lost.
    """
    source = inspect.getsource(SnowflakeColumnSuggestionMixin.supports_column_operation)
    assert "ARRAY_SIZE" in source
    assert "FLATTEN" in source
    assert "ARRAY_LENGTH" in source


# ---------------------------------------------------------------------------
# Evidence level: every entry is marked docs-only
# ---------------------------------------------------------------------------


def test_the_evidence_level_is_stated_once_and_is_docs_pending_cloud():
    """The table's evidence level is a value, not a sentence buried in a docstring.

    Exported as a constant so this test can assert it, and so that a later
    cloud-verified pass has one place to change.
    """
    assert SNOWFLAKE_COLUMN_SUGGESTION_EVIDENCE == "文档（待云验）"


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