# tests/rhosocial/activerecord_snowflake_test/feature/backend/backend/conftest.py
"""Backend lifecycle and configuration run against this directory's emulator database."""
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

DECLARATION = Declaration(
    parallel=True,
    purpose="Snowflake backend lifecycle: connection configuration and backend behavior.",
    passes_means=(
        "configuration and backend behavior hold against the directory's"
        " emulator database"
    ),
    fails_means="configuration is wrong or the emulator database was reset by two workers at once",
)
