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

| Type | Reads | Notes |
| :--- | :--- | :--- |
| `tables` | `information_schema.tables` | Tables, with the row count, clustering key and auto-clustering flag the view reports. |
| `views` | `information_schema.views` | Views, with their definitions. |
| `table` | several | One table by name, with its columns, indexes and foreign keys filled in. |
| `columns` | `information_schema.columns` | One table's columns: name, type, nullability, ordinal position, default. |
| `indexes` | `information_schema.table_constraints`, `key_column_usage` | Constraints and the columns each side names. |
| `foreign-keys` | `information_schema.referential_constraints` | Referential constraints. |
| `databases` | `information_schema.databases` | The databases in the account, with owner and transient flag. |
| `schemas` | `information_schema.schemata` | The schemas in a database — Snowflake's namespace level above a table. |
| `warehouses` | `SHOW WAREHOUSES` | Warehouses with size, state and auto-resume. This is `SHOW`, not an `information_schema` view, because no such view exists. |
| `database` | `CURRENT_DATABASE()`, `CURRENT_VERSION()` | The database this session is in and the account's version. |

`NAME` is required for `table`, `columns`, `indexes` and `foreign-keys`. The
list types take no name.

## Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `-o, --output` | `table` | `table` (rich), `json`, `csv`, `tsv`. |
| `--account` | `SNOWFLAKE_ACCOUNT` | Account identifier. |
| `--host`, `--port` | _None_ | Connection endpoint, when not using the account locator. |
| `--database` | `SNOWFLAKE_DATABASE` | Database to connect to. |
| `--schema` | `SNOWFLAKE_SCHEMA` | Schema to read. |
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

## Examples

```bash
# Account-level objects, which Snowflake has and most engines do not
python -m rhosocial.activerecord.backend.impl.snowflake introspect databases
python -m rhosocial.activerecord.backend.impl.snowflake introspect schemas --database analytics
python -m rhosocial.activerecord.backend.impl.snowflake introspect warehouses -o json

# One table's storage facts
python -m rhosocial.activerecord.backend.impl.snowflake introspect tables --schema public --database analytics
```
