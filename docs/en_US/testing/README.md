# Test configuration

Snowflake is a hosted service, so there is no local server binary to start.
The test suite is layered so that most checks run without credentials, while
the few that need a live account are explicitly marked and skipped when no
configuration is present.

## Test suite composition

1. **Shared testsuite**: feature tests (basic, query, relation, DDL, CLI
   contracts, …) wired in through bridge files under
   `tests/rhosocial/activerecord_snowflake_test/feature/`.
2. **Backend's own tests**: `tests/rhosocial/activerecord_snowflake_test/feature/backend/`
   (dialect and capability contracts, type/adapter tests, DDL tests, introspection
   parsers, fail-fast contracts) plus `tests/core/` and `tests/mock/`.

## Tiers

| Tier | Needs an account? | Examples |
|------|-------------------|----------|
| Unit / dialect | No | dialect formatting, capability probes, config, adapters, type parsing |
| Protocol conformance | No | `supports_*` and `format_*` contract classes |
| Mock / offline CLI | No | mocked connector, `introspect` / `info` offline wiring |
| `fakesnow` scenario | No (local emulator) | DuckDB-based Snowflake emulator tests |
| Integration | **Yes** | real Snowflake connection, data-family figures |

## Running locally

```bash
# Unit and offline tests; PYTHONPATH lets pytest find the provider registry
PYTHONPATH=src:tests pytest tests/ -k "not integration" --ignore=tests/snowflake_fakesnow

# A single feature area
PYTHONPATH=src:tests pytest tests/rhosocial/activerecord_snowflake_test/feature/backend/
```

> Keep local runs targeted. The full suite needs a live account and consumes
> warehouse credits.

## Integration test setup

Create a scenario file (default `tests/config/snowflake_scenarios.yaml`):

```yaml
scenarios:
  my_account:
    account: "YOUR_ACCOUNT"
    username: "YOUR_USER"
    password: "YOUR_PAT_TOKEN"
    warehouse: "COMPUTE_WH"
    role: "SYSADMIN"
    database: "MYDB"
    schema: "PUBLIC"
```

Use a **Programmatic Access Token** rather than a personal password for CI.
Tests skip automatically when no scenario configuration is found.

## Markers

| Marker | Meaning |
|--------|---------|
| `integration` | Requires a real Snowflake instance |
| `requires_protocol` | Requires a specific backend protocol |
| `requires_functions` | Requires specific database functions |
| `snowflake_variant` | `VARIANT` type tests |
| `snowflake_time_travel` | Time-travel tests |
| `fakesnow` | Local Snowflake emulator scenarios |

## What CI verifies — and what it does not

Verified on every push and pull request to the long-lived branches:

- the **statement** each formatter renders — its text and bind parameters — is
  pinned by unit tests;
- the **introspection parsers**, including both result-key casings, are pinned
  against the row shapes the service and the emulator produce;
- the **CLI wiring** is pinned: which introspector method each type calls,
  required vs. refused arguments, exit codes, and both sync and async paths.

**Not verified in CI: the answers.** There is no Snowflake instance in the job,
and even the `fakesnow` scenario suite is excluded from the run. Tests that
create tables and compare figures against a hand count need credentials and
skip when the scenario configuration is absent. Treat the SQL as reviewed
against the vendor's documentation, not as observed behaviour.

## Code style checks

```bash
ruff check src/
black --check src/
isort --check-only src/
mypy src/
```

Line width follows the project configuration (Black/isort 100, Ruff 120).

## Next steps

- [Overview](../introduction/overview.md)
- [Database introspection](../introspection/README.md)
