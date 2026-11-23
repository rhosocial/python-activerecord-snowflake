# tests/rhosocial/activerecord_snowflake_test/feature/backend/adapters/test_neutral_type_adapters.py
"""DB-free contract tests for the Snowflake neutral-type adapters.

No Snowflake account is contacted: the adapters are exercised through
``to_database`` / ``from_database`` only. The wire forms under test are the
ones documented in ``rhosocial.activerecord.backend.impl.snowflake.adapters``:

    Geometry   -> GEOGRAPHY / GEOMETRY (WKT text; GeoJSON accepted on read)
    Vector     -> ARRAY (Python list) / VECTOR (JSON text)
    BitString  -> BINARY (whole bytes only)
    Range      -> VARCHAR (JSON text; Snowflake has no RANGE)
    Multirange -> VARCHAR (JSON array text)
    MacAddress -> VARCHAR (canonical colon text)
    IPAddress  -> VARCHAR (canonical compressed text)
"""

import json

import pytest

from rhosocial.activerecord.backend.adapters import (
    BitString,
    Geometry,
    IPAddress,
    MacAddress,
    Multirange,
    Point,
    Range,
    Vector,
)
from rhosocial.activerecord.backend.errors import TypeConversionError
from rhosocial.activerecord.backend.impl.snowflake.adapters import (
    SnowflakeBitStringAdapter,
    SnowflakeGeometryAdapter,
    SnowflakeIPAddressAdapter,
    SnowflakeMacAddressAdapter,
    SnowflakeRangeAdapter,
    SnowflakeVectorAdapter,
)
from rhosocial.activerecord.backend.impl.snowflake.backend.async_backend import (
    AsyncSnowflakeBackend,
)
from rhosocial.activerecord.backend.impl.snowflake.backend.backend import (
    SnowflakeBackend,
)


NEUTRAL_ADAPTER_CLASSES = (
    SnowflakeBitStringAdapter,
    SnowflakeGeometryAdapter,
    SnowflakeIPAddressAdapter,
    SnowflakeMacAddressAdapter,
    SnowflakeRangeAdapter,
    SnowflakeVectorAdapter,
)


class TestGeometryAdapter:
    def test_wkt_round_trip(self):
        adapter = SnowflakeGeometryAdapter()
        geometry = Point(1.5, -2)

        encoded = adapter.to_database(geometry, str)
        assert encoded == "POINT (1.5 -2.0)"

        assert adapter.from_database(encoded, Geometry) == geometry

    def test_geojson_text_is_accepted_on_read(self):
        adapter = SnowflakeGeometryAdapter()
        text = json.dumps(Point(1, 2).to_json_value())
        assert adapter.from_database(text, Geometry) == Point(1, 2)

    def test_geojson_mapping_is_accepted_on_read(self):
        adapter = SnowflakeGeometryAdapter()
        assert adapter.from_database({"type": "Point", "coordinates": [1, 2]}, Geometry) == (
            Point(1, 2)
        )

    def test_unparseable_value_is_wrapped(self):
        adapter = SnowflakeGeometryAdapter()
        with pytest.raises(TypeConversionError):
            adapter.from_database("NOT A GEOMETRY", Geometry)


class TestVectorAdapter:
    def test_list_round_trip(self):
        adapter = SnowflakeVectorAdapter()
        vector = Vector([0.25, 2, -3])

        encoded = adapter.to_database(vector, list)
        assert encoded == [0.25, 2.0, -3.0]
        assert adapter.from_database(encoded, Vector) == vector

    def test_text_round_trip_for_vector_columns(self):
        adapter = SnowflakeVectorAdapter()
        vector = Vector([0.25, 2, -3])

        encoded = adapter.to_database(vector, str)
        assert json.loads(encoded) == [0.25, 2.0, -3.0]
        assert adapter.from_database(encoded, Vector) == vector

    def test_unsupported_target_is_wrapped(self):
        adapter = SnowflakeVectorAdapter()
        with pytest.raises(TypeConversionError):
            adapter.to_database(Vector([1.0]), dict)

    def test_non_sequence_is_wrapped(self):
        adapter = SnowflakeVectorAdapter()
        with pytest.raises(TypeConversionError):
            adapter.to_database("not a vector", list)


