# src/rhosocial/activerecord/backend/impl/snowflake/expression/types.py
"""Snowflake-specific DataType subclass definitions.

Snowflake data types per official documentation:
https://docs.snowflake.com/en/sql-reference/data-types

Key Snowflake types:
- VARCHAR / STRING / TEXT / VARCHAR2 / NVARCHAR
- CHAR / CHARACTER / NCHAR  (synonymous with VARCHAR; default length CHAR(1))
- NUMBER / DECIMAL / DEC / NUMERIC
- INT / INTEGER / BIGINT / SMALLINT / TINYINT / BYTEINT (all NUMBER(38, 0))
- FLOAT / FLOAT4 / FLOAT8 / DOUBLE / DOUBLE PRECISION / REAL (all 64-bit)
- BOOLEAN
- DATE
- TIME
- TIMESTAMP / TIMESTAMP_LTZ / TIMESTAMP_NTZ / TIMESTAMP_TZ
- BINARY / VARBINARY (synonymous with one another)
- VARIANT
- OBJECT
- ARRAY
- GEOGRAPHY
- GEOMETRY
- UUID (server release 10.2 and newer; :class:`SnowflakeUuidType`)

What is deliberately **not** here, because Snowflake has no such type:
``INTERVAL`` (a time span is a ``NUMBER`` of units chosen per call), ``XML``
(``PARSE_XML()`` yields an ``OBJECT``), ``JSONB`` (one ``VARIANT`` serves
both), ``BINARY(n)``-vs-``VARBINARY(n)`` (``BINARY`` and ``VARBINARY`` are the
same type), and a ``REAL`` that stores 4 bytes (Snowflake's ``REAL`` is its
64-bit ``FLOAT``).  The core concepts that have no Snowflake counterpart are
named in
:meth:`~...mixins.types.SnowflakeTypeSupportMixin.suggested_data_types`
rather than being faked with a formatter.

One class here is **conditional**: :class:`SnowflakeUuidType` renders the
native ``UUID`` that arrived in server release 10.2, so the dialect refuses it
below that and keeps substituting ``VARCHAR`` there — see
``SNOWFLAKE_UUID_TYPE_MIN_VERSION`` and the formatter.

Inheritance
-----------
Every class here has **exactly one** base.  Inheritance in this codebase means
*identity* — "this class **is** that SQL type" — not "this class belongs to that
family".  So ``SnowflakeVarcharType`` derives from ``VarCharType`` because a
Snowflake ``VARCHAR`` **is** a variable-length character string, and
``SnowflakeGeographyType`` sits directly on ``DataType`` because a spatial type
is not a kind of any core concept.  There are no family/grouping nodes to
inherit from, no mixins, and no diamond edges: rendering never happens on a
type either, it goes ``DataType.to_sql()`` →
``dialect.format_data_type(self)`` → ``format_data_type_<name>``.
"""
from typing import Any, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.serialization import ExpressionRegistry
from rhosocial.activerecord.backend.expression.types._base import DataType
from rhosocial.activerecord.backend.expression.types.integer import IntegerType
from rhosocial.activerecord.backend.expression.types.string import VarCharType
from rhosocial.activerecord.backend.expression.types.numeric import DecimalType, FloatType
from rhosocial.activerecord.backend.expression.types.boolean import BooleanType
from rhosocial.activerecord.backend.expression.types.binary import BlobType
from rhosocial.activerecord.backend.expression.types.datetime_ import DateType, TimeType, TimestampType
from rhosocial.activerecord.backend.expression.types.json_ import JsonType
from rhosocial.activerecord.backend.expression.types.array import ArrayType
from rhosocial.activerecord.backend.expression.types.uuid_ import UUIDType

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


# ========== String Types ==========

class SnowflakeVarcharType(VarCharType):
    """Snowflake ``VARCHAR`` — variable-length UTF-8 character string.

    Base: :class:`VarCharType`.  Snowflake's ``VARCHAR`` **is** the
    variable-length character string; the manual lists ``STRING``, ``TEXT``,
    ``VARCHAR2`` and ``NVARCHAR`` as synonyms of it rather than as a different
    storage.  The only Snowflake-specific facts are that the default maximum
    length is 16,777,216 characters and that the limit is 134,217,728 *bytes*
    for multi-byte characters — a per-column maximum, not a type.

    This class exists for the namespaced dispatch key (``snowflake_varchar``)
    and because it is the backend-owned spelling a model declares; the SQL it
    produces is the same ``VARCHAR(n)`` the core type produces.
    """

    PARAMETERS = ("length",)

    name = "snowflake_varchar"

    def __init__(self, dialect=None, *, length: Optional[int] = None):
        super().__init__(dialect, length=length)


