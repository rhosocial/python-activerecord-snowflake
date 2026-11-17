# tests/rhosocial/activerecord_snowflake_test/feature/backend/extensions/conftest.py
"""Snowflake extension-object tests run against this directory's emulator database."""
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

DECLARATION = Declaration(
    parallel=True,
    purpose=(
        "Snowflake-specific objects: file formats, routines, streams, tasks,"
        " pipes, undrop/clone and materialized views."
    ),
    passes_means=(
        "extension objects render and behave correctly against the directory's"
        " emulator database"
    ),
    fails_means=(
        "an extension object is wrong or the emulator database was reset by two"
        " workers at once"
    ),
)
