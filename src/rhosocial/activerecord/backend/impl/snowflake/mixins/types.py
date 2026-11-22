# src/rhosocial/activerecord/backend/impl/snowflake/mixins/types.py
"""Snowflake DataType formatting and parsing mixin.

Uses DataTypeMixin naming-convention dispatch for Snowflake-specific type SQL.
"""

from __future__ import annotations

from typing import Optional, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.ddl_type import DataTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DataTypeSupport
# Aliased because this module also uses ``Type[DataType]``-style annotations
# from ``typing``; ``TypeObject`` names the schema object a UDT reference is.
from rhosocial.activerecord.backend.expression.objects import Type as TypeObject
from rhosocial.activerecord.backend.expression.types import (
    BigIntType,
    BlobType,
    BooleanType,
    CharType,
    CustomType,
    DataType,
    DateType,
    DateTimeType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    JsonType,
    RealType,
    SmallIntType,
    TextType,
    TimeType,
    TimeTzType,
    TimestampType,
    TimestampTzType,
    TinyIntType,
    VarCharType,
)
from ..expression.types import (
    SnowflakeArrayType,
    SnowflakeBinaryType,
    SnowflakeBooleanType,
    SnowflakeDateType,
    SnowflakeFloatType,
    SnowflakeGeographyType,
    SnowflakeGeometryType,
    SnowflakeNumberType,
    SnowflakeObjectType,
    SnowflakeTimeType,
    SnowflakeTimestampLtzType,
    SnowflakeTimestampNtzType,
    SnowflakeTimestampTzType,
    SnowflakeUserDefinedType,
    SnowflakeUuidType,
    SnowflakeVariantType,
    SnowflakeVarcharType,
)
from rhosocial.activerecord.backend.suggestion.definitions import SubstituteTypeSuggestion
from .ddl_type import SNOWFLAKE_TYPE_DDL_MIN_VERSION


#: First Snowflake server release with a native ``UUID`` column type.  The 10.2
#: release notes announce it under "SQL updates": "New UUID data type — This
#: release adds support for the UUID data type. The UUID data type stores
#: universally unique identifiers (UUIDs)."
#: https://docs.snowflake.com/en/release-notes/2026/10_2
#:
#: The entry carries no "(Preview)" and no "(General availability)" marker —
#: the OneLake announcement in the same release is marked "(*General
#: availability*)" — so the release notes do not label this one either way.  The
#: type reference page documents it as an ordinary column type with no preview
#: banner, and the summary-of-data-types table lists ``UUID`` alongside every
#: other type, which is what this gate rests on.
#: https://docs.snowflake.com/en/sql-reference/data-types-uuid
#: https://docs.snowflake.com/en/sql-reference/intro-summary-data-types
SNOWFLAKE_UUID_TYPE_MIN_VERSION = (10, 2, 0)


