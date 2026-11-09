# `introspect` — Snowflake metadata, from the command line

The `introspect` subcommand asks a live Snowflake account what it holds, and
prints the answer. Every question runs through the backend's introspector, so
what the CLI reports is what the library sees — the same objects, the same
types, the same parsing — rather than a second implementation that can drift
from it. Twenty-six types are advertised, derived from `_TYPE_CAPABILITIES` in
the source rather than written out a second time, so a family cannot be
answerable and unaskable at once.

```bash
python -m rhosocial.activerecord.backend.impl.snowflake introspect <TYPE> [NAME] [OPTIONS]
```

## What it can ask about

Twenty-six types, in the order `--help` prints them. The catalogue families
answer True for this dialect; the operational and one-object families are
offered and gated on their switch, so a run is refused (exit 2) rather than
answered with an empty list.

| Type | `NAME` | Reads | Notes |
| :--- | :--- | :--- | :--- |
| `tables` | — | `information_schema.tables` | Tables, with the kind the catalogue reports and their comment. |
| `views` | view, optional | `information_schema.views` | Views, with their definitions; one view when named. |
| `columns` | table, required | `information_schema.columns` | One table's columns: name, type, nullability, ordinal position, default, and whether the value is identity- or sequence-generated. |
| `indexes` | table, required | `information_schema.table_constraints`, `key_column_usage` | Constraints and the columns each side names. |
| `foreign-keys` | table, required | `information_schema.referential_constraints` | Referential constraints. |
| `database` | — | `CURRENT_DATABASE()`, `CURRENT_VERSION()` | The database this session is in and the account's version. |
| `databases` | — | `information_schema.databases` | The databases in the account, with owner and transient flag. |
| `schemas` | — | `information_schema.schemata` | The schemas in a database — Snowflake's namespace level above a table. `--database` names the database to enumerate. |
| `warehouses` | — | `SHOW WAREHOUSES` | Warehouses with size, state and auto-resume. This is `SHOW`, not an `information_schema` view, because no such view exists. |
| `table-storage-metrics` | table, required | `information_schema.table_storage_metrics`, `information_schema.tables` | One table's billed storage: active, time travel, failsafe and clone-retained bytes, plus the row count, clustering key and kind `tables` reports. |
| `routines` | — | `information_schema.functions`, `information_schema.procedures` | Functions and stored procedures as one family: language, argument signature, return type, owner and comment. |
| `sequences` | — | `information_schema.sequences` | Standalone sequences: type, start, increment, next value, ordered property and owner. This is not the identity answer; that is on `columns`. |
| `stages` | — | `information_schema.stages` | Named stages with their URL, region and type. |
| `file-formats` | — | `information_schema.file_formats` | Named file formats with their delimiters, formats and compression. |
| `pipes` | — | `information_schema.pipes` | Pipes with the COPY definition, auto-ingest flag and pattern. |
| `tasks` | — | `SHOW TASKS` | Tasks with schedule, state, definition, predecessors and overlap policy. Scoped with `IN SCHEMA` when a schema is set. |
| `streams` | — | `SHOW STREAMS` | Streams with source table, type, mode, staleness and `stale_after`. |
| `unused-indexes` | — | refused here | Offered and gated: `supports_unused_indexes_detection` answers False here, so the run is refused rather than answered empty. |
| `table-stats` | — | refused here | Offered and gated on `supports_table_stats`, which answers False here. |
| `runtime` | — | refused here | Offered and gated on `supports_runtime_stats`, which answers False here. |
| `index-stats` | — | refused here | Offered and gated on `supports_index_stats`, which answers False here. |
| `dependencies` | object, optional | refused here | Offered and gated on `supports_object_dependencies` (False here); a name narrows the graph to that object's edges. |
| `ddl` | table, required | refused here | Offered and gated on `supports_ddl_extraction` (False here). |
| `column-profiles` | table, required | the rows themselves | Answers True here: the profile is aggregated from the rows, so every figure is exact and paid for in time. |
| `value-samples` | table, required | the rows themselves | Answers True here, read from the rows; `--column` names the column and `--limit` caps the count (default 100). |
| `join-coverage` | left table, required | the rows themselves | Answers True here: how much two columns' value domains overlap. `--column`, `--right-table` and `--right-column` are required. |

`NAME` is required for `columns`, `indexes`, `foreign-keys`,
`table-storage-metrics`, `ddl`, `column-profiles`, `value-samples` and
`join-coverage`. For `views` and `dependencies` it is optional: a name asks for
that one view, or narrows the graph to that object's edges. The list types —
`tables`, `database`, `databases`, `schemas`, `warehouses`, `routines`,
`sequences`, `stages`, `file-formats`, `pipes`, `tasks`, `streams`,
`unused-indexes`, `table-stats`, `runtime` and `index-stats` — take no name,
and a stray one is refused (exit 2) rather than ignored: this backend has no
`get_*_info` method that could answer for a single database, schema, routine,
sequence, stage, file format, pipe, task or stream. `schemas --database
analytics` is unaffected — `--database` says which database's schemas to
enumerate, not which schema to fetch.

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

The nine families beyond the catalogue are offered for a different reason than
the ten above: they are questions the *protocol* asks every dialect, and
Snowflake's answer is a real answer, not a gap. Six of them — `unused-indexes`,
`table-stats`, `runtime`, `index-stats`, `dependencies` and `ddl` — are gated on
a switch that answers `False` here, so asking them exits 2 with "not supported by
this server"; the remaining three (`column-profiles`, `value-samples`,
`join-coverage`) read the rows themselves and answer True. Offering a gated type
at all is the point: the dialect's answer is "this engine cannot tell you",
which is a fact worth letting a caller ask for and be told, and is not the same
as an empty list that would read as "it has none".

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
| `--column` | _None_ | The column a `value-samples` or `join-coverage` question is about. |
| `--right-table`, `--right-column` | _None_ | The right-hand side of a `join-coverage` question. |
| `--limit` | `100` | How many values `value-samples` lists when not given. |
| `--include-system` | off | Include the objects the system itself owns. |

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

# The schema objects beyond tables and views
python -m rhosocial.activerecord.backend.impl.snowflake introspect routines --schema public --database analytics
python -m rhosocial.activerecord.backend.impl.snowflake introspect sequences --schema public --database analytics
python -m rhosocial.activerecord.backend.impl.snowflake introspect stages --schema public --database analytics
python -m rhosocial.activerecord.backend.impl.snowflake introspect file-formats --schema public --database analytics
python -m rhosocial.activerecord.backend.impl.snowflake introspect pipes --schema public --database analytics
python -m rhosocial.activerecord.backend.impl.snowflake introspect tasks --schema public --database analytics
python -m rhosocial.activerecord.backend.impl.snowflake introspect streams --schema public --database analytics

# What the rows hold, not what the columns declare -- read from the rows, so exact and paid for
python -m rhosocial.activerecord.backend.impl.snowflake introspect column-profiles orders
python -m rhosocial.activerecord.backend.impl.snowflake introspect value-samples orders --column status --limit 50
python -m rhosocial.activerecord.backend.impl.snowflake introspect join-coverage orders --column buyer_id --right-table customers --right-column id

# Questions this dialect declines -- exit 2, "not supported by this server", not an empty list
python -m rhosocial.activerecord.backend.impl.snowflake introspect unused-indexes
python -m rhosocial.activerecord.backend.impl.snowflake introspect dependencies
```
