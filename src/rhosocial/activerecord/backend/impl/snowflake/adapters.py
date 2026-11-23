"""Snowflake backend type adapters.

This module provides type adapters for Snowflake-specific data types,
converting between Python types and Snowflake database types.
"""
import json
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Type, Union

from rhosocial.activerecord.backend.adapters import (
    BitString,
    BitStringAdapterBase,
    Geometry,
    GeometryAdapterBase,
    GeometryCollection,
    IPAddress,
    IPAddressAdapterBase,
    LineString,
    MacAddress,
    MacAddressAdapterBase,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Multirange,
    Point,
    Polygon,
    Range,
    RangeAdapterBase,
    Vector,
    VectorAdapterBase,
)
from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter


class SnowflakeVariantAdapter(SQLTypeAdapter):
    """Adapts Python dict/list to Snowflake VARIANT and vice-versa.

    Snowflake VARIANT type stores semi-structured data natively. Writing goes
    through ``json.dumps`` because the connector binds a JSON text literal for
    VARIANT columns; reading goes through ``json.loads`` when the connector hands
    the value back as text (the connector may also return ``dict``/``list``
    directly, in which case the value is returned unchanged).

    ``default`` / ``object_hook`` are forwarded to ``json.dumps`` / ``json.loads``
    so callers can plug in a neutral-type codec (see
    ``rhosocial.activerecord.backend.adapters.json_codec``). Both default to
    ``None``, which leaves the existing encoding untouched.
    """

    def __init__(
        self,
        default: Optional[Callable[[Any], Any]] = None,
        object_hook: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        """
        Args:
            default: Called by ``json.dumps`` for objects that are not natively
                JSON serializable. ``None`` keeps the stdlib behaviour.
            object_hook: Called by ``json.loads`` for every decoded JSON object.
                ``None`` keeps plain dict decoding. Bypassed when the Snowflake
                connector has already decoded the value into ``dict``/``list``.
        """
        self._json_default = default
        self._json_object_hook = object_hook

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {dict: [str], list: [str]}

    def to_database(
        self, value: Union[dict, list], target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=self._json_default)
        return value

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[Union[dict, list]]:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value, object_hook=self._json_object_hook)


