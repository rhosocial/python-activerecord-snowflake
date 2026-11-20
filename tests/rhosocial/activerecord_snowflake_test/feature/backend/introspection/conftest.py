# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/conftest.py
"""Snowflake introspection tests run against this directory's emulator database."""
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

DECLARATION = Declaration(
    uses_database=True,
    parallel=True,
    purpose="Snowflake SHOW-based schema and account-object introspection.",
    passes_means="introspection reports match the directory's emulator database",
    fails_means="introspection is wrong or the emulator database was reset by two workers at once",
)
