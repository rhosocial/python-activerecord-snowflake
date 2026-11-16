# src/rhosocial/activerecord/backend/impl/snowflake/mixins/data_type_suggestions.py
"""Snowflake's **suggested data types**: what a bare field is declared as here.

The DDL half of the type answer, separate from :mod:`.column_type` for the
reason that file already states: a column class says what a value can *do*,
this says what a column *is*.

Three things about this server shape the answers:

* **semi-structured storage is one type, spelled ``VARIANT``.**  ``dict`` gets
  a ``VARIANT`` column because that is the universal container for a document
  whose key set is declared nowhere; the format (JSON, Avro, ORC, Parquet) is
  chosen by the value, not by the column.
* **arrays are native, but untyped.**  ``list``/``tuple``/``set``/``frozenset``
  get Snowflake's own ``ARRAY``.  A bare ``ARRAY`` column stores ``VARIANT``
  elements and declares no element type -- the structured ``ARRAY(NUMBER)``
  form is a different declaration -- so the shared container is what a bare
  annotation becomes.
* **everything else is the recorder's own word.**  Snowflake has one byte
  string (``BINARY``), no ``INTERVAL``, and no ``UUID`` before server release
  10.2.  A time span is stored as text, because the unit is an argument to
  ``DATEDIFF`` rather than a column property.  A UUID is a 36-character string
  below 10.2, and the native ``UUID`` type of 10.2+ is declared with
  :class:`SnowflakeUuidType` (or ``UseSqlType``) rather than suggested here:
  a suggestion has to render on every server version this dialect can describe,
  and a version-gated word does not.

Three families carry a parameter a bare annotation does not say: ``Vector``
needs a dimension, ``Range`` / ``Multirange`` need an element type, and a
``BitString`` needs a width.  A suggestion may not invent any of them, so the
**text carrier** the neutral adapter already writes is named for each.  A field
that wants the server's native type declares it with ``UseSqlType``; the
alternative, answering ``None``, would take the table away from the caller,
which is not what a suggestion is for.

Each call returns a **fresh dict** whose values are this module's read-only
templates; the derivation binds a dialect on a copy of the single entry it uses.
"""
from __future__ import annotations

import datetime
import decimal
import enum
import uuid
from typing import Any, Dict, Optional

from rhosocial.activerecord.backend.adapters import (
    BitString,
    Geometry,
    MacAddress,
    Multirange,
    Range,
    Vector,
)
from rhosocial.activerecord.backend.expression.types import (
    BlobType,
    BooleanType,
    DateType,
    DecimalType,
    DoubleType,
    IntegerType,
    TextType,
    TimeType,
    VarCharType,
)
from ..expression.types import (
    SnowflakeArrayType,
    SnowflakeGeometryType,
    SnowflakeTimestampNtzType,
    SnowflakeVariantType,
)

#: Snowflake's suggested declaration per framework-modelled Python type.
SNOWFLAKE_DATA_TYPE_SUGGESTIONS: Dict[Any, Optional[Any]] = {
    bool: BooleanType(),
    int: IntegerType(),
    float: DoubleType(),
    decimal.Decimal: DecimalType(),
    # TEXT and VARCHAR are the same storage here; the concept stays TEXT and
    # renders at Snowflake's own default width.
    str: TextType(),
    bytes: BlobType(),
    bytearray: BlobType(),
    datetime.date: DateType(),
    datetime.time: TimeType(),
    # Millisecond precision is what the framework's datetime carries; Snowflake
    # accepts 0-9 fractional-second digits.
    datetime.datetime: SnowflakeTimestampNtzType(precision=3),
    # No INTERVAL type: the value's text form is the carrier.
    datetime.timedelta: TextType(),
    # No UUID type before server 10.2; the native one is version-gated, so the
    # 36-character form is the suggestion that renders everywhere.
    uuid.UUID: VarCharType(length=36),
    # One semi-structured type serves every document format.
    dict: SnowflakeVariantType(),
    # Native ARRAY, with the element type declared by the column rather than
    # by the annotation.
    list: SnowflakeArrayType(),
    tuple: SnowflakeArrayType(),
    set: SnowflakeArrayType(),
    frozenset: SnowflakeArrayType(),
    enum.Enum: VarCharType(length=255),
    # -- Complex families ------------------------------------------------
    # GEOMETRY untyped: the column decides the shape (and GEOGRAPHY vs
    # GEOMETRY decides the datum).
    Geometry: SnowflakeGeometryType(),
    # A dimension is column policy; the adapter's text form round-trips.
    Vector: TextType(),
    # BIT(n) needs a width the annotation does not carry; digits as text.
    BitString: TextType(),
    # The element type is column policy; the adapter writes the literal text.
    Range: TextType(),
    Multirange: TextType(),
    # The ISO textual spelling (aa:bb:cc:dd:ee:ff) is 17 characters wide.
    MacAddress: VarCharType(length=17),
}


class SnowflakeDataTypeSuggestionsMixin:
    """Snowflake's answer to "what declaration does a bare field get here"."""

    def suggested_data_types(self) -> Dict[Any, Optional[Any]]:
        return dict(SNOWFLAKE_DATA_TYPE_SUGGESTIONS)


__all__ = [
    "SNOWFLAKE_DATA_TYPE_SUGGESTIONS",
    "SnowflakeDataTypeSuggestionsMixin",
]
