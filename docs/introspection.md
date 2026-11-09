# Database Introspection

The Snowflake backend answers three layers of questions: what the account declares (from `INFORMATION_SCHEMA` and `SHOW`), what its account-level objects are (databases, schemas, warehouses, storage), and what a table's rows hold (three data families). `backend.introspector` is the entry point for all three, and every answer on this page is Snowflake's own: what this backend says about the account it is connected to, not the shape a cross-dialect consumer can expect.

## Overview

The introspection system is available via `backend.introspector` and answers:

- **Database information**: the database the session is connected to, and its version
- **Account objects**: every database the role can see, a database's schemas, and the virtual warehouses
- **Table information**: tables, views, and every table kind Snowflake's catalogue reports
- **Column information**: name, position, nullability, default, comment, and a composed type including its size
- **Index information**: primary-key and unique constraints, which are as close to an index as this engine has
- **Foreign-key information**: referenced table, column mapping, and the update/delete rules the catalogue declares
- **View information**: definition, check option, updatability
- **Routine information**: stored procedures and user-defined functions, with language, argument signature, return type, owner and comment
- **Sequence information**: standalone sequences, with start, increment, next value and ordered property
- **Catalog objects**: named stages, file formats, pipes, tasks and streams, each with its owning role and engine-specific facts
- **Storage information**: the four billed storage tiers of one table, and the total that fills a table record's `size_bytes`
- **Data answers**: per-column profiles, value listings, and two columns' domain overlap

Snowflake has no trigger object, so the trigger family answers `False` rather than pretending an empty list is an answer. It also keeps no per-column distribution catalogue and no counter relations of the shape the operational families need, which is why six of those families are declined here instead of guessed.

## What Snowflake Answers

Every question in the introspection contract has a probe on the dialect, and a probe is a question about the server in front of you rather than about the product. This table is Snowflake's answer to every probe the families use. Read the `False` rows first: a probe that answers `False` says the question cannot be asked of this server, never that the answer was empty or zero.

Ten catalogue families answer `True` among the original set -- the ten catalogue types the CLI offered before the catalog-object work -- and so do the three data families. Seven more answer `True` as of this change: `routines`, `sequences`, `stages`, `file-formats`, `pipes`, `tasks` and `streams`. Two further switches answer `True`: `supports_introspection()`, the umbrella every scope is gated on, and `supports_table_storage_introspection()`, which fills one table record's `size_bytes` rather than backing a CLI type of its own.

| Probe | Snowflake answers | The question it gates |
|-------|-------------------|-----------------------|
| `supports_introspection()` | `True` | Anything about the schema at all |
| `supports_database_info()` | `True` | The database the session is connected to |
| `supports_database_introspection()` | `True` | Every database in the account |
| `supports_schema_introspection()` | `True` | One database's schemas |
| `supports_warehouse_introspection()` | `True` | The account's virtual warehouses |
| `supports_table_introspection()` | `True` | Tables, views and the vendor table kinds |
| `supports_column_introspection()` | `True` | Columns and what they declare |
| `supports_index_introspection()` | `True` | Primary-key and unique constraints |
| `supports_foreign_key_introspection()` | `True` | Foreign keys and their rules |
| `supports_view_introspection()` | `True` | Views and their definitions |
| `supports_routine_introspection()` | `True` | Stored procedures and user-defined functions |
| `supports_sequence_introspection()` | `True` | Standalone sequences |
| `supports_stage_introspection()` | `True` | Named stages |
| `supports_file_format_introspection()` | `True` | Named file formats |
| `supports_pipe_introspection()` | `True` | Pipes |
| `supports_task_introspection()` | `True` | Tasks, from `SHOW TASKS` |
| `supports_stream_introspection()` | `True` | Streams, from `SHOW STREAMS` |
| `supports_table_storage_introspection()` | `True` | One table's `size_bytes` slot |
| `supports_table_storage_metrics()` | `True` | Billed storage, row count and clustering of one table |
| `supports_column_data_profile()` | `True` | What each column of a table holds |
| `supports_column_value_sample()` | `True` | Which values occur, and how often |
| `supports_join_coverage()` | `True` | How much two columns' domains overlap |
| `supports_trigger_introspection()` | `False` | Triggers |
| `supports_unused_indexes_detection()` | `False` | Indexes with no recorded access |
| `supports_table_stats()` | `False` | Per-table usage counters |
| `supports_runtime_stats()` | `False` | Live runtime facts |
| `supports_index_stats()` | `False` | Per-index usage counters |
| `supports_object_dependencies()` | `False` | The declared object dependency graph |
| `supports_ddl_extraction()` | `False` | The text that recreates an object |
| `supports_ddl_extraction_native()` | `False` | Whether that text is the engine's own |
| `supports_partition_info()` | `False` | Core's partition family |
| `supports_extensions()` | `False` | Installed add-on components |

