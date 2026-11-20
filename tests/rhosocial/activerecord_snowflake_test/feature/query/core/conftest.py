# tests/rhosocial/activerecord_snowflake_test/feature/query/core/conftest.py
"""The ``query/core`` minimal test set.

Two kinds of test live here: the shared cross-database contracts, whose tables
the suite's ``query/cross_database`` group owns, and Snowflake's own collation
expression tests, which build the one table they need themselves.  The group is
prepared as a whole, so the directory declares the cross-database group.
"""
from rhosocial.activerecord.testsuite.feature.query.cross_database.conftest import *  # noqa: F401,F403
