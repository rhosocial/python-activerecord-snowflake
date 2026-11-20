# Connection configuration

Snowflake uses a different connection model from a local database: you
authenticate to an **account**, then choose a **warehouse** for compute and a
**database / schema** for object resolution. This backend uses
`SnowflakeConnectionConfig`, a subclass of the core `ConnectionConfig`.

## Minimal configuration

```python
from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig

config = SnowflakeConnectionConfig(
    account="your-account",          # e.g. XY12345.us-east-1
    username="user",
    password="secret",
    warehouse="COMPUTE_WH",
    database="myapp",
    schema="PUBLIC",
    role="SYSADMIN",
)
```

## Snowflake-specific fields

| Field | Default | Purpose |
|-------|---------|---------|
| `account` | `None` | Account identifier — the only Snowflake-specific required value |
| `warehouse` | `None` | Virtual warehouse that supplies compute for queries |
| `database` | inherited | Default database context |
| `schema` | `None` | Default schema (see `schema_name` alias below) |
| `role` | `None` | Role whose grants govern visible objects |
| `authenticator` | `None` | Authentication method: `snowflake`, `snowflake_jwt`, `oauth`, `externalbrowser` |
| `private_key` / `private_key_path` / `private_key_passphrase` | `None` | Key-pair authentication material |
| `token` / `oauth_token` | `None` | PAT / OAuth token |
| `autocommit` | `True` | Passed to the connector |
| `client_session_keep_alive` | `False` | Send heartbeats so an idle warehouse session is not dropped |
| `client_session_keep_alive_heartbeat_frequency` | `None` | Heartbeat frequency in seconds |
| `session_parameters` | `None` | Session-level parameter dict passed to the driver |
| `network_timeout` / `login_timeout` | `None` | Driver timeouts in seconds |
| `database_name` / `schema_name` / `warehouse_name` | `None` | Alternate spellings; `schema` falls back to `schema_name` in `to_dict()` |

Fields inherited from the core `ConnectionConfig` and its mixins (SSL, charset,
timezone, version, logging, pooling) follow their usual semantics.

## Authentication methods

1. **Password** — `username` + `password` with the default `snowflake`
   authenticator.
2. **Programmatic Access Token (PAT)** — a JWT-style token for automation and
   CI, generated in Snowsight (*Settings → Authentication → Programmatic access
   tokens*) or via `ALTER USER ADD PROGRAMMATIC ACCESS TOKEN ...`. Pass it as
   `password` (or via the token fields) with `authenticator="snowflake_jwt"`.
3. **SSO / external browser** — `authenticator="externalbrowser"`, which opens
   a browser for interactive sign-in.
4. **Key pair** — provide `private_key` or `private_key_path` (and
   `private_key_passphrase` if encrypted).
5. **OAuth** — `authenticator="oauth"` with `oauth_token`.

Use a PAT in CI rather than a personal password; integration test runs consume
warehouse credits and should use a dedicated role.

## Warehouse lifecycle

Virtual warehouses auto-suspend after inactivity (commonly five minutes, but
this is an account setting). A long-running operation may lose its session to
that suspension. Set `client_session_keep_alive=True` for such workloads, and
choose warehouse size deliberately — credit consumption scales with size.

## Bind the configuration to a model

```python
from rhosocial.activerecord.model import ActiveRecord
from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend

class User(ActiveRecord):
    ...

User.configure(config, SnowflakeBackend)
```

All subsequent queries on `User` go through this backend. If `database` /
`schema` are not set in the config, reference objects with three-part names —
see [Three-part naming & identifiers](../features/naming.md).

## Environment variables and CLI flags

The command-line surface accepts the same parameters as flags or environment
variables:

| Flag | Environment variable | Description |
|------|---------------------|-------------|
| `--account` | `SNOWFLAKE_ACCOUNT` | Account identifier |
| `--host` | `SNOWFLAKE_HOST` | Host, where the account alone is not enough |
| `--port` | `SNOWFLAKE_PORT` | Port (default 443) |
| `--database` | `SNOWFLAKE_DATABASE` | Database |
| `--schema` | `SNOWFLAKE_SCHEMA` | Schema (default `PUBLIC`) |
| `--warehouse` | `SNOWFLAKE_WAREHOUSE` | Virtual warehouse |
| `--role` | `SNOWFLAKE_ROLE` | Role |
| `--user` | `SNOWFLAKE_USER` | Username |
| `--password` | `SNOWFLAKE_PASSWORD` | Password or PAT |
| `--authenticator` | `SNOWFLAKE_AUTHENTICATOR` | Authentication method |

For example:

```bash
export SNOWFLAKE_ACCOUNT=your-account
export SNOWFLAKE_DATABASE=myapp
export SNOWFLAKE_WAREHOUSE=COMPUTE_WH
export SNOWFLAKE_ROLE=SYSADMIN
python -m rhosocial.activerecord.backend.impl.snowflake introspect tables
```

> The CLI has no `status` subcommand: this backend has no status introspector.
> `info` reports the version and the protocol/capability matrix instead.

## Async backend — experimental only

`snowflake-connector-python` has no native async API. `AsyncSnowflakeBackend`
wraps the synchronous driver's operations in `asyncio.run_in_executor()`: it is
a **pseudo-async thread-pool shim** with no performance benefit and is
**not for production**. Use `SnowflakeBackend` in production code.

```python
from rhosocial.activerecord.backend.impl.snowflake.backend.async_backend import (
    AsyncSnowflakeBackend,
)

backend = AsyncSnowflakeBackend(account="your-account", database="myapp")
await backend.connect()
```

The async introspector shares its parsers with the synchronous one, so records
have the same shape on both sides; only the executor differs.

## Next steps

- [Three-part naming & identifiers](../features/naming.md)
- [VARIANT & ARRAY](../features/semi_structured.md)