The answers most easily mistaken for a gap in this backend, rather than a property of the engine, are triggers and the operational set.

`supports_trigger_introspection()` is `False` because Snowflake has no trigger object to ask about. The dialect still has a trigger formatter -- it renders a statement that cannot match a row (`SELECT 1 WHERE 1 = 0`) -- so a caller that ignores the probe receives an empty listing from a real statement rather than an error. The probe is the answer, though: the question has no answer because the object does not exist. The CLI does not offer a `triggers` type at all.

The operational families -- `unused-indexes`, `table-stats`, `runtime` and `index-stats` -- read counters of a shape this engine does not publish to a session: per-index access counts and per-table I/O counters. `dependencies` needs a declared edge catalogue, and Snowflake's catalogue does not record which view, task or stage mentions which table. `ddl` needs the engine's own retained text for an object; this backend reads no such text and refuses to assemble one, because an assembled `CREATE` would read as authoritative while being this library's guess. `ddl_extraction_native` is `False` for the same reason. All six switches are constants on this dialect: unlike a feature that appears in a later release, these answers do not vary by server version.

`supports_partition_info()` stays `False` by inheritance. Snowflake's own partition questions live under their own switches, and `supports_partition_metadata_introspection()` answers `False` because the dialect has a formatter for the family but no introspector method reads it. The CLI excludes `partition-metadata` for that reason, rather than offering a type with no answer behind it.

`supports_extensions()` is `False` because this backend declares no catalogue mapping for add-on components, so there is nothing to answer a `True` with.

`supports_index_introspection()` is `True` even though Snowflake has no traditional index: the index family is answered from primary-key and unique constraints, so the question "what indexes does this table have" has an answer in the only vocabulary this engine has. Each record reports `index_type` as `UNKNOWN` -- the catalogue names a constraint kind, not an access method -- and carries `is_unique=True` with `is_primary` set for the primary key.

## Basic Usage

### Accessing the Introspector

```python
from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend

backend = SnowflakeBackend(
    account="myaccount",
    database="mydb",
    schema="PUBLIC",
    username="user",
    password="secret",
    warehouse="COMPUTE_WH",
)
backend.connect()

introspector = backend.introspector
```

### Sync and async

The async backend exposes the same method names, awaited:

```python
from rhosocial.activerecord.backend.impl.snowflake.backend.async_backend import (
    AsyncSnowflakeBackend,
)

backend = AsyncSnowflakeBackend(account="myaccount", database="mydb", username="user")
await backend.connect()

tables = await backend.introspector.list_tables()
```

`SnowflakeIntrospector` and `AsyncSnowflakeIntrospector` are separate classes that cannot coexist. They share every parser through `SnowflakeIntrospectorMixin`, so a record has the same shape on both sides; only the executor differs -- the async side runs the synchronous driver's cursor operations in a thread pool, because `snowflake-connector-python` has no native async API.

### Cache Management

Answers are cached by scope. The account-level questions share scopes with the schema questions, so they carry an `extra` discriminator in their cache keys and cannot serve each other's answers:

```python
backend.introspector.clear_cache()

from rhosocial.activerecord.backend.introspection.types import IntrospectionScope

backend.introspector.invalidate_cache(scope=IntrospectionScope.TABLE, name="orders")
```

One absence is deliberately not cached: a `None` from `get_table_storage_metrics()` may be a permission that could be granted tomorrow, and caching a permission-shaped `None` would outlive the permission.

## Catalogue Families

Each of these is one catalogue read, or one `SHOW` for warehouses. None scans the user's rows.

| Family | Method | Snowflake source |
|--------|--------|------------------|
| Tables | `list_tables()` | `INFORMATION_SCHEMA.TABLES` |
| Views | `list_views()`, `get_view_info()` | `INFORMATION_SCHEMA.VIEWS` |
| Columns | `list_columns()` | `INFORMATION_SCHEMA.COLUMNS` |
| Indexes | `list_indexes()` | `INFORMATION_SCHEMA.TABLE_CONSTRAINTS` + `KEY_COLUMN_USAGE` |
| Foreign keys | `list_foreign_keys()` | `REFERENTIAL_CONSTRAINTS` + `KEY_COLUMN_USAGE` + `TABLE_CONSTRAINTS` |
| Database | `get_database_info()` | `CURRENT_DATABASE()`, `CURRENT_VERSION()` |
| Databases | `list_databases()` | `SNOWFLAKE.INFORMATION_SCHEMA.DATABASES` |
| Schemas | `list_schemas()` | `INFORMATION_SCHEMA.SCHEMATA` |
| Warehouses | `list_warehouses()` | `SHOW WAREHOUSES` |
| Storage metrics | `get_table_storage_metrics()` | `TABLE_STORAGE_METRICS` joined to `TABLES` |
| Routines | `list_routines()` | `INFORMATION_SCHEMA.FUNCTIONS` + `PROCEDURES` |
| Sequences | `list_sequences()` | `INFORMATION_SCHEMA.SEQUENCES` |
| Stages | `list_stages()` | `INFORMATION_SCHEMA.STAGES` |
| File formats | `list_file_formats()` | `INFORMATION_SCHEMA.FILE_FORMATS` |
| Pipes | `list_pipes()` | `INFORMATION_SCHEMA.PIPES` |
| Tasks | `list_tasks()` | `SHOW TASKS` |
| Streams | `list_streams()` | `SHOW STREAMS` |

