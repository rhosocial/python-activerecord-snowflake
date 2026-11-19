# query/relation tests (snowflake bridge)

Snowflake bridge for the shared `feature/query/relation` testsuite topic,
mirroring the sqlite bridge tree at `feature/query/relation`.

- `conftest.py` — star-imports `testsuite.feature.query.relation.conftest`.
- `core/` — backend-local relation unit tests (carried over with the bridge
  tree; they exercise core relation machinery and need no database of their
  own).
- `ordering/` — bridge to `testsuite.feature.query.relation.ordering` plus the
  backend-local `with_()` ordering unit test.
- `legacy/` — the real-database `with_()` integration tests carried over from
  the old `query/relations` group, with a self-contained L2 conftest whose DDL
  is built from the dialect-neutral expression API. Under fakesnow the
  emulator's capability probes skip the cases it cannot reproduce.

This directory contains only bridge/topic tests. Snowflake's own backend test
tree under `feature/backend/` is untouched by the restructure.
