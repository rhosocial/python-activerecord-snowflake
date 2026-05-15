"""Tests for Snowflake type adapters."""
import json
from decimal import Decimal
from typing import Any, Dict

import pytest

from rhosocial.activerecord.backend.impl.snowflake.adapters import (
    SnowflakeVariantAdapter,
    SnowflakeArrayAdapter,
    SnowflakeBooleanAdapter,
    SnowflakeDecimalAdapter,
    SnowflakeTimestampAdapter,
)


class TestSnowflakeVariantAdapter:
    def setup_method(self):
        self.adapter = SnowflakeVariantAdapter()

    def test_to_database_dict(self):
        data = {"key": "value"}
        result = self.adapter.to_database(data, dict)
        assert result == json.dumps(data, ensure_ascii=False)

    def test_to_database_list(self):
        data = [1, 2, 3]
        result = self.adapter.to_database(data, list)
        assert result == json.dumps(data, ensure_ascii=False)

    def test_to_database_none(self):
        assert self.adapter.to_database(None, dict) is None

    def test_from_database_dict(self):
        result = self.adapter.from_database({"key": "value"}, dict)
        assert result == {"key": "value"}

    def test_from_database_json_string(self):
        result = self.adapter.from_database('{"key": "value"}', dict)
        assert result == {"key": "value"}

    def test_from_database_none(self):
        assert self.adapter.from_database(None, dict) is None

    def test_round_trip_dict(self):
        data = {"name": "test", "count": 42, "nested": {"a": 1}}
        serialized = self.adapter.to_database(data, dict)
        deserialized = self.adapter.from_database(serialized, dict)
        assert deserialized == data

    def test_round_trip_list(self):
        data = [1, "two", 3.0, None]
        serialized = self.adapter.to_database(data, list)
        deserialized = self.adapter.from_database(serialized, list)
        assert deserialized == data

    def test_supported_types(self):
        types = self.adapter.supported_types
        assert dict in types
        assert list in types


class TestSnowflakeArrayAdapter:
    def setup_method(self):
        self.adapter = SnowflakeArrayAdapter()

    def test_to_database_list(self):
        result = self.adapter.to_database([1, 2, 3], list)
        assert result == json.dumps([1, 2, 3], ensure_ascii=False)

    def test_to_database_none(self):
        assert self.adapter.to_database(None, list) is None

    def test_from_database_list(self):
        result = self.adapter.from_database([1, 2, 3], list)
        assert result == [1, 2, 3]

    def test_from_database_json_string(self):
        result = self.adapter.from_database("[1, 2, 3]", list)
        assert result == [1, 2, 3]

    def test_from_database_none(self):
        assert self.adapter.from_database(None, list) is None

    def test_round_trip(self):
        data = [1, "two", 3.0]
        serialized = self.adapter.to_database(data, list)
        deserialized = self.adapter.from_database(serialized, list)
        assert deserialized == data


class TestSnowflakeBooleanAdapter:
    def setup_method(self):
        self.adapter = SnowflakeBooleanAdapter()

    def test_to_database_true(self):
        assert self.adapter.to_database(True, bool) is True

    def test_to_database_false(self):
        assert self.adapter.to_database(False, bool) is False

    def test_to_database_none(self):
        assert self.adapter.to_database(None, bool) is None

    def test_from_database_bool(self):
        assert self.adapter.from_database(True, bool) is True
        assert self.adapter.from_database(False, bool) is False

    def test_from_database_int(self):
        assert self.adapter.from_database(1, bool) is True
        assert self.adapter.from_database(0, bool) is False

    def test_from_database_string(self):
        assert self.adapter.from_database("true", bool) is True
        assert self.adapter.from_database("false", bool) is False
        assert self.adapter.from_database("1", bool) is True
        assert self.adapter.from_database("0", bool) is False

    def test_from_database_none(self):
        assert self.adapter.from_database(None, bool) is None


class TestSnowflakeDecimalAdapter:
    def setup_method(self):
        self.adapter = SnowflakeDecimalAdapter()

    def test_to_database_decimal(self):
        result = self.adapter.to_database(Decimal("123.45"), Decimal)
        assert result == 123.45

    def test_to_database_none(self):
        assert self.adapter.to_database(None, Decimal) is None

    def test_from_database_decimal(self):
        result = self.adapter.from_database(Decimal("123.45"), Decimal)
        assert result == Decimal("123.45")

    def test_from_database_float(self):
        result = self.adapter.from_database(123.45, Decimal)
        assert result == Decimal("123.45")

    def test_from_database_string(self):
        result = self.adapter.from_database("123.45", Decimal)
        assert result == Decimal("123.45")

    def test_from_database_int(self):
        result = self.adapter.from_database(123, Decimal)
        assert result == Decimal("123")

    def test_from_database_none(self):
        assert self.adapter.from_database(None, Decimal) is None


class TestSnowflakeTimestampAdapter:
    def setup_method(self):
        self.adapter = SnowflakeTimestampAdapter()

    def test_to_database_passthrough(self):
        import datetime
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert self.adapter.to_database(dt, datetime.datetime) == dt

    def test_to_database_none(self):
        assert self.adapter.to_database(None, object) is None

    def test_from_database_passthrough(self):
        import datetime
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert self.adapter.from_database(dt, datetime.datetime) == dt

    def test_from_database_none(self):
        assert self.adapter.from_database(None, object) is None