### Tables and views

The listing projects `TABLE_NAME`, `TABLE_TYPE` and `COMMENT`, filtered by `TABLE_SCHEMA`. The record keeps the catalogue's own word in `extra["snowflake_table_type"]` on every row -- not only for the vendor kinds -- because a caller filtering on `"ICEBERG TABLE"` needs the spelling the catalogue reported, and a field present only for some rows cannot be filtered on.

The mapping from spelling to core member is one table: base, managed, event, hybrid, Iceberg and dynamic tables all read as `BASE_TABLE`; `VIEW` reads as `VIEW`; `MATERIALIZED VIEW` as `MATERIALIZED_VIEW`; `SYSTEM TABLE`, `TEMPORARY TABLE` and `EXTERNAL TABLE` as their own members. Dynamic tables are deliberately not materialized views: the catalogue distinguishes them, and reporting one as a view would make a "no views" listing return a row whose member says it is a view.

Filtering by `table_type` reads three vocabularies: an exact catalogue spelling selects exactly that spelling, a core `TableType` name expands onto every spelling mapped to it, and an unknown spelling is passed through as a spelling this backend has not learned yet. A core kind the catalogue cannot express -- `FOREIGN_TABLE` or `PARTITIONED_TABLE` -- is rendered as a comparison that cannot hold (`1 = 2`) and answers with no rows, rather than dropping the condition and answering with every table.

`list_tables()` asks with `include_views=True`. The formatter's `include_views=False` branch drops exactly the two view spellings (`VIEW`, `MATERIALIZED VIEW`) and leaves every table kind visible -- it does not narrow to `BASE TABLE`, which would hide the managed, event, Iceberg, hybrid and dynamic kinds. `include_system=False` drops both `information_schema` and `PUBLIC` from the listing, so a table in `PUBLIC` -- the schema a default connection usually works in -- is not in the default answer; `--include-system` (or `include_system=True`) is how a caller asks for it. The values in that predicate are the statement's own, never a caller's.

A view's definition comes from `VIEW_DEFINITION`, with `CHECK_OPTION` and `IS_UPDATABLE` beside it. A view is also a row in `TABLES`, so it can appear in a table listing; `table_type="VIEW"` is how a caller asks for views alone.

### Columns

`INFORMATION_SCHEMA.COLUMNS` gives the bare word in `DATA_TYPE` and the size in a different column depending on the type, so the record carries both: `data_type` is the lower-cased word the catalogue reported, and `data_type_full` is the composed spelling with the size restored.

The composition is per concept, not per family. `CHARACTER_MAXIMUM_LENGTH` is documented in characters of string columns, so it is fed to `VARCHAR`, `CHAR` and sized `TEXT` only, and a bare word with no usable width stays bare. `NUMERIC_PRECISION` and `NUMERIC_SCALE` are fed to `NUMBER` only: the integer names are documented as `NUMBER` synonyms that cannot carry a precision or scale, so composing their reported 38 would turn every `INT` column into `NUMBER(38, 0)`, and `FLOAT`'s reported precision is left alone because neither its unit nor its radix is selected by the query. `BINARY` is deliberately excluded: the manual measures binary lengths in bytes and the selected columns are documented for string columns, so this backend composes no width for it rather than feeding a byte count to a character column.

The other fields are the catalogue's own: `ORDINAL_POSITION`, `IS_NULLABLE` (read as `YES`, everything else is `NOT_NULL`), `COLUMN_DEFAULT`, `COMMENT`, `COLLATION_NAME`, and the raw precision/scale/length columns.

`IS_IDENTITY` answers the auto-increment question. Snowflake documents it as "Whether this column is an identity column", and the identity columns (`IDENTITY_GENERATION`, `IDENTITY_START`, `IDENTITY_INCREMENT`, `IDENTITY_ORDERED`) carry the declared numbers and ordering property. A column whose default is `some_sequence.NEXTVAL` is the second way the database can generate a value; the default text is the only place that fact appears. Both set `is_auto_increment` on the column record, and `extra["snowflake_auto_increment_source"]` says which one it was (`"identity"` or `"sequence_default"`). A column with neither is false. The identity fields are always present in `extra`, so a caller can tell "not an identity" from "identity details not read".