class SnowflakeArrayAdapter(SQLTypeAdapter):
    """Adapts Python list to Snowflake ARRAY and vice-versa.

    Snowflake ARRAY type stores ordered sequences natively. Like the VARIANT
    adapter it serializes with ``json.dumps`` and decodes with ``json.loads``.
    ``default`` / ``object_hook`` are optional passthroughs to those calls;
    ``None`` (the default) reproduces the previous behaviour exactly.
    """

    def __init__(
        self,
        default: Optional[Callable[[Any], Any]] = None,
        object_hook: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        self._json_default = default
        self._json_object_hook = object_hook

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {list: [str]}

    def to_database(
        self, value: list, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        if isinstance(value, list):
            return json.dumps(value, ensure_ascii=False, default=self._json_default)
        return value

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[list]:
        if value is None:
            return None
        if isinstance(value, list):
            return value
        return json.loads(value, object_hook=self._json_object_hook)


class SnowflakeTimestampAdapter(SQLTypeAdapter):
    """Adapts Python datetime to Snowflake TIMESTAMP types.

    Snowflake supports three timestamp variants:
    - TIMESTAMP_LTZ: Local timezone — stored in UTC, displayed in local TZ
    - TIMESTAMP_NTZ: No timezone — stored and displayed as-is
    - TIMESTAMP_TZ: With timezone — preserves the original timezone offset

    The ``timestamp_type`` option controls behavior:
    - "ntz" (default): Naive datetimes, no TZ conversion
    - "ltz": Convert to UTC for storage, display in session TZ
    - "tz": Preserve timezone offset alongside the timestamp
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        import datetime
        return {datetime.datetime: [str]}

    def to_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        import datetime
        if not isinstance(value, datetime.datetime):
            return value

        ts_type = (options or {}).get("timestamp_type", "ntz")
        if ts_type == "ltz":
            # LTZ: normalize to UTC for storage
            if value.tzinfo is not None:
                value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        elif ts_type == "tz":
            # TZ: ensure timezone-aware for Snowflake to preserve offset
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
        # NTZ: store as-is
        return value

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        if value is None:
            return None
        import datetime
        if not isinstance(value, datetime.datetime):
            if isinstance(value, str):
                # Attempt ISO format parse
                try:
                    value = datetime.datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    return value
            else:
                return value

        ts_type = (options or {}).get("timestamp_type", "ntz")
        if ts_type == "ltz":
            # LTZ: database returns UTC, attach UTC tzinfo for proper local conversion
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
        elif ts_type == "tz":
            # TZ: value already carries timezone from Snowflake
            pass
        # NTZ: return as-is (naive datetime)
        return value


class SnowflakeBooleanAdapter(SQLTypeAdapter):
    """Adapts Python bool to Snowflake BOOLEAN and vice-versa.

    Snowflake BOOLEAN type maps directly to Python bool.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {bool: [int, str]}

    def to_database(
        self, value: bool, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        return value

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value)


class SnowflakeDecimalAdapter(SQLTypeAdapter):
    """Adapts Python Decimal to Snowflake NUMBER/DECIMAL and vice-versa.

    Snowflake NUMBER(p, s) type maps to Python Decimal for precision.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {Decimal: [float, str, int]}

    def to_database(
        self, value: Decimal, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        return value

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))


# --- Neutral-type adapters -------------------------------------------------
#
# ``rhosocial.activerecord.backend.adapters`` defines driver-independent types;
# this backend pins one wire form per type. The table is authoritative:
#
#   neutral type   column                wire value
#   Geometry       GEOGRAPHY / GEOMETRY  WKT text (read also accepts GeoJSON)
#   Vector         ARRAY / VECTOR        Python ``list`` for ARRAY columns;
#                                        JSON text ``[1.0, 2.0]`` for VECTOR
#                                        columns / text bindings
#   BitString      BINARY                whole bytes (bit_length % 8 == 0)
#   Range          VARCHAR (no native)   JSON text from ``Range.to_json_value``
#   Multirange     VARCHAR (no native)   JSON text: array of Range objects
#   MacAddress     VARCHAR (no native)   canonical lowercase colon text
#
# Snowflake GEOGRAPHY is spherical/WGS84 and GEOMETRY is planar; both accept
# WKT on write. The connector hands GEOGRAPHY/GEOMETRY back as text in the
# session's output format (WKT by default, GeoJSON if the session sets
# ``GEOGRAPHY_OUTPUT_FORMAT='GeoJSON'``), so the decoder accepts both.
#
# Snowflake has no native RANGE or MAC type, so those are stored as text; the
# neutral JSON/Range and canonical-text forms are documented above.
_GEOMETRY_TYPES = (
    Geometry,
    Point,
    LineString,
    Polygon,
    MultiPoint,
    MultiLineString,
    MultiPolygon,
    GeometryCollection,
)


class SnowflakeGeometryAdapter(GeometryAdapterBase):
    """Encodes neutral geometries as WKT for ``GEOGRAPHY`` / ``GEOMETRY``.

    Snowflake accepts a WKT string for both spatial types. On read the
    connector may return WKT (the default output format) or GeoJSON if the
    session set ``GEOGRAPHY_OUTPUT_FORMAT='GeoJSON'``; both are accepted.
    """

    def __init__(self):
        super().__init__()
        for geometry_type in _GEOMETRY_TYPES:
            self.register_type(geometry_type, str)

    def _encode(self, geometry: Geometry, target_type: Type, options: Dict[str, Any]) -> str:
        return geometry.to_wkt()

    def _decode(self, value: Any, options: Dict[str, Any]) -> Geometry:
        if isinstance(value, (bytes, bytearray)):
            value = bytes(value).decode("utf-8")
        if isinstance(value, dict):
            return Geometry.from_json_value(value)
        text = self._require_text(value).strip()
        if text.startswith("{"):
            return Geometry.from_json_value(json.loads(text))
        return Geometry.from_wkt(text)


class SnowflakeVectorAdapter(VectorAdapterBase):
    """Encodes neutral vectors for Snowflake ``ARRAY`` / ``VECTOR`` columns.

    An ``ARRAY`` column binds a Python list natively, which is the preferred
    wire value. A ``VECTOR(FLOAT, n)`` column (and a text binding of an
    ``ARRAY``) is written as the JSON array text ``[1.0, 2.0]``; Snowflake
    accepts that form for both. Decoding accepts either a list or that text.
    """

    def __init__(self):
        super().__init__()
        self.register_type(Vector, list)
        self.register_type(Vector, str)

    def _encode(self, vector: Vector, target_type: Type, options: Dict[str, Any]) -> Any:
        values = [float(item) for item in vector.values]
        if target_type is str:
            return json.dumps(values)
        if target_type is list:
            return values
        raise ValueError(
            "Snowflake vectors are written either as a list (ARRAY) or as "
            f"JSON text (VECTOR), not {getattr(target_type, '__name__', target_type)!r}"
        )

    def _decode(self, value: Any, options: Dict[str, Any]) -> Vector:
        if isinstance(value, (list, tuple)):
            return Vector.from_json_value(list(value))
        payload = json.loads(self._require_text(value))
        if not isinstance(payload, list):
            raise ValueError(
                f"expected a JSON array of numbers, got {type(payload).__name__}"
            )
        return Vector.from_json_value(payload)


class SnowflakeBitStringAdapter(BitStringAdapterBase):
    """Encodes neutral bit strings as whole bytes in a ``BINARY`` column.

    ``BINARY`` carries only whole bytes, so a bit length that is not a
    multiple of 8 cannot be represented losslessly and is rejected rather than
    silently padded or truncated.
    """

    def __init__(self):
        super().__init__()
        self.register_type(BitString, bytes)

    def _encode(self, bits: BitString, target_type: Type, options: Dict[str, Any]) -> bytes:
        if bits.bit_length % 8:
            raise ValueError(
                f"Snowflake BINARY carries whole bytes, but bit_length is {bits.bit_length}; "
                "use a VARCHAR column if the sub-byte length must be preserved"
            )
        return bits.data

    def _decode(self, value: Any, options: Dict[str, Any]) -> BitString:
        return BitString.from_bytes(self._require_bytes(value))


class SnowflakeRangeAdapter(RangeAdapterBase):
    """Encodes neutral ranges as JSON text in a Snowflake ``VARCHAR``.

    Snowflake has no range column type, so ``Range`` and ``Multirange`` are
    stored as the lossless JSON produced by ``to_json_value`` (with the
    ``element_type`` label and bound inclusivity), and re-established on read.
    """

    def __init__(self):
        super().__init__()
        self.register_type(Range, str)
        self.register_type(Multirange, str)

    def _encode(
        self, value: Union[Range, Multirange], target_type: Type, options: Dict[str, Any]
    ) -> str:
        if isinstance(value, Multirange) and target_type is Range:
            raise ValueError("a Multirange cannot be written to a single-range target")
        if isinstance(value, Range) and target_type is Multirange:
            raise ValueError("a Range cannot be written to a multirange target")
        return json.dumps(value.to_json_value(), ensure_ascii=False)

    def _decode(
        self, value: Any, target_type: Type, options: Dict[str, Any]
    ) -> Union[Range, Multirange]:
        payload = json.loads(self._require_text(value))
        if isinstance(payload, list):
            if target_type is Range:
                raise ValueError("expected one JSON range object, got a JSON array")
            return Multirange.from_json_value(payload)
        if not isinstance(payload, dict):
            raise ValueError(
                "range JSON text must decode to an object or an array, "
                f"got {type(payload).__name__}"
            )
        if target_type is Multirange:
            raise ValueError("expected a JSON array of ranges, got one JSON object")
        return Range.from_json_value(payload)


class SnowflakeMacAddressAdapter(MacAddressAdapterBase):
    """Encodes neutral MAC addresses as canonical text in a ``VARCHAR``.

    Snowflake has no MAC type; the wire value is the lowercase colon-separated
    form produced by ``str(MacAddress)``. Decoding also accepts raw octets
    from a ``BINARY(6)`` / ``BINARY(8)`` column.
    """

    def __init__(self):
        super().__init__()
        self.register_type(MacAddress, str)

    def _encode(self, mac: MacAddress, target_type: Type, options: Dict[str, Any]) -> str:
        return str(mac)

    def _decode(self, value: Any, options: Dict[str, Any]) -> MacAddress:
        if isinstance(value, (bytes, bytearray)):
            return MacAddress.parse(bytes(value))
        return MacAddress.parse(self._require_text(value))


class SnowflakeIPAddressAdapter(IPAddressAdapterBase):
    """Encodes neutral IP addresses as canonical text in a ``VARCHAR``.

    Snowflake has no IP type; the wire value is the canonical compressed form
    produced by ``str(IPAddress)``, at most 45 characters for an IPv6 address.
    """

    def __init__(self):
        super().__init__()
        self.register_type(IPAddress, str)

    def _encode(self, ip_addr: IPAddress, target_type: Type, options: Dict[str, Any]) -> str:
        return str(ip_addr)

    def _decode(self, value: Any, options: Dict[str, Any]) -> IPAddress:
        return IPAddress.parse(self._require_text(value))