# ========== Numeric Types ==========

class SnowflakeNumberType(DecimalType):
    """Snowflake ``NUMBER`` — exact fixed-point, ``NUMBER(p, s)``.

    Base: :class:`DecimalType`.  The manual states that ``DECIMAL``, ``DEC`` and
    ``NUMERIC`` are *synonymous* with ``NUMBER``: same storage, same exact
    arithmetic, same rounding.  A ``NUMBER`` is therefore a ``DecimalType``
    under a different name, not a different type.

    What is Snowflake's is the ceiling: at most 38 significant digits and a
    maximum scale of 37, checked by
    :meth:`~...mixins.types.SnowflakeTypeSupportMixin._validate_number_precision`
    at render time.

    ``scale`` is part of this type's identity — core puts it in ``PARAMETERS`` —
    and Snowflake's ``NUMBER(precision, scale)`` really does take one, so it is
    rendered and never discarded.  The one thing Snowflake has no spelling for
    is a scale without a precision, so that combination is refused; see
    :meth:`~...mixins.types.SnowflakeTypeSupportMixin._format_number`.
    https://docs.snowflake.com/en/sql-reference/data-types-numeric

    **``unsigned`` is carried and refused here, not inherited-by-accident.**
    Core's :class:`DecimalType` puts ``unsigned`` in its ``PARAMETERS`` and
    validates it, so this class has always had the *attribute*; what it did not
    have is the field in its own identity or a way to set it, because the
    ``__init__`` below narrows the parent's signature.  Narrowing is the right
    answer for ``spelling`` — Snowflake does not write ``numeric``, ``dec`` or
    ``numeric(10, 2)`` as anything but ``NUMBER`` — but narrowing a field that
    core declares as identity is the opposite: it leaves one column reachable
    through two names, one of which answers "no" to an unsigned request and the
    other of which cannot even be asked.  ``unsigned`` is therefore declared
    here too, in the same position core puts it (appended, after ``precision``
    and ``scale``), and refused by
    :meth:`~...mixins.types.SnowflakeTypeSupportMixin._refuse_unsigned_numeric`
    for the same reason core's ``decimal`` is — Snowflake's numeric inventory
    has no unsigned row and its column grammar has no modifier after the type
    name.
    """

    PARAMETERS = ("precision", "scale", "unsigned",)

    name = "snowflake_number"

    def __init__(self, dialect=None, *, precision: Optional[int] = None,
                 scale: Optional[int] = None, unsigned: bool = False):
        super().__init__(dialect, precision=precision, scale=scale,
                         unsigned=unsigned)


class SnowflakeFloatType(FloatType):
    """Snowflake ``FLOAT`` — 64-bit IEEE 754 approximate numeric.

    Base: :class:`FloatType`.  A Snowflake ``FLOAT`` is a precision-bearing
    approximate numeric (``FLOAT(p)``, where ``p`` counts *binary* digits), so
    that is the concept it is.  ``FLOAT4`` and ``FLOAT8`` are documented as
    names for compatibility with other systems that Snowflake treats as the same
    64-bit type — a compatibility alias, not a different width, which is why
    they are not separate classes.

    Snowflake always stores 64 bits; ``precision`` is a declaration of how much
    of that the caller intends to use, and the accepted range is 1-126 binary
    digits.

    **``unsigned`` is carried and refused here for the reason given on
    :class:`SnowflakeNumberType`**: it is the same storage as core's ``float``
    and core's ``float`` refuses the flag, so leaving it off this class's
    identity would give one Snowflake column one answer through ``float`` and a
    different one through ``snowflake_float``.  ``spelling`` is *not* carried:
    Snowflake writes ``FLOAT`` and never ``FLOAT4`` or ``FLOAT8`` as a column
    type of its own, and neither is a field of the concept.
    """

    PARAMETERS = ("precision", "unsigned",)

    name = "snowflake_float"

    def __init__(self, dialect=None, *, precision: Optional[int] = None,
                 unsigned: bool = False):
        super().__init__(dialect, precision=precision, unsigned=unsigned)


# ========== Boolean Type ==========

class SnowflakeBooleanType(BooleanType):
    """Snowflake ``BOOLEAN`` — SQL three-valued logic.

    Base: :class:`BooleanType`.  Identical storage and identical semantics
    (``TRUE`` / ``FALSE`` / ``NULL``); ``BOOL`` is only a spelling.
    """

    name = "snowflake_boolean"


# ========== Timestamp Variants ==========