`KIND = 'VIRTUAL_COLUMN'` marks a generated column, and `EXPRESSION` carries the expression that computes it. `is_generated` and `generated_expression` are filled from those two columns; a regular `COLUMN` keeps both unset, whatever text the expression slot happens to contain.

### Routines, sequences and catalog objects

`list_routines()` reads two views because Snowflake stores functions and procedures separately: `INFORMATION_SCHEMA.FUNCTIONS` and `INFORMATION_SCHEMA.PROCEDURES`. The columns are prefixed per view, so the parser reads the prefix off the `kind` it was given, and the two listings are merged and sorted by `(kind, name, argument_signature)`. `argument_signature` is the view's own signature text, which is how overloads are distinguished; `return_type` is `DATA_TYPE`; `language` is the view's `FUNCTION_LANGUAGE` / `PROCEDURE_LANGUAGE`. The engine-specific remainder -- volatility, security, handler, runtime, packages, integrations, secrets -- is in `extra` under the documented uppercase name.

`list_sequences()` projects `INFORMATION_SCHEMA.SEQUENCES` onto core's `SequenceInfo`, with Snowflake's facts in `extra`. `MINIMUM_VALUE`, `MAXIMUM_VALUE` and `CYCLE_OPTION` are documented "Not applicable for Snowflake" and stay `None`; `START_VALUE` and `INCREMENT` are documented `VARCHAR` and are converted to integers. `NEXT_VALUE` is the value the sequence will produce next, not a last-produced value, so it is stored as `extra["snowflake_next_value"]` and `last_value` stays `None`.

Stages, file formats, pipes, tasks and streams share one stable record shape (`SnowflakeCatalogObjectInfo`): name, kind, catalog, schema, owner, comment, created and last altered, with each family's engine-specific columns in `extra`. The first three are database-level Information Schema views; tasks and streams have no such view, so they are read through `SHOW TASKS` / `SHOW STREAMS`, scoped with `IN SCHEMA` when a schema is configured. `SHOW` rows are documented lowercase and are normalized before parsing.

Snowflake identity columns are backed by an internal sequence, but that sequence is not a row in `SEQUENCES` and must not be inferred as one. Conversely, a standalone sequence used as a column default does not make the column an identity column. The two facts are deliberately separate: `list_sequences()` answers "which sequence objects exist", while `list_columns()` answers "is this column's value generated", with `extra` naming the mechanism.

### Indexes and foreign keys

Both families read constraints, because that is the structure Snowflake declares.

The index listing joins `TABLE_CONSTRAINTS` to `KEY_COLUMN_USAGE` on the constraint name and schema, keeps `PRIMARY KEY` and `UNIQUE`, and groups the rows by constraint name into one `IndexInfo` per constraint with its columns in `ORDINAL_POSITION` order. `index_type` is `UNKNOWN`, `is_unique` is `True` for both kinds, and `is_primary` separates them.

The foreign-key listing joins four views: the constraint, its columns, the unique constraint it points at, and that constraint's columns. Both rules are read as the catalogue spells them and mapped onto `ReferentialAction`; an absent rule is `NO_ACTION`, which is the value the catalogue's vocabulary implies when it reports nothing.

### Database, databases, schemas and warehouses

These are four different questions, and the answers keep them apart.

`get_database_info()` reads `CURRENT_DATABASE()` and `CURRENT_VERSION()` in a statement with no `FROM` -- there is no table to read, only a question to ask the session. The version is reported from the dialect or the backend's cached server version, never by opening a second connection; something nothing knows yet is reported as `"unknown"` with the all-zero tuple rather than raising.

`list_databases()` reads every database in the account from `INFORMATION_SCHEMA.DATABASES`, qualified with `SNOWFLAKE` so the statement resolves `INFORMATION_SCHEMA` even when the session has no current database -- the state the CLI is in when it is given an account and no database. The view is privilege-filtered: it shows the objects the session's role may access, so the answer is what the role can see, not a claim of omniscience.

`list_schemas()` reads `SCHEMATA`, which is a database-level view: `database=None` means "the current database" and is a legitimate request, while naming a database qualifies the view with it. A database name is rendered as a quoted identifier, not a bind value -- it is part of an object name -- and quoting is case-sensitive in Snowflake, so a caller passes the catalogue's own spelling.

`list_warehouses()` is a `SHOW`, because there is no `INFORMATION_SCHEMA` view for warehouses. Its output columns are documented lowercase and its flags spell `Y`/`N`, unlike the views' uppercase columns and `'YES'`/`'NO'`, so the parser normalises the keys before reading and reads flags through one helper that accepts `Y`, `YES`, `TRUE`, `1` and a real boolean. `SHOW` rows are not post-processed through `RESULT_SCAN`: that function scans the session's most recent statement, which a cache miss elsewhere could replace, and it fails silently rather than erroring. The driver's cursor description is per-cursor and cannot be displaced. The command returns at most ten thousand records per object type and only objects the role may access; neither is a defect this backend can repair, so neither is hidden.

