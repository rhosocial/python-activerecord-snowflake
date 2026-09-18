# tests/rhosocial/activerecord_snowflake_test/feature/backend/dialect/test_dql_capabilities.py
"""Snowflake DQL capability tests."""

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect


def test_offset_without_limit_supported():
    assert SnowflakeDialect().supports_offset_without_limit() is True


def test_fetch_with_ties_unsupported():
    assert SnowflakeDialect().supports_fetch_with_ties() is False


def test_nulls_first_last_supported():
    assert SnowflakeDialect().supports_nulls_first_last() is True
