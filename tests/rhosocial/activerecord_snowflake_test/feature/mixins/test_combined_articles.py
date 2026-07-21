# tests/rhosocial/activerecord_snowflake_test/feature/mixins/test_combined_articles.py
"""
Test combined article functionality (combining multiple mixins) for Snowflake backend.

This module imports and runs the shared tests from the testsuite package,
ensuring Snowflake backend compatibility.
"""

# Import shared tests from testsuite package
from rhosocial.activerecord.testsuite.feature.mixins.test_combined_articles import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.mixins.test_combined_articles_async import *  # noqa: F403

