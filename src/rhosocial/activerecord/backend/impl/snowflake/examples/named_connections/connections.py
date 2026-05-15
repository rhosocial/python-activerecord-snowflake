"""Snowflake named connection definitions.

Each callable returns a SnowflakeConnectionConfig instance.
These can be resolved via NamedConnectionResolver or used directly.

Usage:
    from rhosocial.activerecord.backend.impl.snowflake.examples.named_connections.connections import spider2_snow

    # Direct usage
    config = spider2_snow()
    backend = SnowflakeBackend(connection_config=config)
    backend.connect()

    # Via NamedConnectionResolver
    from rhosocial.activerecord.backend.named_connection import resolve_named_connection
    config = resolve_named_connection(
        "rhosocial.activerecord.backend.impl.snowflake.examples.named_connections.connections.spider2_snow"
    )
"""
from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig


def spider2_snow():
    """Spider 2.0 Snow evaluation environment (PARTICIPANT role).

    Provides read-only access to the Spider 2.0 Snowflake datasets
    used in the Spider 2.0 benchmark evaluation.
    """
    return SnowflakeConnectionConfig(
        account="RSRSBDK-YDB67606",
        username="vistart",
        password="",  # PAT token must be provided via environment or override
        warehouse="COMPUTE_WH_PARTICIPANT",
        role="PARTICIPANT",
        database="IOWA_LIQUOR_SALES",
        schema="IOWA_LIQUOR_SALES",
        autocommit=True,
        client_session_keep_alive=True,
    )


def analytics_dev():
    """Development analytics environment.

    Connects to a development Snowflake account for ad-hoc analysis.
    Uses password authentication with a development warehouse.
    """
    return SnowflakeConnectionConfig(
        account="dev-org-dev_account",
        username="analyst",
        password="",  # Set via environment variable
        warehouse="DEV_WH",
        role="ANALYST_DEV",
        database="ANALYTICS_DEV",
        schema="PUBLIC",
        autocommit=True,
        client_session_keep_alive=True,
    )


def analytics_prod():
    """Production analytics environment.

    Connects to the production Snowflake account using SSO/JWT authentication.
    Uses a production-optimized warehouse.
    """
    return SnowflakeConnectionConfig(
        account="prod-org-prod_account",
        username="analyst",
        authenticator="externalbrowser",  # SSO via browser
        warehouse="PROD_WH_XLARGE",
        role="ANALYST_PROD",
        database="ANALYTICS",
        schema="PUBLIC",
        autocommit=False,  # Explicit transaction control in production
        client_session_keep_alive=True,
    )