### Table storage metrics

`get_table_storage_metrics()` asks `TABLE_STORAGE_METRICS` for one live table, joined to `TABLES` for the row count, clustering key and table type that the storage view does not document. The join is `LEFT` because the storage view keeps rows for dropped tables that `TABLES` no longer lists, and the filter keeps the current version only (`TABLE_DROPPED IS NULL`): joining a dropped version would attach the live table's row count to a dead one. `TABLES.BYTES` is deliberately not selected -- it is documented as bytes accessed by a scan, not storage, and a second byte column with a different meaning would invite confusion.

The four billed tiers are `ACTIVE_BYTES`, `TIME_TRAVEL_BYTES`, `FAILSAFE_BYTES` and `RETAINED_FOR_CLONE_BYTES`; their sum is the table's retained footprint and is what `get_table_info()` puts on `size_bytes`. The split slots `data_size_bytes` and `index_size_bytes` stay `None`: storage is managed micro-partition bytes with no index side to attribute them to, which is the engine's shape rather than a missing measurement.

`get_table_storage_metrics()` returns `None` for no row, and that `None` is ambiguous by documentation: the view returns no rows to roles other than `ACCOUNTADMIN`. "The table is gone" and "this role may not see its metrics" cannot be told apart from this view, and the method does not pretend to tell them apart. The CLI exits 1 with a message about absent metrics rather than reporting a missing table.

## Operational Families

None of the six answers here. Each probe is `False`, each is a constant on the dialect, and the CLI refuses the type (exit 2) instead of printing an empty listing.

| Family | Probe | Why this backend declines |
|--------|-------|---------------------------|
| `unused-indexes` | `supports_unused_indexes_detection()` | No per-index access counter of the shape the family reads |
| `table-stats` | `supports_table_stats()` | No per-table I/O counter relation |
| `runtime` | `supports_runtime_stats()` | No live runtime measurement relation in the catalogue the family reads |
| `index-stats` | `supports_index_stats()` | The same missing per-index counters |
| `dependencies` | `supports_object_dependencies()` | No declared edge catalogue recording which object mentions which |
| `ddl` | `supports_ddl_extraction()` | No retained rebuildable text, and no assembly this backend will pass off as native |

The distinction that matters is between `False` and an empty answer. A `False` tells a caller not to ask; an empty list would tell it that the question was asked and nothing was found. An operator reading "no unused indexes" for an engine that keeps no such counter would be reading a report nobody produced.

## Data Families

The three data families measure the rows rather than read a catalogue. Snowflake keeps no per-column distribution a session can read -- `INFORMATION_SCHEMA.COLUMNS` describes what a column *declares*, and the micro-partition metadata that records value ranges for pruning is published nowhere queryable -- so every figure is computed when asked, exact, and paid for in time proportional to the table.

| Family | Method | Price |
|--------|--------|-------|
| Column profiles | `list_column_data_profiles(table)` | One pass over the table per column |
| Value samples | `sample_column_values(table, column, limit=100)` | One grouped pass over the column, plus a sort |
| Join coverage | `estimate_join_coverage(left_table, left_column, right_table, right_column)` | Each side read twice: once for the overlap, once for its denominator |

### Column Profiles

The statement is one `UNION ALL` arm per column of the table, and the column list comes from the introspector's own `list_columns()` call: SQL cannot pivot `SUM(CASE WHEN col IS NULL ...)` across columns it was never told about. Each arm reads the table once, so a table of ten columns is read ten times -- one round trip, ten scans.

The rendered shape, for two columns `code` and `amount`:

```sql
SELECT CAST('code' AS VARCHAR(16777216)) AS "COLUMN_NAME",
       SUM(CASE WHEN "code" IS NULL THEN 1 ELSE 0 END) AS "NULL_COUNT",
       COUNT(DISTINCT "code") AS "DISTINCT_COUNT",
       MIN("code") AS "MIN_VALUE",
       MAX("code") AS "MAX_VALUE",
       COUNT(*) AS "ROW_COUNT",
       CAST('aggregate' AS VARCHAR(16777216)) AS "SOURCE"
FROM "orders"
UNION ALL
SELECT CAST('amount' AS VARCHAR(16777216)) AS "COLUMN_NAME",
       SUM(CASE WHEN "amount" IS NULL THEN 1 ELSE 0 END) AS "NULL_COUNT",
       COUNT(DISTINCT "amount") AS "DISTINCT_COUNT",
       MIN("amount") AS "MIN_VALUE",
       MAX("amount") AS "MAX_VALUE",
       COUNT(*) AS "ROW_COUNT",
       CAST('aggregate' AS VARCHAR(16777216)) AS "SOURCE"
FROM "orders"
```

