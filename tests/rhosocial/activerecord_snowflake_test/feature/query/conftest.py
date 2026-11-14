# tests/rhosocial/activerecord_snowflake_test/feature/query/conftest.py
"""Fixtures shared by the ``query`` topic.

The models and their per-test fixtures come from the testsuite; each leaf
directory below this one declares its own table group, so this module only
imports the shared fixture group.
"""
from rhosocial.activerecord.testsuite.feature.query.conftest import *  # noqa: F401,F403
