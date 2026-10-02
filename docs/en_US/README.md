# rhosocial-activerecord Snowflake Backend Documentation

The Snowflake backend is the Snowflake backend implementation for
[rhosocial-activerecord](https://github.com/rhosocial/python-activerecord). It uses the
`snowflake-connector-python` driver. Snowflake organizes objects into
`<database>.<schema>.<object>`, and it is the only backend in this project where the
`schema` is a distinct namespace level rather than another name for the database.

## Table of Contents

- **[Schema Namespaces](snowflake_specific_features/schema_namespace.md)**: declaring
  `__schema_name__`, three-part column references, aliasing, `CURRENT_SCHEMA()`,
  `SEARCH_PATH`, and the limits of single-level qualification

## Key facts at a glance

| Question | Answer |
|---|---|
| What does `schema_name` mean? | A schema inside a database — a distinct level |
| Qualified table renders as | `"app"."orders"` |
| Column references | Three parts on unaliased ranges: `"app"."orders"."id"` |
| After an alias | `"o"."id"` |
| Current schema | `CURRENT_SCHEMA()` |
| `CREATE SCHEMA` / `DROP SCHEMA` | Supported |
| `AUTHORIZATION` on schema DDL | Not supported |

## Related documentation

- **[Schema Namespaces (core guide)](https://github.com/rhosocial/python-activerecord/tree/docs/docs/modeling/schema_namespace.md)**:
  the dialect-independent rules that every backend shares

---

> ⚠️ **Dependency note**: this backend depends on the core library
> `rhosocial-activerecord`. Install it together with the core library rather than
> independently.