The counts are exact, and that is a deliberate choice rather than an oversight. `COUNT(DISTINCT ...)` is used where `APPROX_COUNT_DISTINCT` would be cheaper, because `ProfileSource` has no word for a HyperLogLog estimate: `aggregate` says every row was counted and the answer is exact, `sample` says a subset was read and `row_count` says how many, and an estimate over the whole table is neither. Labelling it `aggregate` would claim precision it lacks; labelling it `sample` would claim a subset was read when every row was. The exactness also carries a comparison an estimate would destroy: `distinct_count == row_count` is how a caller recognises a unique column, and that comparison has no tolerance. A table large enough for the exact count to hurt is one whose owner should decide to pay for it, which is why this is a probe and not an automatic pass.

`null_fraction` is derived in the parser (`null_count / row_count`), so a row count that may be zero never has to be guarded in SQL. An empty table answers `null_fraction = None` because `SUM` over no rows is `NULL` -- absence of a measurement, not "no nulls" -- while `distinct_count` and `row_count` are `0`, which are measurements. `source` is projected into every row as the constant `'aggregate'`, not stamped on afterwards, so a consumer comparing profiles across engines can tell what it is reading.

**Identifier casing is the trap.** Snowflake folds an unquoted identifier to upper case, so the projections alias in upper case (`"COLUMN_NAME"`, `"NULL_COUNT"`, `"MIN_VALUE"`, `"SOURCE"`) and the catalogue stores unquoted names upper case too. The result keys arrive upper-cased from the service; the local emulator this repository can run without an account preserves the alias exactly as written, so the same statement can arrive lower-cased there. This backend's three `parse_*` overrides lower-case every row's keys before handing them to core's parser, which is what makes one shape out of two. Values are untouched: only the keys are casing. A row can arrive under either casing, and code that reads `row["NULL_COUNT"]` directly will work against one and not the other.

**One result type per column position.** Snowflake resolves a single type per position across all `UNION ALL` arms, so `MIN_VALUE` -- carrying `code`'s text in one arm and `amount`'s number in another -- can arrive coerced to text. The figures are exact; only the Python type is the union's, which is why a numeric endpoint is read through `Decimal(str(value))`. A future formatter that cast the position instead would trade text endpoints away to make numeric ones prettier.

A column type `MIN`, `MAX` or `COUNT(DISTINCT ...)` refuses -- `VARIANT`, `OBJECT`, `ARRAY` -- fails the whole statement rather than dropping that column's arm, because a silently missing column would be a profile claiming the table has fewer columns than it does.

### Value Samples

A `GROUP BY` over the column plus a sort of the groups: the same order of cost as the profile, which is why the two are separate calls -- a caller wanting only the listing does not pay for the profile's distinct counts and endpoints. `ORDER BY COUNT(*) DESC` is what makes the answer "the most frequent values" rather than "the first values", and ties break by the value so two runs of the same query agree. The limit is a bind parameter, so the caller's integer is never spliced into statement text.

Only `value` and `count` are projected; `frequency` stays `None` because the engine reports a count and the denominator is the row count the profile carries. `GROUP BY` groups `NULL`s, so a column containing `NULL` has an entry whose `value` is `None`, usually the most frequent one; the parser keeps it, and a caller reading the listing as "the values in this column" must not assume every entry is a value.

### Join Coverage

One statement produces both fractions. For each side, the numerator counts the distinct values that also occur on the other side, and the denominator counts that side's distinct non-`NULL` values. `IS NOT NULL` is written on both halves: in the numerator it is load-bearing, because a `DISTINCT` treats `NULL` as one value and counting it would credit a match that can never join; in the divisor `COUNT(DISTINCT ...)` skips `NULL` on its own, but the share is of the values that could join and the statement says so. `NULLIF(..., 0)` makes a column with nothing to match answer `NULL` rather than `0.0`, so "nothing matched" and "nothing to match" stay distinct. Snowflake's `/` over two integers already answers a fractional `NUMBER`, so no `* 1.0` is needed. Collations are not reconciled, so across mismatched collations the fractions are a lower bound, never an upper one.

```python
profiles = backend.introspector.list_column_data_profiles("orders")
for profile in profiles:
    print(profile.column_name, profile.null_fraction, profile.distinct_count,
          profile.row_count, profile.source)

samples = backend.introspector.sample_column_values("orders", "status", limit=20)
for sample in samples:
    print(sample.value, sample.count)    # value is None when NULL is a group

coverage = backend.introspector.estimate_join_coverage(
    "orders", "customer_id",
    "customers", "id",
)
print(coverage.left_coverage, coverage.right_coverage)
```

## What Is Verified, and What Is Not

This section exists because the difference is not visible from the code, and a reader must not infer more than was measured.

**Verified in CI**, on every push to `main`, `release/v**` and `maint/**`, and on every pull request into them:

