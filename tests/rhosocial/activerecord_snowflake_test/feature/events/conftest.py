# tests/rhosocial/activerecord_snowflake_test/feature/events/conftest.py
"""Fixtures shared by the ``events`` topic.

The models and their per-test fixtures come from the testsuite; the directory's
database and table group are declared in ``core/``, which is where the shared
event contracts are run.
"""
from rhosocial.activerecord.testsuite.feature.events.conftest import *  # noqa: F401,F403
