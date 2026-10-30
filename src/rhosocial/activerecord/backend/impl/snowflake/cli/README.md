# `introspect` — Snowflake metadata, from the command line

The `introspect` subcommand asks a live Snowflake account what it holds, and
prints the answer. Every question runs through the backend's introspector, so
what the CLI reports is what the library sees — the same objects, the same
types, the same parsing — rather than a second implementation that can drift
from it.

```bash
python -m rhosocial.activerecord.backend.impl.snowflake introspect <TYPE> [NAME] [OPTIONS]
```

## What it can ask about

| Type | `NAME` | Reads | Notes |
| :--- | :--- | :--- | :--- |
| `tables` | — | `information_schema.tables` | Tables, with the kind the catalogue reports and their comment. |
| `views` | view, optional | `information_schema.views` | Views, with their definitions; one view when named. |
| `columns` | table, required | `information_schema.columns` | One table's columns: name, type, nullability, ordinal position, default. |
| `indexes` | table, required | `information_schema.table_constraints`, `key_column_usage` | Constraints and the columns each side names. |
| `foreign-keys` | table, required | `information_schema.referential_constraints` | Referential constraints. |
| `table-storage-metrics` | table, required | `information_schema.table_storage_metrics`, `information_schema.tables` | One table's billed storage: active, time travel, failsafe and clone-retained bytes, plus the row count, clustering key and kind `tables` reports. |
| `databases` | — | `information_schema.databases` | The databases in the account, with owner and transient flag. |
| `schemas` | — | `information_schema.schemata` | The schemas in a database — Snowflake's namespace level above a table. `--database` names the database to enumerate. |
| `warehouses` | — | `SHOW WAREHOUSES` | Warehouses with size, state and auto-resume. This is `SHOW`, not an `information_schema` view, because no such view exists. |
| `database` | — | `CURRENT_DATABASE()`, `CURRENT_VERSION()` | The database this session is in and the account's version. |

`NAME` is required for `columns`, `indexes`, `foreign-keys` and
`table-storage-metrics`. For `views` it is optional: a name asks for that one
view, and a name the catalogue does not have exits 1. The list types —
`tables`, `database`, `databases`, `schemas` and `warehouses` — take no name,
and a stray one is refused (exit 2) rather than ignored: this backend has no
`get_*_info` method that could answer for a single database, schema or
warehouse. `schemas --database analytics` is unaffected — `--database` says
which database's schemas to enumerate, not which schema to fetch.

Exit codes follow that split: **1** is a runtime failure (connection, query,
unexpected) and also "the named view or table is not there"; **2** is a request
this backend cannot serve — a type whose capability switch is off, or a `NAME`
on a list type.

Two absences worth naming:

*   **No `triggers` type.** Snowflake has no triggers, so there is no object to
    ask about. That is an engine fact, not a gap in the CLI.
*   **No `partition-metadata` type.** The dialect carries a formatter for it,
    but no introspector method reads it, so there is no answer behind the type.

`table-storage-metrics` is a type of its own rather than a column of `tables`
for two reasons. Its statement joins two views, so folding it into the listing
would charge every list for that join. And `TABLE_STORAGE_METRICS` returns no
rows for roles other than `ACCOUNTADMIN`, so an empty answer means "no metrics
for this role" — a `None` the command can state out loud, which a column on the
listing could not. An exit of 1 on this type is therefore **not** "the table
does not exist".

## Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `-o, --output` | `table` | `table` (rich), `json`, `csv`, `tsv`. |
| `--account` | `SNOWFLAKE_ACCOUNT` | Account identifier. |
| `--host`, `--port` | _None_ | Connection endpoint, when not using the account locator. |
| `--database` | `SNOWFLAKE_DATABASE` | Database to connect to. |
| `--schema` | `SNOWFLAKE_SCHEMA` | Schema to connect to; introspection reads it. Defaults to `PUBLIC`. |
| `--warehouse` | `SNOWFLAKE_WAREHOUSE` | Warehouse to run queries on. |
| `--role` | `SNOWFLAKE_ROLE` | Role to assume. |
| `--user`, `--password` | env | Credentials. |
| `--authenticator` | _None_ | How the user is authenticated. |
| `--use-async` | off | Drive the asynchronous backend. |

## Notes

*   **Read-only.** `introspect` never writes. It does not create, drop, or
    alter anything, so it is safe to run against an account whose schema
    matters.
*   **The warehouse matters.** Snowflake needs one to run a query. If the role's
    default warehouse is not set, pass `--warehouse`; a missing warehouse is a
    connection failure, not an empty answer.
*   **`SHOW WAREHOUSES` has no `information_schema` counterpart.** It also
    caps its output, and its column names come back lower case — both are
    recorded next to the query in the source rather than assumed here.
*   **Nothing here was run against a live account.** The statements are written
    from the official documentation (cited beside each one in the source).
    Verify the first run against your account before relying on the shapes.
*   **One question per invocation.** A CLI process is one connection that
    opens, answers, and closes — there is no cache carried between runs.
*   **No `status` subcommand.** This backend implements no status
    introspector — there is no `AbstractStatusIntrospector` implementation
    under `introspection/` — so the CLI has no `status` command to wire up.
    That is a missing library capability, not a forgotten command: `info`
    reports the version and the protocol/capability matrix instead. Aligning
    the backends on `status` starts in the library, not here.

## Examples

```bash
# Account-level objects, which Snowflake has and most engines do not
python -m rhosocial.activerecord.backend.impl.snowflake introspect databases
python -m rhosocial.activerecord.backend.impl.snowflake introspect schemas --database analytics
python -m rhosocial.activerecord.backend.impl.snowflake introspect warehouses -o json

# One table's storage facts
python -m rhosocial.activerecord.backend.impl.snowflake introspect table-storage-metrics orders --schema public --database analytics
```
