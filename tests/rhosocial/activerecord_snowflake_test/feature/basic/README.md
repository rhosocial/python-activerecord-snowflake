# `basic` scope wiring — Snowflake

This directory mirrors the shared `testsuite/feature/basic` scope with thin
bridge files (`from rhosocial.activerecord.testsuite.feature.basic.<dir>... import *`).
There is **one copy of every test** — the test bodies live only in the testsuite.

## Not-yet-introduced directories

The testsuite `basic` scope also defines the directories below. Their test
modules are retained in the testsuite (the single source of truth); this
backend deliberately does **not** provide bridge files for them yet. This is a
record of "not enabled here", not a claim that Snowflake lacks the feature —
several of the observed failures come from the `fakesnow` (DuckDB) emulator
used when no real Snowflake account is configured, not from the backend itself.

| Directory | Observed when temporarily bridged | Why not introduced |
|-----------|-----------------------------------|--------------------|
| `bulk_crud/` | fails under `fakesnow` (e.g. `test_delete_all_no_matches`) | The backend implements `bulk_insert`; the failure is emulator fidelity (DuckDB cannot reproduce the contract). Needs a real Snowflake account, or emulator-compatible skips, before the contract gives a meaningful signal. |
| `crud_composite_pk/` | fails under `fakesnow` (e.g. `test_is_new_record_any_pk_none`) | Snowflake does not enforce PRIMARY KEY constraints, and the emulator cannot reproduce the shared suite's composite-key identity expectations. Needs a backend-specific contract adaptation rather than a blanket skip. |
| `transaction/` | 0 failed, 16 skipped — all skip with "AsyncSnowflakeBackend incompatible with fakesnow" | The whole scope skips under the emulator, so wiring it adds no signal. Snowflake does support savepoints; the skip is emulator-driven. Revisit once a real account is used. |
| `worker/` | fails under `fakesnow` (e.g. `test_multiple_pools_sequential`) | Multi-process worker-pool lifecycle cannot be validated against the DuckDB emulator. Needs a real Snowflake account. |

Introducing any of these is future work: add the bridge files, reconcile the
shared contract with the backend/emulator (via the capability skips in this
directory's `conftest.py` or a backend-specific expectation), and confirm green
against both `fakesnow` and a real account.
