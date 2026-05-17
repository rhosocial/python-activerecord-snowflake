# src/rhosocial/activerecord/backend/impl/snowflake/cli/connection.py
"""Connection argument parsing and backend creation for Snowflake CLI."""

import os


def add_connection_args(parser):
    """Add Snowflake connection arguments to a subcommand parser."""
    parser.add_argument(
        "--account",
        default=os.getenv("SNOWFLAKE_ACCOUNT"),
        help="Snowflake account identifier (env: SNOWFLAKE_ACCOUNT)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("SNOWFLAKE_HOST"),
        help="Snowflake host (env: SNOWFLAKE_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SNOWFLAKE_PORT", "443")),
        help="Snowflake port (env: SNOWFLAKE_PORT, default: 443)",
    )
    parser.add_argument(
        "--database",
        default=os.getenv("SNOWFLAKE_DATABASE"),
        help="Snowflake database (env: SNOWFLAKE_DATABASE)",
    )
    parser.add_argument(
        "--schema",
        default=os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
        help="Snowflake schema (env: SNOWFLAKE_SCHEMA, default: PUBLIC)",
    )
    parser.add_argument(
        "--warehouse",
        default=os.getenv("SNOWFLAKE_WAREHOUSE"),
        help="Snowflake warehouse (env: SNOWFLAKE_WAREHOUSE)",
    )
    parser.add_argument(
        "--role",
        default=os.getenv("SNOWFLAKE_ROLE"),
        help="Snowflake role (env: SNOWFLAKE_ROLE)",
    )
    parser.add_argument(
        "--user",
        default=os.getenv("SNOWFLAKE_USER"),
        help="Snowflake user (env: SNOWFLAKE_USER)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("SNOWFLAKE_PASSWORD"),
        help="Snowflake password (env: SNOWFLAKE_PASSWORD)",
    )
    parser.add_argument(
        "--authenticator",
        default=os.getenv("SNOWFLAKE_AUTHENTICATOR"),
        help="Authentication method (env: SNOWFLAKE_AUTHENTICATOR)",
    )
    parser.add_argument(
        "--use-async",
        action="store_true",
        help="Use asynchronous backend",
    )


def add_version_arg(parser):
    """Add --version argument (used only by info subcommand)."""
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help='Snowflake version to simulate (e.g., "8.0.0"). Default: 8.0.0.',
    )


def resolve_connection_config_from_args(args):
    """Resolve Snowflake connection config from parsed args."""
    from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig

    return SnowflakeConnectionConfig(
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.user,
        password=args.password or "",
        account=args.account,
        warehouse=args.warehouse,
        schema=args.schema,
        role=args.role,
        authenticator=args.authenticator,
    )
