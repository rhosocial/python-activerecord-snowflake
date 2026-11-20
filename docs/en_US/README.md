# rhosocial-activerecord Snowflake Backend Documentation

This documentation describes the Snowflake backend only. It assumes you already
know ActiveRecord itself; for models, relations, events, and the query builder,
see the [core library documentation](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US).

> ⚠️ **Async is experimental.** `snowflake-connector-python` has no native async
> API, so `AsyncSnowflakeBackend` is a thread-pool wrapper with no performance
> benefit. **Do not use it in production.** Use the synchronous `SnowflakeBackend`.

## Table of Contents

1. **[Introduction](introduction/overview.md)**
    *   **[Overview](introduction/overview.md)**: what this backend is, and why a hosted warehouse changes the rules
    *   **[Capability boundaries & fail-fast](introduction/capability_boundaries.md)**: how `supports_*` gates work here

2. **[Installation & Configuration](installation/installation.md)**
    *   **[Installation guide](installation/installation.md)**: pip install, dependencies, Python versions
    *   **[Connection configuration](installation/configuration.md)**: account, warehouse, database, schema, role, authentication, environment variables

3. **[Snowflake-Specific Features](features/naming.md)**
    *   **[Three-part naming & identifiers](features/naming.md)**: `database.schema.table`, quoting, `%s` placeholders
    *   **[VARIANT & ARRAY](features/semi_structured.md)**: semi-structured types, path access, casts, adapters
    *   **[Time travel](features/time_travel.md)**: `AT` / `BEFORE`, points, retention
    *   **[MERGE & upsert](features/merge.md)**: conditional upserts, `INSERT OVERWRITE`, no `RETURNING`

4. **[Querying](querying/datetime.md)**
    *   **[Date and time differences](querying/datetime.md)**: `seconds_between` and `date_diff` in Snowflake SQL

5. **[Introspection](introspection/README.md)**
    *   **[Database introspection](introspection/README.md)**: what this backend answers, what it declines, and the CLI

6. **[Testing](testing/README.md)**
    *   **[Test configuration](testing/README.md)**: unit, mock, protocol and integration tiers; credentials; CI

> 📖 **Core Library Documentation**: for the complete framework reference, see
> [rhosocial-activerecord docs](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US).
