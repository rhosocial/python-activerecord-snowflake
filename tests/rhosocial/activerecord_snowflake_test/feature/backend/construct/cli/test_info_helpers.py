# tests/rhosocial/activerecord_snowflake_test/feature/backend/construct/cli/test_info_helpers.py
"""Backend-owned tests for ``impl.snowflake.cli.info`` pure helpers.

The shared testsuite never exercises the CLI info surface. These tests pin the
version parsing, protocol-support discovery, and display-format helpers that
are pure functions (no live Snowflake connection needed).
"""
from unittest.mock import MagicMock

import pytest

from rhosocial.activerecord.backend.impl.snowflake.cli import info as mod


class TestParseVersion:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("8.0.0", (8, 0, 0)),
            ("1.2", (1, 2, 0)),
            ("3", (3, 0, 0)),
            ("10.20.30", (10, 20, 30)),
        ],
    )
    def test_valid(self, value, expected):
        assert mod.parse_version(value) == expected

    @pytest.mark.parametrize("value", ["x.y.z", ""])
    def test_non_numeric_component_raises(self, value):
        with pytest.raises(ValueError):
            mod.parse_version(value)


class TestGetStatusStyle:
    @pytest.mark.parametrize(
        "pct,color,symbol",
        [
            (100, "green", "[OK]"),
            (75, "yellow", "[~]"),
            (50, "yellow", "[~]"),
            (25, "red", "[~]"),
            (1, "red", "[~]"),
            (0, "red", "[X]"),
        ],
    )
    def test_thresholds(self, pct, color, symbol):
        assert mod._get_status_style(pct) == (color, symbol)


class TestFormatMethodDisplay:
    @pytest.mark.parametrize(
        "method,expected",
        [
            ("supports_window_functions", "window functions"),
            ("is_json_available", "is json available"),
            ("supports_cte", "cte"),
        ],
    )
    def test_format(self, method, expected):
        assert mod._format_method_display(method) == expected


class TestCalculateProtocolStats:
    def test_bool_map(self):
        assert mod._calculate_protocol_stats({"a": True, "b": False, "c": True}) == (2, 3)

    def test_nested_dicts(self):
        data = {"g1": {"supported": 3, "total": 4}, "g2": {"supported": 1, "total": 2}}
        assert mod._calculate_protocol_stats(data) == (4, 6)

    def test_empty(self):
        assert mod._calculate_protocol_stats({}) == (0, 0)


class _Proto:
    def supports_window(self):
        return True

    def supports_cte(self):
        return False

    def is_json_available(self):
        return True

    def not_a_check(self):
        return True


class _Dialect:
    def supports_window(self):
        return True

    def supports_cte(self):
        return False

    def is_json_available(self):
        return True


class TestProtocolSupport:
    def test_get_support_methods(self):
        assert mod.get_protocol_support_methods(_Proto) == [
            "is_json_available", "supports_cte", "supports_window",
        ]

    def test_check_support(self):
        result = mod.check_protocol_support(_Dialect(), _Proto)
        assert result == {
            "is_json_available": True,
            "supports_cte": False,
            "supports_window": True,
        }

    def test_check_support_missing_method_is_false(self):
        result = mod.check_protocol_support(object(), _Proto)
        assert set(result.values()) == {False}

    def test_build_protocol_info(self):
        proto_info = mod._build_protocol_info(_Dialect(), "g", [_Proto], verbose=0)
        p = proto_info["_Proto"]
        assert p["supported"] == 2 and p["total"] == 3
        assert p["percentage"] == round(2 / 3 * 100, 1)
        assert "methods" not in p

    def test_build_protocol_info_verbose(self):
        proto_info = mod._build_protocol_info(_Dialect(), "g", [_Proto], verbose=2)
        assert "methods" in proto_info["_Proto"]
