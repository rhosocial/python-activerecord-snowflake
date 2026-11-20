# tests/rhosocial/activerecord_snowflake_test/feature/backend/adapters/test_json_adapter_hooks.py
"""DB-free tests for Snowflake's VARIANT / ARRAY JSON hooks."""

import json
from typing import Any, Dict

import pytest

from rhosocial.activerecord.backend.adapters.json_codec import AdapterJSONCodec, register_type
from rhosocial.activerecord.backend.impl.snowflake.adapters import (
    SnowflakeArrayAdapter,
    SnowflakeVariantAdapter,
)


class _Demo:
    """Neutral JSON type used to exercise a pluggable codec."""

    json_type_tag = "snowflake_json_hook_demo"

    def __init__(self, value: int):
        self.value = value

    def to_json_value(self) -> Any:
        return {"number": self.value}

    @classmethod
    def from_json_value(cls, value: Any) -> "_Demo":
        return cls(int(value["number"]))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Demo) and self.value == other.value


def test_variant_without_hooks_keeps_previous_serialization():
    adapter = SnowflakeVariantAdapter()
    assert adapter.to_database({"a": 1}, dict) == '{"a": 1}'
    assert adapter.to_database([1, 2], list) == "[1, 2]"
    # Snowflake keeps non-ASCII text verbatim (ensure_ascii=False).
    assert adapter.to_database({"u": "中文"}, dict) == '{"u": "中文"}'
    assert adapter.from_database('{"a": 1}', dict) == {"a": 1}
    assert adapter.from_database("[1, 2]", list) == [1, 2]
    assert adapter.to_database(None, dict) is None
    assert adapter.from_database(None, dict) is None


def test_array_without_hooks_keeps_previous_serialization():
    adapter = SnowflakeArrayAdapter()
    assert adapter.to_database([1, 2], list) == "[1, 2]"
    assert adapter.to_database(["中"], list) == '["中"]'
    assert adapter.from_database("[1, 2]", list) == [1, 2]
    assert adapter.from_database(None, list) is None


def test_without_default_non_serializable_still_raises():
    with pytest.raises(TypeError):
        SnowflakeVariantAdapter().to_database({"s": {1, 2}}, dict)
    with pytest.raises(TypeError):
        SnowflakeArrayAdapter().to_database([{1, 2}], list)


def test_custom_default_is_forwarded_to_json_dumps():
    adapter = SnowflakeVariantAdapter(default=lambda obj: sorted(obj))
    text = adapter.to_database({"s": {2, 1}}, dict)
    assert json.loads(text) == {"s": [1, 2]}

    array_adapter = SnowflakeArrayAdapter(default=lambda obj: sorted(obj))
    assert json.loads(array_adapter.to_database([{2, 1}], list)) == [[1, 2]]


def test_matching_object_hook_is_forwarded_to_json_loads():
    def hook(value: Dict[str, Any]) -> Any:
        if set(value) == {"demo"}:
            return _Demo(value["demo"])
        return value

    adapter = SnowflakeVariantAdapter(object_hook=hook)
    assert adapter.from_database('{"demo": 7}', dict) == _Demo(7)

    nested = adapter.from_database('{"outer": {"demo": 3}}', dict)
    assert nested["outer"] == _Demo(3)


def test_plain_dict_and_list_decode_with_hook():
    adapter = SnowflakeVariantAdapter(object_hook=lambda value: value)
    assert adapter.from_database('{"a": {"b": 1}}', dict) == {"a": {"b": 1}}
    assert adapter.from_database('[{"a": 1}, [2, 3]]', list) == [{"a": 1}, [2, 3]]

    array_adapter = SnowflakeArrayAdapter(object_hook=lambda value: value)
    assert array_adapter.from_database('[{"a": 1}]', list) == [{"a": 1}]


def test_driver_decoded_values_skip_the_hook():
    """A connector that already returns dict/list never calls json.loads, so no hook."""
    adapter = SnowflakeVariantAdapter(object_hook=lambda value: _Demo(1))
    payload = {"driver": "decoded"}
    assert adapter.from_database(payload, dict) is payload

    array_adapter = SnowflakeArrayAdapter(object_hook=lambda value: _Demo(1))
    array_payload = [1, 2]
    assert array_adapter.from_database(array_payload, list) is array_payload


def test_core_adapter_json_codec_round_trip():
    register_type("snowflake_json_hook_demo", _Demo)
    codec = AdapterJSONCodec(tagged=True)
    adapter = SnowflakeVariantAdapter(default=codec.default, object_hook=codec.object_hook)

    text = adapter.to_database({"demo": _Demo(7)}, dict)
    assert '"__type__": "snowflake_json_hook_demo"' in text

    decoded = adapter.from_database(text, dict)
    assert decoded["demo"] == _Demo(7)

    array_adapter = SnowflakeArrayAdapter(default=codec.default, object_hook=codec.object_hook)
    array_text = array_adapter.to_database([_Demo(9)], list)
    assert array_adapter.from_database(array_text, list) == [_Demo(9)]
