"""Snowflake-specific connection configuration.

This module provides Snowflake-specific connection configuration classes that extend
the base ConnectionConfig with Snowflake-specific parameters and functionality.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from rhosocial.activerecord.backend.config import (
    ConnectionConfig,
    ConnectionPoolMixin,
    SSLMixin,
    CharsetMixin,
    TimezoneMixin,
    VersionMixin,
    LoggingMixin,
)


@dataclass
class SnowflakeConnectionConfig(
    ConnectionConfig,
    ConnectionPoolMixin,
    SSLMixin,
    CharsetMixin,
    TimezoneMixin,
    VersionMixin,
    LoggingMixin,
):
    """Snowflake connection configuration with Snowflake-specific parameters.

    This class extends the base ConnectionConfig with Snowflake-specific
    parameters including account, warehouse, schema, role, and authentication options.
    """

    # Snowflake-specific required parameters
    account: Optional[str] = None

    # Snowflake-specific organizational parameters
    warehouse: Optional[str] = None
    schema: Optional[str] = None
    role: Optional[str] = None

    # Snowflake-specific authentication
    authenticator: Optional[str] = None
    private_key: Optional[str] = None
    private_key_path: Optional[str] = None
    private_key_passphrase: Optional[str] = None
    token: Optional[str] = None
    oauth_token: Optional[str] = None

    # Snowflake-specific connection options
    autocommit: bool = True
    client_session_keep_alive: bool = False
    client_session_keep_alive_heartbeat_frequency: Optional[int] = None
    session_parameters: Optional[Dict[str, Any]] = None
    network_timeout: Optional[int] = None
    login_timeout: Optional[int] = None

    # Snowflake-specific behavior options
    warehouse_name: Optional[str] = None
    database_name: Optional[str] = None
    schema_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary, including Snowflake-specific parameters."""
        config_dict = super().to_dict()

        snowflake_params = {
            'account': self.account,
            'warehouse': self.warehouse,
            'schema': self.schema or self.schema_name,
            'role': self.role,
            'authenticator': self.authenticator,
            'private_key': self.private_key,
            'private_key_path': self.private_key_path,
            'private_key_passphrase': self.private_key_passphrase,
            'token': self.token,
            'oauth_token': self.oauth_token,
            'autocommit': self.autocommit,
            'client_session_keep_alive': self.client_session_keep_alive,
            'client_session_keep_alive_heartbeat_frequency': self.client_session_keep_alive_heartbeat_frequency,
            'session_parameters': self.session_parameters,
            'network_timeout': self.network_timeout,
            'login_timeout': self.login_timeout,
        }

        for key, value in snowflake_params.items():
            if value is not None:
                config_dict[key] = value

        return config_dict