class SnowflakeTimestampLtzType(TimestampType):
    """Snowflake ``TIMESTAMP_LTZ`` — stored UTC, rendered in the session zone.

    Base: :class:`TimestampType`.  All three Snowflake timestamp types carry a
    date and a time of day, which is exactly what ``TimestampType`` means, and
    they differ from each other only in *how the offset is handled*, not in what
    is stored in the value's own fields.  So they are three subclasses of one
    concept rather than three spellings of it: the words differ **because the
    behaviour differs**, which is the test that decides whether two names are
    synonyms.

    ``TIMESTAMP_LTZ`` normalises to UTC on the way in and converts to the
    session time zone on the way out, so two sessions read the same row
    differently.  ``TIMESTAMP_NTZ`` (below) never converts; ``TIMESTAMP_TZ``
    (below) keeps the offset with the value.
    """

    PARAMETERS = ("precision",)

    name = "snowflake_timestamp_ltz"

    def __init__(self, dialect=None, *, precision: Optional[int] = None):
        super().__init__(dialect, precision=precision)


class SnowflakeTimestampNtzType(TimestampType):
    """Snowflake ``TIMESTAMP_NTZ`` — no time zone, stored and read as written.

    Base: :class:`TimestampType`, for the reason given on
    :class:`SnowflakeTimestampLtzType`.  The distinguishing fact is the
    absence of any zone handling: a ``TIMESTAMP_NTZ`` value is stored and
    displayed exactly as written, so it does not change meaning when the
    session time zone does.
    """

    PARAMETERS = ("precision",)

    name = "snowflake_timestamp_ntz"

    def __init__(self, dialect=None, *, precision: Optional[int] = None):
        super().__init__(dialect, precision=precision)


class SnowflakeTimestampTzType(TimestampType):
    """Snowflake ``TIMESTAMP_TZ`` — the UTC offset is stored with the value.

    Base: :class:`TimestampType`, for the reason given on
    :class:`SnowflakeTimestampLtzType`: the value's own fields are a date and a
    time, and what separates the three Snowflake types is offset handling, not
    the shape of the timestamp.  Deriving from core ``TimestampTzType`` instead
    would claim this is the ANSI ``TIMESTAMP WITH TIME ZONE`` type, which is
    not what ``TIMESTAMP_TZ`` is — Snowflake spells and stores it its own way,
    and this dialect renders that word.

    Here the offset travels with the value, so the column reads back the same
    instant it was written regardless of the session time zone.
    """

    PARAMETERS = ("precision",)

    name = "snowflake_timestamp_tz"

    def __init__(self, dialect=None, *, precision: Optional[int] = None):
        super().__init__(dialect, precision=precision)


# ========== Date & Time ==========

class SnowflakeDateType(DateType):
    """Snowflake ``DATE`` — year, month, day, with no time and no time zone.

    Base: :class:`DateType`.  Snowflake's ``DATE`` has no time part at all, so
    there is nothing about it that a core ``DateType`` does not already mean.
    """

    name = "snowflake_date"


class SnowflakeTimeType(TimeType):
    """Snowflake ``TIME`` — time of day with optional fractional seconds.

    Base: :class:`TimeType`.  Snowflake has no ``TIME WITH TIME ZONE``, so its
    ``TIME`` is precisely the standard's zone-less time of day; ``precision``
    (0-9) is the number of fractional-second digits kept.
    """

    PARAMETERS = ("precision",)

    name = "snowflake_time"

    def __init__(self, dialect=None, *, precision: Optional[int] = None):
        super().__init__(dialect, precision=precision)


# ========== Binary ==========

class SnowflakeBinaryType(BlobType):
    """Snowflake ``BINARY`` (a.k.a. ``VARBINARY``) — a sequence of bytes.

    Base: :class:`BlobType`.  The manual states that ``VARBINARY`` is
    *synonymous with* ``BINARY``: one type, two words, up to 67,108,864 bytes
    with a default maximum of 8,388,608.  There is no fixed-length versus
    variable-length binary pair on this backend, because there is only one
    binary type — which is why core ``BinaryType``/``VarBinaryType`` are
    *substituted* rather than rendered (see ``suggested_data_types()``).

    The optional ``length`` is Snowflake's own: ``BINARY(n)`` declares the
    maximum number of bytes and defaults to 8,388,608.  It is kept in
    ``PARAMETERS`` because two ``SnowflakeBinaryType`` columns with different
    maximum lengths are not the same column.
    """

    name = "snowflake_blob"

    length: Optional[int] = None

    def __init__(self, dialect=None, *, length: Optional[int] = None):
        super().__init__(dialect=dialect)
        self.length = length

    PARAMETERS = ("length",)