- the statement each formatter renders -- its text and its bind parameters -- is pinned by unit tests;
- the parser, including both result-key casings, is pinned by unit tests that feed the rows the service and the emulator produce;
- the CLI wiring is pinned: which introspector method each type calls, which argument is required, refused, or forwarded, which exit code each refusal takes, and both the sync and async paths.

**Not verified: the answers.** No statement in this repository has ever been executed against a Snowflake account by this repository's CI. The workflow runs `pytest tests/ -k "not integration" --ignore=tests/snowflake_fakesnow`: there is no Snowflake instance in the job, and even the `fakesnow` (DuckDB) scenario suite is excluded from the run. The tests that do create tables and compare figures against a hand count -- the data-family tests -- need `SNOWFLAKE_ACCOUNT` and related credentials and skip when the scenario configuration is absent, which it is in CI. What is proven here is that the SQL is well-formed and that the parser reads the shape the documentation says comes back; whether Snowflake accepts each statement, whether every view and column exists as documented, and whether the privileges of a given role let it run are open questions this repository has not closed. Treat the statement as reviewed against the vendor's documentation, not as observed behaviour.

## Version and Availability Floors

Every switch in this backend is a constant, so no family is gated on a server version. What gates an answer is a privilege and an account limit, and neither is a version floor:

| Family | Condition | What it looks like |
|--------|-----------|--------------------|
| `table-storage-metrics`, `size_bytes` | Role must be `ACCOUNTADMIN` to see rows | Empty answer; `None` metrics, indistinguishable from a missing table |
| `warehouses` | `SHOW` returns at most 10,000 records per object type | A larger account cannot be fully listed this way; no view exists to fall back on |
| every catalogue family | The role's grants | The engine's own error at execution; the probe said the server can answer, not that this account may ask |

A probe answering `False` is "the question cannot be asked here", not "nothing was used". It does not say that no index was used, that no table was read, or that the database has no dependencies: it says the server cannot be asked. `False` lets a caller take its fallback knowingly; the empty list is reserved for a question that was asked and had nothing to report.

The probes do not test grants. If the connected role may not read a view, the engine's error arrives at execution; the probe answered about the server, not about this account's privileges.

## Command Line Introspection

The backend provides a command-line surface over the same introspector, with one type per family and no type covering two:

```bash
python -m rhosocial.activerecord.backend.impl.snowflake introspect tables \
  --account myaccount --database mydb
```

The invocation requires `--account` and/or `--database`; connection parameters can come from the flags or the environment.

| Parameter | Environment Variable | Description |
|-----------|---------------------|-------------|
| `--account` | `SNOWFLAKE_ACCOUNT` | Account identifier |
| `--host` | `SNOWFLAKE_HOST` | Host, where the account is not enough |
| `--port` | `SNOWFLAKE_PORT` | Port (default: 443) |
| `--database` | `SNOWFLAKE_DATABASE` | Database |
| `--schema` | `SNOWFLAKE_SCHEMA` | Schema (default: `PUBLIC`) |
| `--warehouse` | `SNOWFLAKE_WAREHOUSE` | Virtual warehouse |
| `--role` | `SNOWFLAKE_ROLE` | Role |
| `--user` | `SNOWFLAKE_USER` | Username |
| `--password` | `SNOWFLAKE_PASSWORD` | Password |
| `--authenticator` | `SNOWFLAKE_AUTHENTICATOR` | Authentication method |

### Introspection Types

Twenty-six types. Seventeen are catalogue questions, six are families this backend declines, and three are the data families.

| Type | Description | Name |
|------|-------------|------|
| `tables` | Tables, views and the vendor table kinds | refused |
| `views` | List all views, or describe one | optional (view) |
| `columns` | Column information | required (table) |
| `indexes` | Primary-key and unique constraints | required (table) |
| `foreign-keys` | Foreign-key information | required (table) |
| `database` | The connected database and its version | refused |
| `databases` | Every database the role can see | refused |
| `schemas` | The schemas of `--database`, or the current one | refused |
| `warehouses` | Virtual warehouses | refused |
| `table-storage-metrics` | Billed storage tiers, row count and clustering | required (table) |
| `routines` | Functions and procedures: language, signature, return type, owner | refused |
| `sequences` | Standalone sequences: start, increment, next value | refused |
| `stages` | Named stages: URL, region, type | refused |
| `file-formats` | Named file formats: delimiter, format, compression | refused |
| `pipes` | Pipes: COPY definition, auto-ingest, pattern | refused |
| `tasks` | Tasks: schedule, state, definition, predecessors | refused |
| `streams` | Streams: source table, type, staleness | refused |
| `unused-indexes` | Declined: `False` | refused |
| `table-stats` | Declined: `False` | refused |
| `runtime` | Declined: `False` | refused |
| `index-stats` | Declined: `False` | refused |
| `dependencies` | Declined: `False` | optional (object) |
| `ddl` | Declined: `False` | required (table) |
| `column-profiles` | What each column of a table holds, `source='aggregate'` | required (table) |
| `value-samples` | Most frequent values of one column | required (table) |
| `join-coverage` | Overlap of two columns' value domains | required (left table) |

