# tests/rhosocial/activerecord_snowflake_test/feature/basic/fields/test_fields.py
# ruff: noqa: F401,F403 - bridge file: imports are pytest fixtures
"""Bridge file for basic field tests from the testsuite."""
from rhosocial.activerecord.testsuite.feature.basic.conftest import (
    validated_user,
    async_validated_user,
)
from rhosocial.activerecord.testsuite.feature.basic.fields.test_fields import *
