# Overview

## What this backend is

`rhosocial-activerecord-snowflake` binds the ActiveRecord model to Snowflake, a
hosted cloud data warehouse. It is a backend implementation, **not a standalone
ORM**: it cannot be used on its own and is layered on top of the core
`rhosocial-activerecord` library.

The backend makes Snowflake's own concepts first-class instead of hiding them:

- the three-level `database.schema.table` namespace and double-quoted,
  case-sensitive identifiers;
- warehouse-based compute (you choose a virtual warehouse, not a server port);
- `VARIANT` / `ARRAY` semi-structured columns and their path/cast expressions;
- point-in-time reads via time travel (`AT` / `BEFORE`);
- conditional upserts via `MERGE`, because Snowflake has no DML-level `RETURNING`;
- `%s` (pyformat) placeholders, as required by the driver.

> 💡 *AI prompt: "How does this backend map an ActiveRecord model onto Snowflake's three-level namespace, and why does it generate `%s` placeholders?"*

## A hosted service, not a server version

Snowflake is continuously updated by the vendor. There is **no fixed server
version to track, pin, or gate features on** — unlike a self-managed database,
you do not install or upgrade it. What you do pin is the software on your side:

| Dependency | Constraint | Role |
|------------|-----------|------|
| `rhosocial-activerecord` | `>=1.0.0.dev30,<2.0.0` | core framework and expression layer |
| `snowflake-connector-python` | `>=3.0.0` | DB-API driver and wire protocol |

Capability answers here therefore describe the engine and this backend's
adapters, not a version number you control. See
[Capability boundaries & fail-fast](capability_boundaries.md).

## Design principles

1. **Backend implementation**: extends the core Expression → Dialect → Backend
   layering with Snowflake-specific types, expressions, mixins and protocols.
2. **Driver**: uses `snowflake-connector-python` for connectivity.
3. **Namespace package**: installs under
   `rhosocial.activerecord.backend.impl.snowflake`.
4. **Cloud-native awareness**: account, warehouse, database, schema and role are
   ordinary connection parameters; there is no local server to start.
5. **Pseudo-async, experimental**: `snowflake-connector-python` has no native
   async API, so `AsyncSnowflakeBackend` wraps synchronous cursor calls in
   `asyncio.run_in_executor`. It offers **no performance benefit and is not for
   production**. Use the synchronous `SnowflakeBackend`.

## Supported Python versions

Standard GIL builds of Python **3.8 through 3.14** are supported. Free-threaded
3.14t is experimental (pending verification of `cffi` support); free-threaded
**3.13t is not supported** because the driver's `cryptography` → `cffi` chain has
no free-threaded build. No driver wheel exists for 3.15 yet.

## When to use

- Type-safe modeling on a cloud warehouse without managing a database server.
- Applications that need `VARIANT` / `ARRAY` columns, time-travel reads, or
  `MERGE`-based upserts through the ActiveRecord model.
- Warehouse-credit-aware workloads where compute (warehouse size, auto-suspend)
  is an explicit operational choice.

## When not to use

- Workloads that require DML-level `RETURNING` (use `MERGE` or a separate
  query — see [MERGE & upsert](../features/merge.md)).
- High-concurrency async services: the async backend is a thread-pool shim and
  is explicitly experimental.
- Local/offline development with no Snowflake account: there is no local server
  binary; integration tests need cloud credentials.

## Next steps

- [Capability boundaries & fail-fast](capability_boundaries.md)
- [Installation guide](../installation/installation.md)
- [Connection configuration](../installation/configuration.md)