# ========== UUID ==========

class SnowflakeUuidType(UUIDType):
    """Snowflake ``UUID`` — natively stored, and read back as 36 characters.

    Base: :class:`UUIDType`.  Snowflake added the type in server release **10.2**
    (Jan 26-30, 2026): "This release adds support for the UUID data type. The
    UUID data type stores universally unique identifiers (UUIDs)."
    https://docs.snowflake.com/en/release-notes/2026/10_2

    A Snowflake ``UUID`` **is** the concept, not a stand-in for it, and the
    storage is the reason it was worth adding: the reference page says "The UUID
    data type stores universally unique identifiers (UUIDs). **A UUID is a
    128-bit binary value** that uniquely identifies information", where the
    character storage this backend used before is 36 bytes per value and
    unbounded in what it accepts.
    https://docs.snowflake.com/en/sql-reference/data-types-uuid

    What is *not* different is the text form on the way out, and that is worth
    being precise about because it decides what a driver sees: the same page says
    "Snowflake drivers treat UUID values as text strings", "UUID values are in
    UUID format, which is a 36-character string of hexadecimal digits, separated
    by hyphens, in the pattern 8-4-4-4-12", and "UUID values are case-insensitive"
    — and its worked example selects a ``UUID DEFAULT UUID_STRING()`` column and
    shows ``f353ca91-4fc5-49f2-9b9e-304f83d11914``.  So a UUID column reads back
    as the same 36 characters a ``VARCHAR`` would have held, which is exactly why
    substituting one was never *visibly* wrong; what was wrong was the storage
    underneath it, and that is what 10.2 changed.  Compare the type's own
    limitation list, which is where the practical difference shows up: the type
    "isn't supported in stored procedures or user-defined functions (UDFs)
    written in a language other than SQL, in Python or Java", "isn't supported in
    hybrid tables" and "isn't supported in Snowpark", none of which a ``VARCHAR``
    column was subject to.

    **Gated on the server version.**  There is no ``UUID`` word in a release
    before 10.2 — the type page and the summary table both simply do not list it
    before then — so the formatter refuses below 10.2 rather than writing DDL the
    server will reject, and :meth:`~...mixins.types.SnowflakeTypeSupportMixin.
    suggested_data_types` keeps pointing the core ``uuid`` concept at ``VARCHAR``
    there.  Above 10.2 the suggestion points here instead.
    https://docs.snowflake.com/en/sql-reference/intro-summary-data-types

    No parameters: the syntax is ``<column_name> UUID``, with no length, no
    precision and no scale to declare, so ``PARAMETERS`` stays empty and two of
    these are always the same column.
    """

    name = "snowflake_uuid"

# ========== Semi-Structured Types ==========

class SnowflakeVariantType(JsonType):
    """Snowflake ``VARIANT`` — the universal semi-structured type.

    Base: :class:`JsonType`.  A ``VARIANT`` holds a JSON / Avro / ORC / Parquet
    document addressed by path, which is what ``JsonType`` models — the manual
    names JSON first among the formats it accepts.  What makes it Snowflake's is
    that it is *one* column type for all of them: the format is chosen by the
    value, not by the column, and the access path is
    ``GET``/``GET_PATH``/``:`` rather than a JSON operator.

    ``SnowflakeObjectType`` below is the same base for a different reason: an
    ``OBJECT`` is a *structured* key-value value with a fixed key set, so it is
    a sibling here, not a subclass of this one.
    """

    name = "snowflake_variant"


class SnowflakeObjectType(JsonType):
    """Snowflake ``OBJECT`` — a structured key-value value.

    Base: :class:`JsonType`.  An ``OBJECT`` holds a document addressed the same
    semi-structured way (dot and bracket notation, ``GET``, ``GET_PATH``), which
    is the identity ``JsonType`` states.  Snowflake draws the line at *how the
    keys are decided*: the semi-structured ``OBJECT`` has no declared key set,
    and it is this dialect's ``SnowflakeObjectType`` — not a subclass of
    ``SnowflakeVariantType`` — that stands for both, because a structured
    ``OBJECT(k V, ...)`` is the same expression rendered as ``OBJECT``.
    """

    name = "snowflake_object"


