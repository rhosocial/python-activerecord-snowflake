# tests/rhosocial/activerecord_snowflake_test/feature/relation/conftest.py
"""Fixtures shared by the ``relation`` topic.

The models and their per-test fixtures come from the testsuite; the directory's
database and table group belong to each leaf below this one, so this module only
imports the shared fixture group.
"""
from rhosocial.activerecord.testsuite.feature.relation.conftest import *  # noqa: F401,F403