The six declined types are advertised rather than omitted, and refused at runtime by the switch behind them (exit 2) before the introspector is reached. The advertised list is derived from the same capability map the handler consults, so a family cannot be answerable and unaskable at once.

A `NAME` a type cannot use is refused (exit 2) rather than ignored, and a required one that is missing exits 1 -- a typo and a misfiled question are different failures. `value-samples` also requires `--column`; `join-coverage` requires `--column`, `--right-table` and `--right-column`, with the left table given as `NAME`. `--limit` is forwarded to `sample_column_values()` only when it is given; without it the introspector's own default answers, so the number is not written in two places. A flag the type does not read is refused (exit 2).

The capability gate runs after connecting, in the synchronous path. The asynchronous path (`--use-async`) writes out its own branches and does not consult the gate: a declined type reaches the introspector there instead of exiting 2. The data families' probe answers are what the synchronous gate acts on, and they are what the type list is derived from.

### Querying Operational, Storage and Data Families

```bash
# Storage of one table
python -m rhosocial.activerecord.backend.impl.snowflake introspect table-storage-metrics users \
  --account myaccount --database mydb

# Declined families: exit 2, no query run
python -m rhosocial.activerecord.backend.impl.snowflake introspect ddl orders \
  --account myaccount --database mydb

# The data families
python -m rhosocial.activerecord.backend.impl.snowflake introspect column-profiles orders \
  --account myaccount --database mydb
python -m rhosocial.activerecord.backend.impl.snowflake introspect value-samples orders \
  --column status --limit 20 --account myaccount --database mydb
python -m rhosocial.activerecord.backend.impl.snowflake introspect join-coverage orders \
  --column buyer_id --right-table customers --right-column id \
  --account myaccount --database mydb
```

`column-profiles` prints a note on stderr saying the figures are aggregated from the rows and exact; the note is on stderr so `json`, `csv` and `tsv` stay parseable. Each row also carries `source='aggregate'` itself.

### Output Formats and Async Mode

```bash
python -m rhosocial.activerecord.backend.impl.snowflake introspect tables \
  --account myaccount --database mydb --output json
python -m rhosocial.activerecord.backend.impl.snowflake introspect tables \
  --account myaccount --database mydb --output csv
python -m rhosocial.activerecord.backend.impl.snowflake introspect tables \
  --account myaccount --database mydb --output tsv
python -m rhosocial.activerecord.backend.impl.snowflake introspect tables \
  --account myaccount --database mydb --use-async
```

`table` is the default, and falls back to `json` when the rich renderer is not installed.

## API Reference

### Introspection Methods

| Method | Description |
|--------|-------------|
| `get_database_info()` | The connected database and the known version |
| `list_databases()` | Every database the role can see |
| `list_schemas(database=None)` | A database's schemas, or the current database's |
| `list_warehouses()` | Virtual warehouses, from `SHOW` |
| `list_tables(schema=None, include_system=False, table_type=None)` | Tables, views and vendor table kinds |
| `get_table_info(name, schema=None)` | One table with columns, indexes, foreign keys and `size_bytes` |
| `table_exists(name, schema=None)` | Whether the table is listed |
| `list_columns(table_name, schema=None)` | Column declarations, with the composed type |
| `get_column_info(table_name, column_name, schema=None)` | One column |
| `get_primary_key(table_name, schema=None)` | The primary-key constraint as an index |
| `list_indexes(table_name, schema=None)` | Primary-key and unique constraints |
| `list_foreign_keys(table_name, schema=None)` | Foreign keys with their rules |
| `list_views(schema=None, include_system=False)` | Views |
| `get_view_info(name, schema=None)` | One view's definition |
| `get_table_storage_metrics(table_name, schema=None)` | Billed storage, row count, clustering |
| `list_routines(schema=None)` | Functions and procedures as one family |
| `list_sequences(schema=None)` | Standalone sequences |
| `list_stages(schema=None)` | Named stages |
| `list_file_formats(schema=None)` | Named file formats |
| `list_pipes(schema=None)` | Pipes |
| `list_tasks(schema=None)` | Tasks, from `SHOW TASKS` |
| `list_streams(schema=None)` | Streams, from `SHOW STREAMS` |
| `list_column_data_profiles(table_name, schema=None)` | What each column holds |
| `sample_column_values(table_name, column_name, limit=100, schema=None)` | Most frequent values |
| `estimate_join_coverage(left_table, left_column, right_table, right_column, schema=None)` | Both coverage fractions |
| `clear_cache()` | Clear all cached answers |
| `invalidate_cache(scope, ...)` | Invalidate one scope, or one name |

The operational methods exist on the base introspector and are refused by this dialect's probes; check the probe before calling, and let the `False` be the answer.
