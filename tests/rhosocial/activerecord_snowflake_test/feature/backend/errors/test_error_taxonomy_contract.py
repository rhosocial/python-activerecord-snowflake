# tests/rhosocial/activerecord_snowflake_test/feature/backend/errors/test_error_taxonomy_contract.py
"""Run the testsuite error-taxonomy contract for the Snowflake backend.

The contract lives in rhosocial-activerecord-testsuite; importing it here keeps
CI from silently skipping the taxonomy checks when that package changes.
"""
from rhosocial.activerecord.testsuite.feature.backend.errors.test_error_taxonomy import *  # noqa: F401,F403