class SnowflakeTypeSupportMixin(DataTypeMixin, DataTypeSupport):
    """Snowflake DataType formatting and parsing.

    Implements ``DataTypeSupport`` so the dialect can render ``DataType``
    expressions to SQL strings and parse raw SQL type strings back into
    ``DataType`` instances.

    Formatting dispatches by the type instance's ``name`` through the
    naming-convention ``format_data_type_<name>`` methods (see
    ``DataTypeMixin``). Snowflake-specific types carry ``snowflake_``-prefixed
    names; core types render their real Snowflake SQL.
    """

    # Snowflake precision limits
    _SNOW_NUMBER_PRECISION_MAX = 38
    #: "The *maximum scale*, which is the number of digits to the right of the
    #: decimal point, is 37."  Note this is 37, not 38: a NUMBER holds 38 digits
    #: in total and at least one of them is to the left of the point, which is
    #: why the scale ceiling is one below the precision ceiling.
    #: https://docs.snowflake.com/en/sql-reference/data-types-numeric
    _SNOW_NUMBER_SCALE_MAX = 37
    #: "By default, precision is 38, and scale is 0; that is, NUMBER(38, 0)."
    #: The manual's own words, and ``DESC TABLE`` renders a bare ``NUMBER`` and an
    #: explicit ``NUMBER(38, 0)`` identically -- so on Snowflake the two spellings
    #: are one column, not two.  https://docs.snowflake.com/en/sql-reference/data-types-numeric
    _SNOW_NUMBER_DEFAULT_PRECISION = 38
    _SNOW_NUMBER_DEFAULT_SCALE = 0
    _SNOW_FLOAT_PRECISION_MAX = 126  # binary precision
    _SNOW_TIMESTAMP_PRECISION_MAX = 9  # fractional seconds
    _SNOW_TIME_PRECISION_MAX = 9  # fractional seconds

    #: "If no length is specified, the default is 16777216." — Snowflake's own
    #: reference for ``VARCHAR``, and the summary table repeats it: "Default
    #: length is 16777216 bytes. Maximum length is 134217728 bytes."
    #: https://docs.snowflake.com/en/sql-reference/data-types-text
    _SNOW_VARCHAR_DEFAULT_LENGTH = 16777216
    #: "``CHAR``, ``CHARACTER`` — Synonymous with ``VARCHAR``, except the default
    #: length is ``VARCHAR(1)``."  Same page, same table.  Worth noting what that
    #: sentence does *not* say: Snowflake's ``CHAR`` is not blank-padded the way
    #: SQL's is, which is why :meth:`format_data_type_char` writes ``CHAR(1)``
    #: rather than ``VARCHAR(1)`` and why padding plays no part here.
    _SNOW_CHAR_DEFAULT_LENGTH = 1

    def supports_data_type_snowflake_user_defined(self) -> bool:
        version = getattr(self, "version", None)
        if version is None:
            return False
        try:
            return tuple(version) >= SNOWFLAKE_TYPE_DDL_MIN_VERSION
        except TypeError:
            return False

    def supports_data_type_snowflake_uuid(self) -> bool:
        """Whether a native ``UUID`` column can be declared.

        False below Snowflake 10.2, which has no such type — the numeric, string,
        binary, logical, date/time, semi-structured, structured, geospatial and
        user-defined entries in the manual's own inventory all predate it and
        ``UUID`` is simply absent.  Declaring the gate separately from the
        formatter is what lets
        :meth:`format_data_type_snowflake_uuid` refuse with a version in the
        message instead of writing DDL the server will reject.
        """
        version = getattr(self, "version", None)
        if version is None:
            return False
        try:
            return tuple(version) >= SNOWFLAKE_UUID_TYPE_MIN_VERSION
        except TypeError:
            return False

    def _validate_number_precision(self, precision: int, scale: int = 0) -> None:
        if not 1 <= precision <= self._SNOW_NUMBER_PRECISION_MAX:
            raise ValueError(
                f"Snowflake NUMBER precision must be 1-{self._SNOW_NUMBER_PRECISION_MAX}, "
                f"got {precision}"
            )
        if not 0 <= scale <= self._SNOW_NUMBER_SCALE_MAX:
            raise ValueError(
                f"Snowflake NUMBER scale must be 0-{self._SNOW_NUMBER_SCALE_MAX}, "
                f"got {scale}"
            )

    def _format_number(
        self,
        precision: Optional[int],
        scale: Optional[int],
    ) -> Tuple[str, tuple]:
        """Render ``NUMBER``, honouring both halves of ``NUMBER(p, s)``.

        One implementation for the core ``decimal`` concept and this dialect's own
        ``snowflake_number`` type, because the manual makes them one type:
        "DECIMAL, DEC, NUMERIC — Synonymous with NUMBER."  Two copies of this
        would be two places for the two halves of the syntax to disagree.

        The documented syntax is ``NUMBER [ ( precision [, scale] ) ]`` — the
        manual's own example creates ``num0 NUMBER`` and ``num10 NUMBER(10,1)``
        side by side, and the defaults are given as "By default, precision is 38,
        and scale is 0; that is, NUMBER(38, 0)".
        https://docs.snowflake.com/en/sql-reference/data-types-numeric

        So the scale **is** part of the type and it is written out whenever it is
        declared.  ``scale`` is in ``PARAMETERS``, which is to say it is part of
        this type's identity: two declarations differing only in it are two
        different columns, and this backend can and does distinguish them, because
        the manual says scale changes the storage ("the same value stored in a
        column of type NUMBER(10,5) consumes more space than NUMBER(5,0)").

        The one thing that cannot be written is a scale with no precision.  The
        grammar puts the scale *inside* the parenthesis as the optional second
        argument — ``NUMBER( precision [, scale] )``, and the default precision
        (38) belongs to a bare ``NUMBER`` or a ``NUMBER(p)``, not to a scale on
        its own.  So ``SnowflakeNumberType(scale=2)`` used to render a bare
        ``NUMBER`` and report success: a column that keeps zero fractional digits,
        for a declaration that asked for two, on a type whose equality had just
        said the two are different columns.  That is the silent-drop this
        replaces, so the combination is refused and the message names the field.

        The refusal below fires whenever a precision was not declared, because
        core no longer resolves type parameters from the dialect: writing a
        bare ``NUMBER`` on the caller's behalf would decide a precision this
        framework does not know the server has.  A caller that wants
        ``NUMBER(38, 2)`` declares ``precision=38`` explicitly, on the manual's
        own statement that the default precision is 38.
        """
        if scale is not None and precision is None:
            raise ValueError(
                f"Snowflake NUMBER cannot declare scale={scale} without a "
                f"precision: the documented syntax is NUMBER [ ( precision [, "
                f"scale] ) ], so the scale is the optional second argument inside "
                f"the parenthesis and there is no NUMBER(scale) form (an absent "
                f"precision means the bare NUMBER, i.e. NUMBER(38, 0)). Declare "
                f"precision={self._SNOW_NUMBER_PRECISION_MAX} explicitly to get "
                f"NUMBER({self._SNOW_NUMBER_PRECISION_MAX}, {scale})."
            )
        if precision is not None:
            self._validate_number_precision(precision, scale or 0)
        if precision is not None and scale is not None:
            return f"NUMBER({precision}, {scale})", ()
        if precision is not None:
            return f"NUMBER({precision})", ()
        return "NUMBER", ()

    def _validate_float_precision(self, precision: int) -> None:
        if not 1 <= precision <= self._SNOW_FLOAT_PRECISION_MAX:
            raise ValueError(
                f"Snowflake FLOAT precision (binary) must be 1-{self._SNOW_FLOAT_PRECISION_MAX}, "
                f"got {precision}"
            )

    def _validate_timestamp_precision(self, precision: int) -> None:
        if not 0 <= precision <= self._SNOW_TIMESTAMP_PRECISION_MAX:
            raise ValueError(
                f"Snowflake TIMESTAMP fractional seconds precision must be "
                f"0-{self._SNOW_TIMESTAMP_PRECISION_MAX}, got {precision}"
            )

    def _validate_time_precision(self, precision: int) -> None:
        if not 0 <= precision <= self._SNOW_TIME_PRECISION_MAX:
            raise ValueError(
                f"Snowflake TIME fractional seconds precision must be "
                f"0-{self._SNOW_TIME_PRECISION_MAX}, got {precision}"
            )

    # ------------------------------------------------------------------
    # DataTypeSupport — formatting (core types)
    # ------------------------------------------------------------------

    def _refuse_unsigned_integer(
        self,
        expr: "TinyIntType | SmallIntType | IntegerType | BigIntType",
        snowflake_word: str,
    ) -> None:
        """Refuse ``unsigned=True``, because Snowflake has no unsigned integer.

        The core integer concepts carry signedness as a field rather than as a
        class, so ``TinyIntType(unsigned=True)`` is constructible and the flag
        reaches the formatter.  Every one of the four widths has to do something
        honest with it, and this backend's honest answer is a refusal, because
        the manual's integer inventory contains no unsigned entry at all:

        * "INT, INTEGER, BIGINT, SMALLINT, TINYINT, BYTEINT — Synonymous with
          NUMBER, except precision and scale can't be specified" and, in full,
          "for all INTEGER data types, the range of values is all integer values
          from -99999999999999999999999999999999999999 to
          +99999999999999999999999999999999999999 (inclusive)".  A single
          symmetric range for every width: signedness is not a property
          Snowflake's integer storage has, which is also why the names are there
          "to simplify porting from other systems and to suggest the expected
          range of values" rather than to enforce one.
          https://docs.snowflake.com/en/sql-reference/data-types-numeric
        * The summary table that enumerates every numeric type Snowflake has —
          NUMBER, DECIMAL/NUMERIC, the six integer names, FLOAT/FLOAT4/FLOAT8,
          DOUBLE/DOUBLE PRECISION/REAL, DECFLOAT — has no unsigned row.
          https://docs.snowflake.com/en/sql-reference/intro-summary-data-types
        * The column grammar takes ``<col_name> <col_type>`` and then only
          ``GENERATED``/``inlineConstraint``/``NOT NULL``/``COLLATE``/
          ``DEFAULT``/``AUTOINCREMENT``/policies/``TAG``/``COMMENT`` — there is
          no ``UNSIGNED`` attribute to write after the type name either, so
          there is not even a spelling that would parse.
          https://docs.snowflake.com/en/sql-reference/sql/create-table
        * The manual says so outright where an unsigned type would otherwise
          seem possible: unsigned integer types are on the list of Parquet
          features "that aren't supported" for Delta-sourced tables.
          https://docs.snowflake.com/en/user-guide/tables-iceberg-data-types

        So the answer is uniform across all four widths — none of them has an
        unsigned form — and the four formatters each say so rather than writing
        the signed column out.  Emitting a bare ``TINYINT``/``SMALLINT``/
        ``INTEGER``/``BIGINT`` for an unsigned request would create a column
        that accepts the negatives the caller declared that it would not, and
        report success: the same silent data loss as accepting the flag and
        discarding it, which is what this replaces.

        The signed range does cover every width's unsigned range, so nothing is
        lost by dropping the *concept* on this backend; what would be lost is
        the caller's statement that these particular columns hold no negative
        value, and that belongs in a ``CHECK`` constraint.

        The shape check comes first because this method is the **only** place
        that sees the field: the expression's constructor collects ``unsigned``
        without judging it — only the formatter knows which backend has to honour
        it — so a non-boolean reaches here instead of being rejected at
        construction.  A truth test cannot see it: ``unsigned=0``,
        ``unsigned=""`` and ``unsigned=None`` are all falsy, so they would sail
        past the test below, render a signed column and report success, which is
        the same silent loss this method exists to prevent.  Naming the shape is
        what a truth test cannot do.
        """
        unsigned = expr.unsigned
        if not isinstance(unsigned, bool):
            raise TypeError(
                f"unsigned must be a bool, got {type(unsigned).__name__}; it "
                f"becomes a type modifier in the rendered DDL."
            )
        if not unsigned:
            return
        raise UnsupportedFeatureError(
            self.name,
            f"an unsigned {snowflake_word} column "
            f"(Snowflake has no unsigned integer type; {snowflake_word} is "
            f"NUMBER(38, 0) and nothing else)",
            suggestion=(
                "Declare the column signed and enforce the range with a CHECK "
                "constraint if negatives must be rejected."
            ),
        )

    def _refuse_unsigned_numeric(
        self,
        expr: "FloatType | RealType | DoubleType | DecimalType",
        snowflake_word: str,
    ) -> None:
        """Refuse ``unsigned=True`` on ``NUMBER``, ``FLOAT`` or ``DOUBLE``.

        The same field reaches the four exact/approximate numeric concepts that
        it reaches the four integer widths — ``DecimalType``, ``FloatType``,
        ``DoubleType`` and ``RealType`` each carry ``unsigned`` in
        ``PARAMETERS``, so two declarations differing only in it are different
        columns as far as the schema differ is concerned — and Snowflake's answer
        is the same refusal as :meth:`_refuse_unsigned_integer`, for the same
        underlying reason stated at more length here, because this family has
        *two* documented spellings per concept and the signedness has to be absent
        from both:

        * **The manual's inventory of every numeric type Snowflake has** —
          ``NUMBER``, ``DECIMAL``/``NUMERIC``, the six integer names,
          ``FLOAT``/``FLOAT4``/``FLOAT8``, ``DOUBLE``/``DOUBLE PRECISION``/
          ``REAL``, ``DECFLOAT`` — **has no unsigned row.**  A closed table is
          what turns an absence into evidence rather than a gap.
          https://docs.snowflake.com/en/sql-reference/intro-summary-data-types
        * **The manual says so outright where an unsigned type would otherwise
          seem possible.**  Unsigned integer types are on the list of Parquet
          features "that aren't supported" for Delta-sourced tables — and note
          *integer*: the sentence is about a whole family that Snowflake does not
          have unsigned members of, not about one type that happens to lack one.
          https://docs.snowflake.com/en/user-guide/tables-iceberg-data-types
        * **There is no attribute slot to write it in.**  The column grammar is
          ``<col_name> <col_type>`` and then only ``GENERATED`` /
          ``inlineConstraint`` / ``NOT NULL`` / ``COLLATE`` / ``DEFAULT`` /
          ``AUTOINCREMENT`` / access and masking policies / ``TAG`` / ``COMMENT``
          — nothing that is a modifier *of the type*.  So there is not even a
          spelling that would parse, which is the strongest form of the answer:
          the backend is not choosing to ignore the flag, it could not write it.
          https://docs.snowflake.com/en/sql-reference/sql/create-table

        Writing a bare ``NUMBER`` / ``FLOAT`` / ``DOUBLE`` for an unsigned request
        would create a column that accepts the negatives the caller declared it
        would not, and report success: the same silent loss as accepting the flag
        and discarding it, which is what this replaces.

        **Which classes need this, and which do not** — the honest answer, since
        ``unsigned`` reaches Snowflake through two different class hierarchies
        and the field has to be answered on both:

        * ``DecimalType``, ``FloatType``, ``DoubleType`` and ``RealType`` — core's
          concepts — get the field from core, keep it in ``PARAMETERS``, and call
          this method.  These are the four the schema guard names.
        * :class:`~...expression.types.SnowflakeNumberType` and
          :class:`~...expression.types.SnowflakeFloatType` are **Snowflake's own
          classes for the same two storages under Snowflake's own words**, each
          with its own ``__init__``.  They are **not** covered by the core-concept
          refusal: ``format_data_type_snowflake_number`` and
          ``format_data_type_snowflake_float`` are separate dispatch keys with
          separate formatters, so the core refusal is not on their path at all.
          Leaving them without the field would mean the *same column* — Snowflake
          ``NUMBER``, which the manual makes one type with ``DECIMAL`` — could be
          refused through one name and silently written signed through the other.
          So they declare the field themselves and refuse it here too.  See their
          own docstrings for why that is a second door and not a second concept.

        ``UnsupportedFeatureError``, not ``ValueError``: this is a declaration the
        grammar cannot express at all rather than a wrong value, and the two
        exceptions do not share a base class.  This runs **before**
        ``_check_spelling`` and before every precision and scale check, so a
        request wrong in two ways is told about the signedness first — that one
        is a stronger and less recoverable statement than a misspelled word or an
        out-of-range number.  Every one of those existing checks still fires
        unchanged for a signed declaration, which is what
        ``test_snowflake_type_protocol.py`` pins.

        The shape check is first for the reason given in
        :meth:`_refuse_unsigned_integer`, and it matters **twice** over here
        because this is the gate for two class hierarchies: a non-boolean
        reaches the formatter unjudged (the constructors collect ``unsigned``
        without validating it), and a falsy one — ``0``, ``""``, ``None``, an
        empty container — is invisible to the truth test that follows, so it
        would render a signed ``NUMBER`` / ``FLOAT`` / ``DOUBLE`` and report
        success whether it arrived through ``DecimalType`` or through
        :class:`~...expression.types.SnowflakeNumberType`.
        """
        unsigned = expr.unsigned
        if not isinstance(unsigned, bool):
            raise TypeError(
                f"unsigned must be a bool, got {type(unsigned).__name__}; it "
                f"becomes a type modifier in the rendered DDL."
            )
        if not unsigned:
            return
        raise UnsupportedFeatureError(
            self.name,
            f"an unsigned {snowflake_word} column "
            f"(Snowflake has no unsigned numeric type: the summary table of "
            f"every numeric data type it has -- NUMBER, DECIMAL/NUMERIC, the "
            f"six integer names, FLOAT/FLOAT4/FLOAT8, DOUBLE/DOUBLE "
            f"PRECISION/REAL, DECFLOAT -- has no unsigned row, unsigned "
            f"integers are on the manual's own list of Parquet features that "
            f"aren't supported, and the column grammar leaves no modifier "
            f"after <col_type> in which UNSIGNED could go)",
            suggestion=(
                "Declare the column signed and enforce the range with a CHECK "
                "constraint if negatives must be rejected."
            ),
        )

    def format_data_type_integer(self, expr: IntegerType) -> Tuple[str, tuple]:
        """``INT`` and ``INTEGER`` are both Snowflake's words for the same
        ``NUMBER(38, 0)``, so both are accepted and the concept is rendered
        under Snowflake's canonical spelling rather than the one requested.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_integer`, which is also where the reason for
        the refusal is written down.
        """
        self._check_spelling(expr, IntegerType)
        self._refuse_unsigned_integer(expr, "INTEGER")
        return "INTEGER", ()

    def format_data_type_tinyint(self, expr: TinyIntType) -> Tuple[str, tuple]:
        """Snowflake writes ``TINYINT``.

        ``TINYINT`` is one of the five integer names the manual lists as
        *synonymous with NUMBER*: precision and scale cannot be specified and
        the column is ``NUMBER(38, 0)``, exactly as ``INTEGER``, ``BIGINT``,
        ``SMALLINT`` and ``BYTEINT`` are.  So the word is accepted — Snowflake
        writes it back, and refusing the concept's own default spelling would
        leave ``TinyIntType`` unusable here — but the column is **not** eight
        bits wide.  The manual says as much: the various integer names exist
        "to simplify porting from other systems and to suggest the expected
        range of values", not to enforce one.  A caller who needs the range
        enforced has to say so with a ``CHECK`` constraint; the name alone does
        not.

        ``INT1`` is refused because Snowflake has no such word.

        ``unsigned`` is refused as well; see :meth:`_refuse_unsigned_integer`.
        """
        self._check_spelling(expr, ("tinyint",))
        self._refuse_unsigned_integer(expr, "TINYINT")
        return "TINYINT", ()

    def format_data_type_bigint(self, expr: BigIntType) -> Tuple[str, tuple]:
        """Both spellings are accepted; Snowflake writes ``BIGINT`` and stores
        ``NUMBER(38, 0)``.

        ``unsigned`` is refused; see :meth:`_refuse_unsigned_integer`.
        """
        self._check_spelling(expr, BigIntType)
        self._refuse_unsigned_integer(expr, "BIGINT")
        return "BIGINT", ()

    def format_data_type_smallint(self, expr: SmallIntType) -> Tuple[str, tuple]:
        """Both spellings are accepted; Snowflake writes ``SMALLINT`` and stores
        ``NUMBER(38, 0)`` — a ``SMALLINT`` column here is no narrower than an
        ``INTEGER`` one, for the reason given on
        :meth:`format_data_type_tinyint`.

        ``unsigned`` is refused; see :meth:`_refuse_unsigned_integer`.
        """
        self._check_spelling(expr, SmallIntType)
        self._refuse_unsigned_integer(expr, "SMALLINT")
        return "SMALLINT", ()

    def format_data_type_float(self, expr: FloatType) -> Tuple[str, tuple]:
        """``FLOAT(p)`` counts binary digits on Snowflake, not decimal ones.

        ``unsigned`` is refused rather than ignored, before the precision check;
        see :meth:`_refuse_unsigned_numeric`."""
        self._refuse_unsigned_numeric(expr, "FLOAT")
        if expr.precision is not None:
            self._validate_float_precision(expr.precision)
            return f"FLOAT({expr.precision})", ()
        return "FLOAT", ()

    def format_data_type_real(self, expr: RealType) -> Tuple[str, tuple]:
        """Snowflake has no 4-byte float.

        The manual lists ``REAL`` under "``DOUBLE``, ``DOUBLE PRECISION``,
        ``REAL`` — Synonymous with FLOAT", and ``FLOAT`` is 64-bit IEEE 754.
        So the word is accepted (Snowflake writes it and will report a ``REAL``
        column back as ``FLOAT``) but the column is **not** a 24-bit mantissa:
        it is the same 64 bits as ``FLOAT`` and ``DOUBLE``, and this is the one
        concept of the three whose storage Snowflake cannot narrow.  Nothing is
        silently rewritten — the requested spelling is what appears in the DDL.

        ``unsigned`` is refused rather than ignored; see
        :meth:`_refuse_unsigned_numeric`.  It is the same storage as
        ``FLOAT`` and ``DOUBLE`` and there is no more room for the attribute
        here than in either of them.
        """
        self._refuse_unsigned_numeric(expr, "REAL")
        return "REAL", ()

    def format_data_type_double(self, expr: DoubleType) -> Tuple[str, tuple]:
        """Both spellings are accepted.  Snowflake stores the 64-bit value either
        way; ``DOUBLE`` is the shorter of its two words and what this dialect
        has always rendered.

        ``unsigned`` is refused rather than ignored, **before** the spelling
        check; see :meth:`_refuse_unsigned_numeric`."""
        self._refuse_unsigned_numeric(expr, "DOUBLE")
        self._check_spelling(expr, DoubleType)
        return "DOUBLE", ()

    def format_data_type_decimal(self, expr: DecimalType) -> Tuple[str, tuple]:
        """``DECIMAL``, ``DEC`` and ``NUMERIC`` are documented as synonymous
        with ``NUMBER``, so all three are accepted and the column is rendered
        as ``NUMBER`` with Snowflake's 38-digit / 37-scale limits applied.

        The precision and scale are handed to :meth:`_format_number`, which owns
        both halves of the ``NUMBER(p, s)`` syntax: it renders a declared scale,
        and refuses one declared without a precision.

        ``unsigned`` is refused rather than ignored, **before** ``_check_spelling``
        and before :meth:`_format_number`'s "scale without a precision" refusal
        and its two range checks; see :meth:`_refuse_unsigned_numeric`.  All three
        of those still fire unchanged for a signed declaration."""
        self._refuse_unsigned_numeric(expr, "NUMBER")
        self._check_spelling(expr, DecimalType)
        return self._format_number(expr.precision, expr.scale)

    def format_data_type_boolean(self, expr: BooleanType) -> Tuple[str, tuple]:
        """``BOOL`` is a Snowflake-accepted spelling of ``BOOLEAN``, so both
        render as ``BOOLEAN``."""
        self._check_spelling(expr, BooleanType)
        return "BOOLEAN", ()

    def format_data_type_varchar(self, expr: VarCharType) -> Tuple[str, tuple]:
        """Both spellings render ``VARCHAR``; a declared width is written out.

        ``CHARACTER VARYING`` is SQL's own long form and not one of the words
        the Snowflake manual lists (it lists ``STRING``, ``TEXT``,
        ``VARCHAR2``, ``NVARCHAR`` and ``CHAR VARYING``), but it names the same
        variable-length string and refusing it would refuse the spelling the
        backend's introspection parser produces for that word, which would
        make the round trip lossy in the wrong direction.  Snowflake's own
        word is what gets written.

        An undeclared width stays undeclared in the SQL: the type carries no
        length and the server applies its documented default of 16777216.
        Type-parameter default resolution was removed from core; a caller that
        needs the width in the declaration writes it explicitly.  Reading a
        catalog spelling back into a ``DataType`` is the job of the
        introspection-only ``SnowflakeTypeParser``.
        """
        self._check_spelling(expr, VarCharType)
        if expr.length is not None:
            return f"VARCHAR({expr.length})", ()
        return "VARCHAR", ()

    def format_data_type_char(self, expr: CharType) -> Tuple[str, tuple]:
        """``CHARACTER`` is documented by Snowflake as a synonym of ``CHAR``, so
        both are accepted; the rendered length is Snowflake's own default of
        ``CHAR(1)`` when none was declared.

        The formatter substitutes that default because core no longer resolves
        type parameters from the dialect.  The manual's "except the default
        length is ``VARCHAR(1)``" is what that 1 is.
        """
        self._check_spelling(expr, CharType)
        return (f"CHAR({expr.length})" if expr.length is not None else "CHAR(1)"), ()

    def format_data_type_text(self, expr: TextType) -> Tuple[str, tuple]:
        """Both spellings render ``VARCHAR(16777216)``.

        ``TEXT`` is a documented Snowflake synonym of ``VARCHAR`` and 16,777,216
        is Snowflake's default maximum length, so unbounded text is exactly a
        ``VARCHAR`` written out at its default.  ``CLOB`` is not a Snowflake
        word, but it is the concept's second spelling and both denote the same
        unbounded string, so it is accepted and normalised rather than refused.
        """
        self._check_spelling(expr, TextType)
        return "VARCHAR(16777216)", ()

    def format_data_type_blob(self, expr: BlobType) -> Tuple[str, tuple]:
        """Both spellings render ``BINARY``.

        ``BINARY`` is Snowflake's own name for byte storage and ``VARBINARY``
        is documented as synonymous with it; ``BYTEA`` is PostgreSQL's word for
        the same bytes.  Refusing ``BLOB`` would refuse the concept's default
        spelling, which is the one every plain ``BlobType(dialect)`` carries,
        so the spelling is normalised instead.
        """
        self._check_spelling(expr, BlobType)
        return "BINARY", ()

    def format_data_type_datetime(self, expr: DateTimeType) -> Tuple[str, tuple]:
        """Snowflake has no ``DATETIME`` type; the zone-less timestamp is
        ``TIMESTAMP_NTZ``, and the default precision is 9 fractional-second
        digits."""
        return "TIMESTAMP_NTZ", ()

    def format_data_type_date(self, expr: DateType) -> Tuple[str, tuple]:
        return "DATE", ()

    def format_data_type_time(self, expr: TimeType) -> Tuple[str, tuple]:
        if expr.precision is not None:
            self._validate_time_precision(expr.precision)
            return f"TIME({expr.precision})", ()
        return "TIME", ()

    def format_data_type_timetz(self, expr: TimeTzType) -> Tuple[str, tuple]:
        """Snowflake has no ``TIME WITH TIME ZONE``.

        Its ``TIME`` is the standard's zone-less time of day, so the only thing
        this can honestly render is a ``TIME`` — and the fraction is written out
        at Snowflake's maximum of 9 digits when the caller asked for none,
        because ``TIME``'s own default is 0 and dropping the caller's requested
        precision is the one loss that cannot be recovered.  The zone itself has
        nowhere to go: it is a property of the expression that produced the
        value, not of the column.
        """
        if expr.precision is not None:
            self._validate_time_precision(expr.precision)
            return f"TIME({expr.precision})", ()
        return f"TIME({self._SNOW_TIME_PRECISION_MAX})", ()

    def format_data_type_timestamp(self, expr: TimestampType) -> Tuple[str, tuple]:
        """Snowflake's zone-less timestamp is ``TIMESTAMP_NTZ``.  A ``precision``
        is validated but not rendered: Snowflake always keeps 9 fractional-second
        digits and writes ``TIMESTAMP_NTZ(9)`` itself, so echoing a smaller one
        would be a claim the server does not honour."""
        if expr.precision is not None:
            self._validate_timestamp_precision(expr.precision)
        return "TIMESTAMP_NTZ", ()

    def format_data_type_timestamptz(self, expr: TimestampTzType) -> Tuple[str, tuple]:
        """``TIMESTAMP_TZ`` is the Snowflake type that keeps the UTC offset with
        the value, which is what "timestamp with time zone" means here; it is
        also what :class:`SnowflakeTimestampTzType` renders, so the core concept
        and the backend's own type reach the same column.  ``precision`` is
        validated but not written, for the reason given on
        :meth:`format_data_type_timestamp`."""
        if expr.precision is not None:
            self._validate_timestamp_precision(expr.precision)
        return "TIMESTAMP_TZ", ()

    def format_data_type_json(self, expr: JsonType) -> Tuple[str, tuple]:
        """``VARIANT`` is Snowflake's semi-structured type; JSON is the first
        format the manual lists it as accepting."""
        return "VARIANT", ()

    def format_data_type_custom(self, expr: CustomType) -> Tuple[str, tuple]:
        """Write the caller-supplied type name verbatim.

        This is the honest-ignorance escape hatch, and it is what the
        introspection-only parser produces for a name it does not recognise —
        without it the round trip through introspection loses the name it read.  It is
        safe to emit: ``CustomType`` runs the raw string through
        ``validate_type_name`` at construction, so what arrives here is an
        identifier-shaped name and never a fragment of SQL.  A type used often
        enough to deserve a class should be one — then it is rendered through
        the dialect and cannot be wrong.
        """
        return expr.raw, ()

    # --- Snowflake-specific type formatters (dispatch key = type name) ---

    def format_data_type_snowflake_varchar(self, expr: SnowflakeVarcharType) -> Tuple[str, tuple]:
        """Same SQL as the core ``varchar`` renderer — the backend-named type is
        the same concept reached through this dialect's own entry point.  The
        spelling gate is here too rather than only on the core formatter, so
        neither route can be handed a spelling Snowflake does not write.

        This class is not the core ``VarCharType`` and so does not share its
        declaration by inheritance, exactly as
        :class:`~...impl.sqlserver.expression.types.SQLServerNVarCharMaxType` is
        not handed SQL Server's ``VARCHAR`` width merely for deriving from one.
        Core no longer resolves type parameters from the dialect, so an
        undeclared width stays undeclared here too.
        """
        self._check_spelling(expr, VarCharType)
        if expr.length is not None:
            return f"VARCHAR({expr.length})", ()
        return "VARCHAR", ()

    def format_data_type_snowflake_number(self, expr: SnowflakeNumberType) -> Tuple[str, tuple]:
        """Same SQL as the core ``decimal`` renderer, and for the same reason:
        ``DECIMAL``, ``DEC`` and ``NUMERIC`` are documented as synonymous with
        ``NUMBER``, so one concept reaches one column through either name.  The
        precision and the scale both go to :meth:`_format_number` — ``scale`` is
        in ``PARAMETERS``, so it is part of this type's identity and a declared
        one is written out rather than discarded; a scale declared with no
        precision is refused, because Snowflake's grammar has no ``NUMBER(scale)``
        form.

        ``unsigned`` is refused here too, for exactly the reason
        :meth:`format_data_type_decimal` refuses it: this is the *same* Snowflake
        column under the backend's own dispatch key, so a gate on one path and not
        the other would give one column two different answers.  See
        :meth:`_refuse_unsigned_numeric`, which is also where the reasoning about
        the two class hierarchies is written down."""
        self._refuse_unsigned_numeric(expr, "NUMBER")
        self._check_spelling(expr, DecimalType)
        return self._format_number(expr.precision, expr.scale)

    def format_data_type_snowflake_float(self, expr: SnowflakeFloatType) -> Tuple[str, tuple]:
        """Snowflake's own name for the same ``FLOAT`` column core's ``float``
        writes, under its own dispatch key.

        ``unsigned`` is refused rather than ignored, before the precision check —
        see :meth:`_refuse_unsigned_numeric`.  ``spelling`` is not a field of this
        class, so :meth:`_check_spelling` is deliberately **not** called here:
        there is no word on the concept to gate."""
        self._refuse_unsigned_numeric(expr, "FLOAT")
        if expr.precision is not None:
            self._validate_float_precision(expr.precision)
            return f"FLOAT({expr.precision})", ()
        return "FLOAT", ()

    def format_data_type_snowflake_boolean(self, expr: SnowflakeBooleanType) -> Tuple[str, tuple]:
        return "BOOLEAN", ()

    def format_data_type_snowflake_timestamp_ltz(self, expr: SnowflakeTimestampLtzType) -> Tuple[str, tuple]:
        if expr.precision is not None:
            self._validate_timestamp_precision(expr.precision)
            return f"TIMESTAMP_LTZ({expr.precision})", ()
        return "TIMESTAMP_LTZ", ()

    def format_data_type_snowflake_timestamp_ntz(self, expr: SnowflakeTimestampNtzType) -> Tuple[str, tuple]:
        if expr.precision is not None:
            self._validate_timestamp_precision(expr.precision)
            return f"TIMESTAMP_NTZ({expr.precision})", ()
        return "TIMESTAMP_NTZ", ()

    def format_data_type_snowflake_timestamp_tz(self, expr: SnowflakeTimestampTzType) -> Tuple[str, tuple]:
        if expr.precision is not None:
            self._validate_timestamp_precision(expr.precision)
            return f"TIMESTAMP_TZ({expr.precision})", ()
        return "TIMESTAMP_TZ", ()

    def format_data_type_snowflake_date(self, expr: SnowflakeDateType) -> Tuple[str, tuple]:
        return "DATE", ()

    def format_data_type_snowflake_time(self, expr: SnowflakeTimeType) -> Tuple[str, tuple]:
        if expr.precision is not None:
            self._validate_time_precision(expr.precision)
            return f"TIME({expr.precision})", ()
        return "TIME", ()

    def format_data_type_snowflake_blob(self, expr: SnowflakeBinaryType) -> Tuple[str, tuple]:
        """``BINARY(n)`` states the maximum byte count; without one, Snowflake's
        default of 8,388,608 applies and is left implicit."""
        self._check_spelling(expr, ("blob",))
        if expr.length is not None:
            return f"BINARY({expr.length})", ()
        return "BINARY", ()

    def format_data_type_snowflake_variant(self, expr: SnowflakeVariantType) -> Tuple[str, tuple]:
        return "VARIANT", ()

    def format_data_type_snowflake_object(self, expr: SnowflakeObjectType) -> Tuple[str, tuple]:
        return "OBJECT", ()

    def format_data_type_snowflake_array(self, expr: SnowflakeArrayType) -> Tuple[str, tuple]:
        return "ARRAY", ()

    def format_data_type_snowflake_uuid(
        self,
        expr: SnowflakeUuidType,
    ) -> Tuple[str, tuple]:
        """``<column_name> UUID`` — the type's whole grammar, verbatim.

        No length, no precision, no scale: the manual gives the syntax as exactly
        that one line, and :class:`SnowflakeUuidType` accordingly declares no
        ``PARAMETERS``, so there is nothing here to render and nothing here to
        drop.  https://docs.snowflake.com/en/sql-reference/data-types-uuid

        The refusal below 10.2 is version-gated rather than absent, and the gate
        is the point: writing the word anyway would hand the server a type name it
        has never heard of and report success, and *not writing it* would refuse
        the backend's own type for no stated reason.  So the message says which
        release the type arrived in.
        """
        if not self.supports_data_type_snowflake_uuid():
            raise UnsupportedFeatureError(
                self.name,
                "a native UUID column",
                suggestion=(
                    "Snowflake's UUID data type requires server version 10.2 or "
                    "newer (released Jan 26-30, 2026). On an older server declare "
                    "the column as VarCharType, which is what this dialect "
                    "suggests for the uuid concept there."
                ),
            )
        return "UUID", ()

    def format_data_type_snowflake_user_defined(
        self,
        expr: SnowflakeUserDefinedType,
    ) -> Tuple[str, tuple]:
        if not self.supports_data_type_snowflake_user_defined():
            raise UnsupportedFeatureError(
                self.name,
                "user-defined type references",
                suggestion="Snowflake user-defined types require server version 10.8 or newer.",
            )
        # A UDT reference names the same kind of object the TYPE DDL creates,
        # so it goes through the shared renderer as a ``Type`` rather than
        # being joined by hand here.
        type_sql, _params = TypeObject(
            self,
            expr.type_name,
            catalog_name=expr.database_name,
            schema_name=expr.schema_name,
        ).to_sql()
        return type_sql, ()

    def format_data_type_snowflake_geography(self, expr: SnowflakeGeographyType) -> Tuple[str, tuple]:
        return "GEOGRAPHY", ()

    def format_data_type_snowflake_geometry(self, expr: SnowflakeGeometryType) -> Tuple[str, tuple]:
        return "GEOMETRY", ()

    def suggest_substitute_types(self) -> SubstituteTypeSuggestion:
        """Core types Snowflake stores some other way.

        Snowflake's numeric, string, binary, boolean, date/time and
        semi-structured concepts all have renderers of their own, so what is
        listed here is only what the dialect **genuinely has no type for** — and
        for each one, what it stores instead.  Silence would leave a caller who
        asks for one of these told "unsupported" and nothing more.

        ``array``
            Snowflake has an ``ARRAY`` type, but not core's array *container*.
            A bare Snowflake ``ARRAY`` column is the semi-structured form: its
            elements are ``VARIANT`` and their type is declared nowhere
            (``ARRAY`` reports back as ``ARRAY``, not ``ARRAY(NUMBER)``).  The
            structured form does declare an element type, and it is a different
            thing.  The suggestion is therefore Snowflake's own array.

        ``binary`` / ``varbinary``
            Snowflake has **one** byte-string type.  ``VARBINARY`` is documented
            as synonymous with ``BINARY``, so there is no fixed-length versus
            variable-length pair to preserve and no declared maximum that is
            part of the type's identity — a ``BINARY(16)`` maximum is enforced
            by the column, not by a distinct type.  The substitute is the byte
            storage this backend does have.

        ``interval``
            Snowflake has no ``INTERVAL`` type.  A time span is a ``NUMBER`` of
            units, and the unit is an argument to the function that computes the
            difference (``DATEDIFF``'s ``date_or_time_part``) rather than a
            property of a column, so the field list core's ``IntervalType``
            carries has nowhere to live.  The substitute is the exact numeric
            the value actually is.

        ``jsonb``
            Snowflake has one semi-structured type.  ``VARIANT`` serves both JSON
            documents and the binary-JSON case without a second storage, so the
            distinction has nothing to be stored in.

        ``uuid``
            **Depends on the server version.**  Snowflake added a native
            ``UUID`` data type in server release 10.2 (Jan 26-30, 2026) — "This
            release adds support for the UUID data type. The UUID data type
            stores universally unique identifiers (UUIDs)."
            https://docs.snowflake.com/en/release-notes/2026/10_2 — so from
            10.2 on, the substitute is :class:`SnowflakeUuidType`, which renders
            the real ``UUID``.  The concept stays *substituted* rather than
            rendered on both sides of that line, because the core ``uuid`` name
            itself is not a Snowflake word on either side of it; what changes is
            which storage the substitution names.

            Below 10.2 the substitute is unchanged from what this backend has
            always suggested: ``VARCHAR``, because a UUID there is a
            36-character string and ``TO_VARCHAR``/``TRY_TO_UUID`` are functions
            rather than a column type.  Note that the *value* looks identical on
            both sides — the reference page says "Snowflake drivers treat UUID
            values as text strings" and shows a ``UUID`` column selecting as
            ``f353ca91-4fc5-49f2-9b9e-304f83d11914`` — so the substitution was
            never visibly wrong at the application boundary; the storage
            underneath it was ("A UUID is a 128-bit binary value").
            https://docs.snowflake.com/en/sql-reference/data-types-uuid

        ``xml``
            Snowflake has no XML type either.  The manual is explicit that
            ``PARSE_XML`` returns an ``OBJECT`` — "the returned value is OBJECT.
            The OBJECT contains an internal representation of the XML" — so an
            XML document is stored as a structured ``OBJECT``, not as the text
            it was parsed from.  (Core's ``XmlType`` docstring table records
            ``TEXT``/``VARIANT`` for this backend; that disagrees with the
            Snowflake manual, and the manual wins.)

        ``enum``
            Snowflake has no enum type, so a model declaring one would be told
            the type is unsupported with no route forward.  The value is stored
            as VARCHAR and constrained outside the type, so VARCHAR is what the
            meaning becomes here.
        """
        from ..expression.types import SnowflakeArrayType, SnowflakeObjectType

        return SubstituteTypeSuggestion(mapping={
            "array": SnowflakeArrayType,
            "binary": BlobType,
            "varbinary": BlobType,
            "interval": DecimalType,
            "jsonb": JsonType,
            "uuid": (
                SnowflakeUuidType
                if self.supports_data_type_snowflake_uuid()
                else VarCharType
            ),
            "xml": SnowflakeObjectType,
            "enum": VarCharType,
        })

