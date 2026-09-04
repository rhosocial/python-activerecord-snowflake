# tests/rhosocial/activerecord_snowflake_test/feature/basic/validation/test_validation.py
"""Bridge file for validation tests from the testsuite."""
from rhosocial.activerecord.testsuite.feature.basic.conftest import (
    validated_user_class,
    validated_user,
    async_validated_user_class,
    async_validated_user,
)
from rhosocial.activerecord.testsuite.feature.basic.validation.test_validation import *
from rhosocial.activerecord.testsuite.feature.basic.validation.test_validation_async import *  # noqa: F403

