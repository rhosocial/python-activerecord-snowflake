# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/conftest.py
"""Snowflake DDL tests run against this directory's emulator database."""
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

DECLARATION = Declaration(
    parallel=True,
    purpose="Snowflake DDL: ALTER TABLE guards, table modifiers and object-kind handling.",
    passes_means=(
        "DDL statements render and apply correctly against the directory's"
        " emulator database"
    ),
    fails_means=(
        "a DDL statement is wrong or the emulator database was reset by two"
        " workers at once"
    ),
)
