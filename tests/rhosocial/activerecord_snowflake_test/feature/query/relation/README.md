# query/relation tests (snowflake bridge)

Snowflake bridge for the shared `feature/query/relation` testsuite topic,
mirroring the sqlite bridge tree at `feature/query/relation`.

- `conftest.py` — star-imports `testsuite.feature.query.relation.conftest`.
- `ordering/` — bridge to `testsuite.feature.query.relation.ordering`.

Core-local unit tests (relation core unit tests, the `legacy/` real-SQLite
`with_()` integration tests, and the `with_()` ordering unit test) were
carried over with the bridge tree by mistake and have been removed: they are
not testsuite bridges and reference core's SQLite implementation
(`aiosqlite` / `AsyncSQLiteBackend` / `SQLiteDialect`), which breaks CI
collection on this backend.

This directory contains only bridge/topic tests. Snowflake's own backend test
tree under `feature/backend/` is untouched by the restructure.
