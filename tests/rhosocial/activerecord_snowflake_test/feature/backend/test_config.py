"""Tests for SnowflakeConnectionConfig."""
import pytest

from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig


class TestSnowflakeConnectionConfig:
    def test_default_values(self):
        config = SnowflakeConnectionConfig()
        assert config.account is None
        assert config.warehouse is None
        assert config.schema is None
        assert config.role is None
        assert config.authenticator is None
        assert config.autocommit is True
        assert config.client_session_keep_alive is False
        assert config.session_parameters is None

    def test_custom_values(self):
        config = SnowflakeConnectionConfig(
            account="RSRSBDK-YDB67606",
            warehouse="COMPUTE_WH",
            database="ANALYTICS",
            schema="PUBLIC",
            username="user",
            password="token",
            role="SYSADMIN",
        )
        assert config.account == "RSRSBDK-YDB67606"
        assert config.warehouse == "COMPUTE_WH"
        assert config.database == "ANALYTICS"
        assert config.schema == "PUBLIC"
        assert config.role == "SYSADMIN"

    def test_to_dict_includes_snowflake_params(self):
        config = SnowflakeConnectionConfig(
            account="RSRSBDK-YDB67606",
            warehouse="COMPUTE_WH",
            role="PARTICIPANT",
        )
        d = config.to_dict()
        assert d["account"] == "RSRSBDK-YDB67606"
        assert d["warehouse"] == "COMPUTE_WH"
        assert d["role"] == "PARTICIPANT"

    def test_to_dict_excludes_none_snowflake_params(self):
        config = SnowflakeConnectionConfig()
        d = config.to_dict()
        assert "account" not in d
        assert "warehouse" not in d
        assert "role" not in d
        assert "authenticator" not in d

    def test_to_dict_includes_autocommit(self):
        config = SnowflakeConnectionConfig()
        d = config.to_dict()
        assert d["autocommit"] is True

    def test_session_parameters(self):
        config = SnowflakeConnectionConfig(
            session_parameters={"STATEMENT_TIMEOUT_IN_SECONDS": 60}
        )
        d = config.to_dict()
        assert d["session_parameters"] == {"STATEMENT_TIMEOUT_IN_SECONDS": 60}

    def test_authentication_options(self):
        config = SnowflakeConnectionConfig(
            authenticator="snowflake_jwt",
            private_key_path="/path/to/key.pem",
        )
        assert config.authenticator == "snowflake_jwt"
        assert config.private_key_path == "/path/to/key.pem"

    def test_keep_alive_options(self):
        config = SnowflakeConnectionConfig(
            client_session_keep_alive=True,
            client_session_keep_alive_heartbeat_frequency=1800,
        )
        assert config.client_session_keep_alive is True
        assert config.client_session_keep_alive_heartbeat_frequency == 1800
