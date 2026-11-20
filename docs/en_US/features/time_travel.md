# Time travel

Snowflake keeps historical versions of table data, so a `SELECT` can read a
table as it stood at an earlier point. The backend renders `AT` / `BEFORE`
clauses through the same hook the shared named-relation renderer uses, which
keeps the time-travel suffix separate from the three-part object name.

## Supported points

`supports_time_travel()` is `True`. A point is a `(kind, value)` pair:

| Keyword | Kind | Example SQL |
|---------|------|-------------|
| `AT` | `TIMESTAMP` | `AT(TIMESTAMP => '2024-01-01 00:00:00')` |
| `AT` | `OFFSET` | `AT(OFFSET => -60)` |
| `AT` | `STATEMENT` | `AT(STATEMENT => '01a2b3c4-...')` |
| `BEFORE` | `TIMESTAMP` | `BEFORE(TIMESTAMP => '2024-01-01 00:00:00')` |
| `BEFORE` | `STATEMENT` | `BEFORE(STATEMENT => '01a2b3c4-...')` |

`OFFSET` counts seconds and is emitted as an unquoted integer. `TIMESTAMP` and
`STATEMENT` are literals: the value is escaped and quoted. Only one point is
allowed per relation; two points raise `UnsupportedFeatureError` with a
suggestion, because Snowflake accepts one time-travel point per relation.

The clause is appended **after** the relation reference:

```sql
SELECT * FROM "MYDB"."APP"."events" AT(OFFSET => -60);
```

A qualifier such as `"MYDB"."APP"."events"` and the `AT(...)` suffix are
rendered by different code paths — see [Three-part naming & identifiers](naming.md).

## Why not the SQL-standard form

Snowflake does not speak the generic `FOR SYSTEM_TIME AS OF` syntax, so this
dialect deliberately does **not** claim the core temporal-table protocol. It
implements its own `SnowflakeTimeTravelSupport` protocol and renders Snowflake's
own `AT` / `BEFORE` keywords. Passing a different keyword raises
`UnsupportedFeatureError` rather than emitting invalid SQL.

## Retention limits

A time-travel read can only reach data still within the table's retention
window:

- **Standard edition**: 1 day.
- **Enterprise edition**: up to 90 days, configurable per table/account.

These are account/edition facts, not capability gates in the backend — a probe
answering `True` means the clause can be rendered, not that your retention
window covers the point you asked for. A read beyond retention fails at
execution.

## Shared point definitions

The same `(kind, value)` point shape is used by stream DDL in this backend, so
one definition can describe both a time-travel read and the point from which a
stream starts tracking changes.

## Next steps

- [VARIANT & ARRAY](semi_structured.md)
- [MERGE & upsert](merge.md)
