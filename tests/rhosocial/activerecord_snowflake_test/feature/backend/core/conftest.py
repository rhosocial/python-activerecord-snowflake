# tests/rhosocial/activerecord_snowflake_test/feature/backend/core/conftest.py
"""Core Snowflake backend behavior runs against this directory's emulator database."""
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

DECLARATION = Declaration(
    parallel=True,
    purpose=(
        "Snowflake core behavior: clause guards, error mapping, identifier quoting"
        " and introspection data profiles."
    ),
    passes_means="core behavior holds against the directory's emulator database",
    fails_means=(
        "a core behavior is wrong or the emulator database was reset by two"
        " workers at once"
    ),
)
