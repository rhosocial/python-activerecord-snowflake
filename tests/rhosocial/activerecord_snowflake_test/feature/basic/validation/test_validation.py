# tests/rhosocial/activerecord_snowflake_test/feature/basic/validation/test_validation.py
# ruff: noqa: F401,F403 - bridge file: imports are pytest fixtures
"""Bridge file for validation tests from the testsuite."""
from rhosocial.activerecord.testsuite.feature.basic.conftest import (
    validated_user_class,
    validated_user,
    async_validated_user_class,
    async_validated_user,
)
from rhosocial.activerecord.testsuite.feature.basic.validation.test_validation import *
