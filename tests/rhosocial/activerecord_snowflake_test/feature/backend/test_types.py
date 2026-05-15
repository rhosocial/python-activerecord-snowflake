"""Tests for Snowflake type helper classes."""
import pytest

from rhosocial.activerecord.backend.impl.snowflake.types import (
    SnowflakeVariant,
    SnowflakeArray,
)


class TestSnowflakeVariant:
    def test_create_with_dict(self):
        v = SnowflakeVariant({"key": "value"})
        assert v.value == {"key": "value"}

    def test_create_with_list(self):
        v = SnowflakeVariant([1, 2, 3])
        assert v.value == [1, 2, 3]

    def test_create_with_none(self):
        v = SnowflakeVariant(None)
        assert v.value is None

    def test_create_default(self):
        v = SnowflakeVariant()
        assert v.value is None

    def test_to_database(self):
        data = {"a": 1}
        v = SnowflakeVariant(data)
        assert v.to_database() == data

    def test_repr(self):
        v = SnowflakeVariant({"key": "value"})
        assert "SnowflakeVariant" in repr(v)
        assert "key" in repr(v)

    def test_equality_same_type(self):
        v1 = SnowflakeVariant({"key": "value"})
        v2 = SnowflakeVariant({"key": "value"})
        assert v1 == v2

    def test_equality_different_type(self):
        v = SnowflakeVariant({"key": "value"})
        assert v == {"key": "value"}

    def test_inequality(self):
        v1 = SnowflakeVariant({"a": 1})
        v2 = SnowflakeVariant({"b": 2})
        assert v1 != v2

    def test_hash(self):
        v1 = SnowflakeVariant({"key": "value"})
        v2 = SnowflakeVariant({"key": "value"})
        assert hash(v1) == hash(v2)


class TestSnowflakeArray:
    def test_create_with_list(self):
        a = SnowflakeArray([1, 2, 3])
        assert a.elements == [1, 2, 3]

    def test_create_empty(self):
        a = SnowflakeArray()
        assert a.elements == []

    def test_create_with_none(self):
        a = SnowflakeArray(None)
        assert a.elements == []

    def test_to_database(self):
        a = SnowflakeArray([1, 2, 3])
        assert a.to_database() == [1, 2, 3]

    def test_len(self):
        a = SnowflakeArray([1, 2, 3])
        assert len(a) == 3

    def test_getitem(self):
        a = SnowflakeArray([10, 20, 30])
        assert a[0] == 10
        assert a[2] == 30

    def test_getitem_slice(self):
        a = SnowflakeArray([10, 20, 30, 40])
        assert a[1:3] == [20, 30]

    def test_repr(self):
        a = SnowflakeArray([1, 2])
        assert "SnowflakeArray" in repr(a)

    def test_equality_same_type(self):
        a1 = SnowflakeArray([1, 2])
        a2 = SnowflakeArray([1, 2])
        assert a1 == a2

    def test_equality_different_type(self):
        a = SnowflakeArray([1, 2])
        assert a == [1, 2]

    def test_inequality(self):
        a1 = SnowflakeArray([1, 2])
        a2 = SnowflakeArray([3, 4])
        assert a1 != a2