class SnowflakeArrayType(ArrayType):
    """Snowflake ``ARRAY`` — an ordered sequence of same-typed elements.

    Base: :class:`ArrayType`.  An ``ARRAY`` is exactly the array container: an
    ordered sequence whose elements share one type.  What it is *not* is a
    parameterised ``T[]``: a bare Snowflake ``ARRAY`` column is the
    semi-structured form, whose elements are ``VARIANT`` and whose element type
    is declared nowhere — the structured form spells it ``ARRAY(NUMBER)`` and is
    a different thing.  This class therefore renders the untyped word ``ARRAY``
    and its ``element_type`` records nothing the server knows; that is also why
    core ``ArrayType`` is *substituted* rather than rendered here.

    Equality compares the element type rather than the element instance, so two
    arrays of the same element type are equal however their defaults were
    built, and ``dimensions`` is ignored for the same reason — it is the axis
    Snowflake's ``ARRAY`` does not have.
    """

    name = "snowflake_array"

    def __init__(self, dialect=None, *, element_type: Optional[DataType] = None):
        super().__init__(dialect, element_type=element_type or IntegerType())
        # Recorded as its own field so the identity declaration below is a
        # plain attribute read. What distinguishes two Snowflake ARRAY columns
        # is *which kind* of element they hold, not the element's own
        # parameters: an ARRAY of VARCHAR(10) and one of VARCHAR(20) are the
        # same column to Snowflake, so declaring ``element_type`` here would
        # report a change the server does not have.
        self.element_type_class = type(self.element_type)

    PARAMETERS = ("element_type_class",)


# ========== Geospatial Types ==========

class SnowflakeGeographyType(DataType):
    """Snowflake ``GEOGRAPHY`` — Earth-surface coordinates (WGS 84 lat/long).

    Deliberately **not** derived from a core concept.  SQL:2016 has no spatial
    types at all, and there is nothing in the core hierarchy this could
    truthfully be a kind of: the value is a geodetic coordinate pair interpreted
    on the WGS 84 spheroid, and it is neither a number, a string, nor a
    structured document.  Deriving from ``DataType`` directly says "the
    framework models no concept here", which is the honest statement; deriving
    from ``JsonType`` or ``DataType``-as-a-string would say "geography is a kind
    of JSON", which is false.
    """

    name = "snowflake_geography"


class SnowflakeGeometryType(DataType):
    """Snowflake ``GEOMETRY`` — planar (flat-earth) Cartesian coordinates.

    Deliberately **not** derived from a core concept, for the reason given on
    :class:`SnowflakeGeographyType`: SQL:2016 has no spatial types.  It is kept
    separate from ``GEOGRAPHY`` rather than made a subclass of it because the
    two disagree about the datum — ``GEOMETRY`` measures straight lines on a
    plane and ``GEOGRAPHY`` on the WGS 84 spheroid — so the same coordinates
    mean different distances in the two types.  That is a storage property of
    the value, not a labelling preference.
    """

    name = "snowflake_geometry"


class SnowflakeUserDefinedType(DataType):
    """Reference to a Snowflake schema-level user-defined type.

    A UDT is a named type created by ``CREATE TYPE`` and referenced by name, so
    its namespace is the shared one: *database_name* is the catalog slot and
    *schema_name* the schema slot. The slots are validated while rendering
    rather than here -- building the shared
    :class:`~rhosocial.activerecord.backend.expression.objects.Type` rejects a
    blank slot, and the dialect rejects a database with no schema -- so this
    class only records what the caller asked for.

    Deliberately not derived from a core concept: core has no "named type"
    reference. It is neither an object nor a variant -- a UDT carries a field
    list and no base type, whereas Snowflake's ``OBJECT`` and ``VARIANT`` are
    semi-structured runtime values, so inheriting from ``JsonType`` would claim
    the UDT is a kind of document and it is not.
    
    """

    name = "snowflake_user_defined"

    def __init__(
        self,
        dialect: Optional["SQLDialectBase"] = None,
        *,
        type_name: str,
        schema_name: Optional[str] = None,
        database_name: Optional[str] = None,
    ) -> None:
        super().__init__(dialect)
        self.type_name = type_name
        self.schema_name = schema_name
        self.database_name = database_name

    PARAMETERS = ("database_name", "schema_name", "type_name",)

_SNOWFLAKE_DATA_TYPES = (
    SnowflakeVarcharType,
    SnowflakeNumberType,
    SnowflakeFloatType,
    SnowflakeBooleanType,
    SnowflakeTimestampLtzType,
    SnowflakeTimestampNtzType,
    SnowflakeTimestampTzType,
    SnowflakeDateType,
    SnowflakeTimeType,
    SnowflakeBinaryType,
    SnowflakeUuidType,
    SnowflakeVariantType,
    SnowflakeObjectType,
    SnowflakeArrayType,
    SnowflakeGeographyType,
    SnowflakeGeometryType,
    SnowflakeUserDefinedType,
)
for _data_type in _SNOWFLAKE_DATA_TYPES:
    ExpressionRegistry.register(_data_type)