class TestBitStringAdapter:
    def test_byte_aligned_round_trip(self):
        adapter = SnowflakeBitStringAdapter()
        bits = BitString.from_bits("10110011")

        encoded = adapter.to_database(bits, bytes)
        assert encoded == b"\xb3"
        assert adapter.from_database(encoded, BitString) == bits

    def test_sub_byte_length_is_rejected(self):
        adapter = SnowflakeBitStringAdapter()
        with pytest.raises(TypeConversionError) as excinfo:
            adapter.to_database(BitString.from_bits("1011"), bytes)
        assert "whole bytes" in str(excinfo.value)

    def test_text_decode_is_wrapped(self):
        adapter = SnowflakeBitStringAdapter()
        with pytest.raises(TypeConversionError):
            adapter.from_database("1011", BitString)


class TestRangeAdapter:
    def test_range_json_round_trip(self):
        adapter = SnowflakeRangeAdapter()
        value = Range(1, 5, "[)")

        encoded = adapter.to_database(value, str)
        assert json.loads(encoded) == value.to_json_value()

        assert adapter.from_database(encoded, Range) == value

    def test_multirange_json_round_trip(self):
        adapter = SnowflakeRangeAdapter()
        value = Multirange((Range(1, 5), Range(7, 9)))

        encoded = adapter.to_database(value, str)
        assert adapter.from_database(encoded, Multirange) == value

    def test_mismatched_target_is_wrapped(self):
        adapter = SnowflakeRangeAdapter()
        with pytest.raises(TypeConversionError):
            adapter.to_database(Multirange((Range(1, 5),)), Range)

    def test_unknown_element_type_is_wrapped(self):
        adapter = SnowflakeRangeAdapter()
        payload = {
            "lower": 1,
            "upper": 5,
            "bounds": "[)",
            "empty": False,
            "element_type": "bogus",
        }
        with pytest.raises(TypeConversionError):
            adapter.from_database(json.dumps(payload), Range)


class TestMacAddressAdapter:
    def test_canonical_text_round_trip(self):
        adapter = SnowflakeMacAddressAdapter()
        mac = MacAddress.parse("08:00:2B:01:02:03")

        encoded = adapter.to_database(mac, str)
        assert encoded == "08:00:2b:01:02:03"
        assert adapter.from_database(encoded, MacAddress) == mac

    def test_binary_decode(self):
        adapter = SnowflakeMacAddressAdapter()
        assert adapter.from_database(b"\x08\x00\x2b\x01\x02\x03", MacAddress) == (
            MacAddress.parse("08:00:2b:01:02:03")
        )

    def test_bad_text_is_wrapped(self):
        adapter = SnowflakeMacAddressAdapter()
        with pytest.raises(TypeConversionError):
            adapter.from_database("nope", MacAddress)


class TestIPAddressAdapter:
    def test_ipv6_canonical_text_round_trip(self):
        adapter = SnowflakeIPAddressAdapter()
        address = IPAddress.parse("2001:db8::1")

        encoded = adapter.to_database(address, str)
        assert encoded == "2001:db8::1"
        assert adapter.from_database(encoded, IPAddress) == address

    def test_ipv4_text_round_trip(self):
        adapter = SnowflakeIPAddressAdapter()
        address = IPAddress.parse("192.0.2.1")
        assert adapter.from_database(adapter.to_database(address, str), IPAddress) == address

    def test_bad_text_is_wrapped(self):
        adapter = SnowflakeIPAddressAdapter()
        with pytest.raises(TypeConversionError):
            adapter.from_database("not-an-ip", IPAddress)


@pytest.mark.parametrize(
    "backend_cls",
    [SnowflakeBackend, AsyncSnowflakeBackend],
    ids=["sync", "async"],
)
def test_inventory_contains_neutral_adapters(backend_cls):
    backend = backend_cls(account="demo", user="demo", password="demo", database="demo")
    inventory = backend.get_type_adapters()

    for adapter_cls in NEUTRAL_ADAPTER_CLASSES:
        assert any(isinstance(adapter, adapter_cls) for adapter in inventory), (
            f"{adapter_cls.__name__} missing from get_type_adapters()"
        )
