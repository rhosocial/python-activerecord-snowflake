# src/rhosocial/activerecord/backend/impl/snowflake/mixins/types.py
"""Snowflake DataType formatting and parsing mixin.

Uses DDLTypeMixin naming-convention dispatch for Snowflake-specific type SQL.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.ddl_type import DDLTypeMixin
from rhosocial.activerecord.backend.dialect.protocols import DDLTypeSupport
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


class SnowflakeTypeSupportMixin(DDLTypeMixin, DDLTypeSupport):
    """Snowflake DataType formatting and parsing.

    Implements ``DDLTypeSupport`` so the dialect can render ``DataType``
    expressions to SQL strings and parse raw SQL type strings back into
    ``DataType`` instances.

    Formatting dispatches by the type instance's ``name`` through the
    naming-convention ``format_data_type_<name>`` methods (see
    ``DDLTypeMixin``). Snowflake-specific types carry ``snowflake_``-prefixed
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

    def type_parameter_defaults(self) -> Dict[str, Dict[str, object]]:
        """The widths and precisions Snowflake supplies for a declaration that
        named none.

        Every number here is quoted from the manual and none is a guess: an
        unsized ``VARCHAR`` on Snowflake **is** ``VARCHAR(16777216)``, an unsized
        ``CHAR`` is ``CHAR(1)``, and an unsized ``NUMBER`` is ``NUMBER(38, 0)``.
        That matters most because Snowflake's catalog will not tell you otherwise
        -- ``INFORMATION_SCHEMA.COLUMNS`` reports ``DATA_TYPE`` as the bare word
        (``VARCHAR``, ``NUMBER``, and since behaviour-change bundle BCR-1960
        ``VARCHAR`` for every string column; before that bundle, which is
        **postponed with no new release date**, the bare word is ``TEXT``) and
        keeps the size in separate columns.  So a bare word reaching
        :meth:`parse_type` is not an unusual thing to meet: on this backend it is
        the normal case, and the value that fills it in has to be the server's
        real default or the parser is inventing one.

        **It used to invent 255**, which appears nowhere in Snowflake's
        documentation and is not any server's default here.  The consequence was
        not cosmetic: a ``VARCHAR(50)`` column introspected as
        ``VarCharType(length=255)``, so the schema differ compared it against the
        declaration that made it, found two different widths, and reported a
        change on a column that had not changed.  16777216 is at least the width
        Snowflake really gives an unsized declaration.

        ``snowflake_varchar`` is declared separately from ``varchar`` because
        :class:`~...impl.snowflake.expression.types.SnowflakeVarcharType` is the
        same concept reached through this dialect's own entry point and carries
        its own dispatch key.  Two names, one width -- and they are declared side
        by side on purpose, because a dialect that let them drift apart would be
        describing one storage two ways.  ``snowflake_number`` is declared for the
        same reason beside ``decimal``.

        ``decimal`` / ``snowflake_number`` are declared now, where they were not
        before, and the reason is the *second* shape of the same defect: the
        catalog reports a ``NUMBER`` column's size as ``NUMERIC_PRECISION`` and
        ``NUMERIC_SCALE``, not as a length, so ``NUMBER(10, 2)`` introspected as
        a bare ``DecimalType`` with both parameters dropped -- and the differ
        reported a change on every sized numeric column.  The declaration is
        load-bearing in both directions: core resolves ``precision`` and
        ``scale`` at read time exactly as it resolves
        :attr:`~...expression.types.VarCharType.length`, so a bare
        ``DecimalType(dialect)`` carries -- and therefore compares as -- the
        documented ``NUMBER(38, 0)`` the server actually stores, and the
        introspector no longer has to fold the catalog's explicit pair back to
        the bare word (see
        :meth:`~...introspection.introspector.SnowflakeIntrospectorMixin._catalog_type_string`).
        ``NUMBER(38, 0)`` and a bare ``NUMBER`` are one column on this server
        -- "By default, precision is 38, and scale is 0; that is, NUMBER(38, 0)"
        -- so the resolved pair is what makes the declaration and its own round
        trip agree rather than merely render the same storage.

        What is deliberately **not** declared: ``text``, whose
        ``VARCHAR(16777216)`` is written out by :meth:`format_data_type_text`
        rather than being a bare form at all; ``blob``, whose ``BINARY`` length
        the manual states in **bytes** ("If no length is specified, the default is
        8388608") while ``BlobType`` carries no width at all, so there is nothing
        for the framework to fill in; and the integer and float shapes, whose
        names the manual defines as ``NUMBER(38, 0)`` and a bare ``FLOAT``
        respectively -- parameters "can't be specified" for the former, so
        resolving one would be inventing a parameter the type refuses to accept.
        """
        return {
            "char": {"length": self._SNOW_CHAR_DEFAULT_LENGTH},
            "varchar": {"length": self._SNOW_VARCHAR_DEFAULT_LENGTH},
            "snowflake_varchar": {"length": self._SNOW_VARCHAR_DEFAULT_LENGTH},
            "decimal": {
                "precision": self._SNOW_NUMBER_DEFAULT_PRECISION,
                "scale": self._SNOW_NUMBER_DEFAULT_SCALE,
            },
            "snowflake_number": {
                "precision": self._SNOW_NUMBER_DEFAULT_PRECISION,
                "scale": self._SNOW_NUMBER_DEFAULT_SCALE,
            },
        }

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

        A type bound to *this* dialect never reaches that absence, because core
        now resolves the undeclared precision to the value declared in
        :meth:`type_parameter_defaults` before this method sees it:
        ``SnowflakeNumberType(dialect, scale=2)`` renders ``NUMBER(38, 2)``, on
        the manual's own statement that the default precision is 38.  The
        refusal below therefore fires for a type bound to a dialect that
        supplies no precision — or to none at all — where there is nothing
        honest to fill in and writing a bare ``NUMBER`` on the caller's behalf
        would decide a precision this framework does not know that server has.
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
    # DDLTypeSupport — formatting (core types)
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
        """
        if not expr.unsigned:
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
        """
        if not getattr(expr, "unsigned", False):
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
        """Both spellings render ``VARCHAR``, and an undeclared width is written out.

        ``CHARACTER VARYING`` is SQL's own long form and not one of the words
        the Snowflake manual lists (it lists ``STRING``, ``TEXT``,
        ``VARCHAR2``, ``NVARCHAR`` and ``CHAR VARYING``), but it names the same
        variable-length string and refusing it would refuse the spelling
        ``parse_type()`` itself produces for that word, which would make the
        round trip lossy in the wrong direction.  Snowflake's own word is what
        gets written.

        **A bare declaration now renders ``VARCHAR(16777216)`` where it used to
        render a bare ``VARCHAR``, and the two are the same column.**  The
        manual is explicit — "If no length is specified, the default is
        16777216" — and the value is resolved onto the type by
        :meth:`type_parameter_defaults`, so this formatter is writing a width the
        type actually carries rather than substituting one of its own.  Two
        things follow, and both are the point:

        * the declared type and the catalog's report of the column it produced
          are now **the same value**.  A bare ``VarCharType`` used to render
          ``VARCHAR`` while carrying no length, and ``parse_type("VARCHAR")``
          answered 255, so the declaration compared unequal to its own
          round trip and the differ invented a change on every undeclared
          string column.
        * on Snowflake an undeclared ``VARCHAR`` and unbounded text are the same
          storage, so this now renders exactly what
          :meth:`format_data_type_text` renders — ``VARCHAR(16777216)``.  The
          classes stay distinct, because the differ is entitled to see that a
          caller declared a bounded concept rather than text; the *server* does
          not distinguish them and does not pretend to.
        """
        self._check_spelling(expr, VarCharType)
        if expr.length is not None:
            return f"VARCHAR({expr.length})", ()
        return "VARCHAR", ()

    def format_data_type_char(self, expr: CharType) -> Tuple[str, tuple]:
        """``CHARACTER`` is documented by Snowflake as a synonym of ``CHAR``, so
        both are accepted; the rendered length is Snowflake's own default of
        ``CHAR(1)`` when none was declared.

        That default is now resolved onto the type by
        :meth:`type_parameter_defaults`, so ``CharType(dialect)`` carries the 1
        rather than the formatter substituting it.  **The SQL is unchanged**: it
        was already ``CHAR(1)`` for a bare declaration, and the manual's "except
        the default length is ``VARCHAR(1)``" is what that 1 is.
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

        This is the honest-ignorance escape hatch, and it is what
        ``parse_type()`` produces for a name it does not recognise — without it
        the round trip through introspection loses the name it just read.  It is
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

        It is also declared under its own ``snowflake_varchar`` key in
        :meth:`type_parameter_defaults`, which is what keeps the two routes
        resolving to the same width: this class is not the core ``VarCharType``
        and so is not handed its declaration by inheritance, exactly as
        :class:`~...impl.sqlserver.expression.types.SQLServerNVarCharMaxType` is
        not handed SQL Server's ``VARCHAR`` width merely for deriving from one.
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

    # ------------------------------------------------------------------
    # DDLTypeSupport — parsing
    # ------------------------------------------------------------------

    _SNOW_INTEGER_TYPES = re.compile(r"^(?:INT|INTEGER|BIGINT|SMALLINT|TINYINT|BYTEINT)\b", re.IGNORECASE)
    _SNOW_FLOAT_TYPES = re.compile(r"^(?:FLOAT|FLOAT4|FLOAT8|DOUBLE|DOUBLE\s+PRECISION|REAL)\b", re.IGNORECASE)
    _SNOW_DECIMAL_TYPES = re.compile(r"^(?:NUMBER|DECIMAL|NUMERIC)\b", re.IGNORECASE)
    _SNOW_STRING_TYPES = re.compile(r"^(?:VARCHAR|CHAR|CHARACTER|STRING|TEXT)\b", re.IGNORECASE)
    _SNOW_BINARY_TYPES = re.compile(r"^(?:BINARY|VARBINARY)\b", re.IGNORECASE)
    _SNOW_DATE_TYPES = re.compile(r"^(?:DATETIME|TIMESTAMP(?:_[A-Z]+)?|DATE|TIME)\b", re.IGNORECASE)
    _SNOW_BOOLEAN_TYPES = re.compile(r"^(?:BOOLEAN)\b", re.IGNORECASE)
    _SNOW_VARIANT_TYPES = re.compile(r"^(?:VARIANT|OBJECT|ARRAY)\b", re.IGNORECASE)
    _SNOW_UUID_TYPES = re.compile(r"^UUID\b", re.IGNORECASE)
    _SNOW_GEO_TYPES = re.compile(r"^(?:GEOGRAPHY|GEOMETRY)\b", re.IGNORECASE)
    # ``UNSIGNED`` as a whole word anywhere in a type string.  Snowflake has no
    # unsigned type and no attribute slot to write one in, so no catalog row can
    # carry this; ``parse_type`` is also the reader for caller-supplied DDL, and
    # reading the attribute off there would hand back a signed value object for a
    # declaration that says otherwise.  Refused by name instead --
    # ``_refuse_unsigned_type_string``.
    _UNSIGNED_ATTRIBUTE = re.compile(r"\bUNSIGNED\b", re.IGNORECASE)

    def _refuse_unsigned_type_string(self, raw: str) -> None:
        """Refuse a type string that carries an ``UNSIGNED`` attribute.

        :meth:`_refuse_unsigned_numeric` closes the door on the way *in* — a
        declaration.  This closes it on the way *out*: a string.  Same field, same
        loss, other direction, and a real hole because ``parse_type`` reads two
        sources: Snowflake's own ``SHOW COLUMNS`` rows **and** caller-supplied DDL
        such as a dump or a hand-written migration.

        Without this the ``_SNOW_INTEGER_TYPES`` / ``_SNOW_FLOAT_TYPES`` /
        ``_SNOW_DECIMAL_TYPES`` branches would match the word in front of it and
        return a *signed* type: ``parse_type("NUMBER(10,2) UNSIGNED")`` would be
        ``DecimalType(precision=10, scale=2)``, and ``==`` would call that equal to
        the signed column — the differ reporting no change for the one change the
        string describes.

        Nothing here claims a catalog row is at stake: Snowflake's numeric
        inventory has no unsigned row and its column grammar leaves no modifier
        after ``<col_type>``, so no server can have written this string.  The
        branch guards the caller-supplied path and says so.
        """
        raise UnsupportedFeatureError(
            self.name,
            f"an UNSIGNED attribute in a type string ({raw!r}) "
            f"(Snowflake has no unsigned numeric type, so no declaration and no "
            f"catalog row can carry UNSIGNED: the summary table of every numeric "
            f"data type it has has no unsigned row, unsigned integers are on the "
            f"manual's own list of Parquet features that aren't supported, and "
            f"the column grammar leaves no modifier after <col_type> in which "
            f"UNSIGNED could go. Reading the attribute off and returning a signed "
            f"type would compare equal to the signed column, which is the silent "
            f"loss this refuses.)",
            suggestion=(
                "Declare the column signed and enforce the range with a CHECK "
                "constraint if negatives must be rejected."
            ),
        )

    def parse_type(self, raw: str) -> DataType:
        stripped = raw.strip()
        upper = stripped.upper()

        if self._UNSIGNED_ATTRIBUTE.search(stripped):
            self._refuse_unsigned_type_string(stripped)

        if self._SNOW_INTEGER_TYPES.match(upper):
            if upper.startswith("BIGINT"):
                return BigIntType(dialect=self)
            if upper.startswith("SMALLINT"):
                return SmallIntType(dialect=self)
            return IntegerType(dialect=self)

        if self._SNOW_FLOAT_TYPES.match(upper):
            if "DOUBLE" in upper or "REAL" in upper:
                return DoubleType(dialect=self)
            return FloatType(dialect=self)

        if self._SNOW_DECIMAL_TYPES.match(upper):
            nums = re.findall(r"\d+", stripped)
            if len(nums) >= 2:
                return DecimalType(dialect=self, precision=int(nums[0]), scale=int(nums[1]))
            if len(nums) == 1:
                return DecimalType(dialect=self, precision=int(nums[0]))
            return DecimalType(dialect=self)

        if self._SNOW_STRING_TYPES.match(upper):
            length_match = re.search(r"\((\d+)", stripped)
            length = int(length_match.group(1)) if length_match else None
            # An unsized declaration is completed from ``type_parameter_defaults()``
            # rather than from a number written here, so the parser cannot claim a
            # width Snowflake does not document.  It used to invent 255, which is
            # in no Snowflake document; the declared default is 16777216 and the
            # manual says so outright.
            #
            # A *bare* word from the catalog is no longer the only case, but it is
            # still a real one: ``parse_type`` is called on caller-supplied DDL as
            # well as on catalog rows, so ``parse_type("VARCHAR")`` has to keep
            # answering the server's default.
            #
            # ``VARYING`` has to be decided first: both ``CHARACTER VARYING`` and
            # Snowflake's own ``CHAR VARYING`` name the *variable-length* string,
            # and a plain prefix test for ``CHAR`` would silently hand back a
            # fixed-length ``CharType`` — a wrong-width column that the differ
            # would then compare as equal to the one that was actually declared.
            if upper.startswith("CHARACTER VARYING") or upper.startswith("CHAR VARYING"):
                return VarCharType(
                    dialect=self,
                    length=length or self._SNOW_VARCHAR_DEFAULT_LENGTH,
                    spelling="character varying",
                )
            if "VARCHAR" in upper:
                return VarCharType(
                    dialect=self, length=length or self._SNOW_VARCHAR_DEFAULT_LENGTH)
            # ``TEXT`` and ``STRING`` are documented synonyms of ``VARCHAR``, and
            # this branch is what the catalog's own word reaches: behaviour-change
            # bundle BCR-1960 makes ``DATA_TYPE`` read ``VARCHAR`` for every string
            # column, and the postponed bundle it replaced had it reading ``TEXT``
            # for all of them.
            # https://docs.snowflake.com/en/release-notes/bcr-bundles/un-bundled/bcr-1960
            #
            # A **sized** ``TEXT(50)`` is therefore a 50-character variable-length
            # string and nothing else -- the manual puts ``TEXT`` in the same list
            # as ``VARCHAR2`` and ``NVARCHAR``, all "Synonymous with VARCHAR" -- so
            # it parses as one.  It used to parse as the unbounded concept
            # regardless of the size, which lost the width outright: a ``VARCHAR(50)``
            # column on an account that has not enabled BCR-1960 came back as a bare
            # ``TextType``.  A **bare** ``TEXT`` still parses as
            # :class:`TextType`, because the bare form genuinely is the unbounded
            # concept on this server.
            # https://docs.snowflake.com/en/sql-reference/data-types-text
            if ("TEXT" in upper or "STRING" in upper) and length is not None:
                return VarCharType(dialect=self, length=length)
            if "TEXT" in upper or "STRING" in upper:
                return TextType(dialect=self)
            if upper.startswith("CHARACTER"):
                return CharType(
                    dialect=self,
                    length=length or self._SNOW_CHAR_DEFAULT_LENGTH,
                    spelling="character",
                )
            return CharType(dialect=self, length=length or self._SNOW_CHAR_DEFAULT_LENGTH)

        if self._SNOW_BINARY_TYPES.match(upper):
            return BlobType(dialect=self)

        if self._SNOW_DATE_TYPES.match(upper):
            # The three TIMESTAMP_* words are three storages and the catalog
            # reports each verbatim, so each parses to its own class. The
            # branch used to answer the NTZ concept for all three, which
            # collapsed a TIMESTAMP_LTZ column and a TIMESTAMP_TZ column
            # into the NTZ one -- a difference the differ could not see,
            # found by the render-parse-re-render sweep over this backend's
            # own registry.
            # Three TIMESTAMP_* words, answered by the core-class design
            # this parse follows: the concept that renders the word. That
            # used to be DateTimeType for all three, which collapsed a
            # TIMESTAMP_LTZ column and a TIMESTAMP_TZ column into the NTZ
            # concept -- a difference the differ could not see, found by the
            # round-trip sweep. TIMESTAMP_TZ is what core's
            # :class:`TimestampTzType` renders here, so it answers; LTZ has
            # no core rendering and follows the UUID exception's shape --
            # a backend-native word with no core spelling parses to the
            # backend's own class.
            if "TIMESTAMP" in upper:
                if "TIMESTAMP_LTZ" in upper:
                    return SnowflakeTimestampLtzType(dialect=self)
                if "TIMESTAMP_TZ" in upper:
                    return TimestampTzType(dialect=self)
                return DateTimeType(dialect=self)
            # The fractional-seconds precision is part of a TIME column's
            # identity, so it is read off the rendering rather than
            # dropped: parse_type("TIME(9)") used to answer a bare TimeType
            # that re-rendered "TIME", silently widening the column.
            if upper.startswith("TIME"):
                nums = re.findall(r"\d+", stripped)
                precision = int(nums[0]) if nums else None
                return TimeType(dialect=self, precision=precision)
            if upper.startswith("DATE"):
                if upper.strip() == "DATE":
                    return DateType(dialect=self)
                return DateTimeType(dialect=self)
            return DateTimeType(dialect=self)

        if self._SNOW_BOOLEAN_TYPES.match(upper):
            return BooleanType(dialect=self)

        # Semi-structured: one concept, three words. The design this parse
        # follows -- pinned in test_data_type_parsing.py -- is that parse
        # answers *concepts*, and the semi-structured concept is JsonType:
        # VARIANT serves JSON, OBJECT and ARRAY alike, so all three words
        # parse to it and the differ, comparing two introspected columns,
        # stays internally consistent. The words the *own* classes render
        # are recorded in the round-trip sweep's table as (class, string)
        # entries instead: a declared SnowflakeArrayType parses to the
        # concept and re-renders as VARIANT, which the table states as a
        # reviewable fact rather than as string instability.
        if self._SNOW_VARIANT_TYPES.match(upper):
            return JsonType(dialect=self)

        # Geospatial: own words with own classes, each rendering a single
        # word the catalog reports verbatim. They used to fall through to
        # CustomType -- a dialect that renders a word its own parse does
        # not model has a gap on one side or the other.
        if self._SNOW_GEO_TYPES.match(upper):
            if upper.startswith("GEOGRAPHY"):
                return SnowflakeGeographyType(dialect=self)
            return SnowflakeGeometryType(dialect=self)

        if self._SNOW_UUID_TYPES.match(upper):
            return SnowflakeUuidType(dialect=self)

        # A user-defined type reference renders as its quoted, optionally
        # database- and schema-qualified name -- and the catalog reports the
        # same back. The type-name validation guarding CustomType refuses a
        # quoted name by design, so the quoted forms are recognised here
        # and rebuilt as the UDT they came from: collapsing them to
        # CustomType raised on this dialect's own rendering, and answering
        # an unquoted raw would have been a different name.
        udt_match = re.match(r'^(?:"[^"]+"\s*\.\s*){0,2}"[^"]+"$', stripped)
        if udt_match is not None:
            parts = re.findall(r'"([^"]+)"', stripped)
            if len(parts) == 1:
                return SnowflakeUserDefinedType(dialect=self, type_name=parts[0])
            if len(parts) == 2:
                return SnowflakeUserDefinedType(
                    dialect=self, type_name=parts[1], schema_name=parts[0])
            return SnowflakeUserDefinedType(
                dialect=self, type_name=parts[2], schema_name=parts[1],
                database_name=parts[0])

        return CustomType(dialect=self, raw=stripped)

    def suggested_data_types(self) -> Dict[str, type]:
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

        return {
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
        }

