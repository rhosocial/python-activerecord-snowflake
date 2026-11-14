# tests/rhosocial/activerecord_snowflake_test/feature/query/core/test_cross_database_compatibility.py
"""Shared ``query/cross_database`` contract, run against this backend.

The suite's cross-database tests are generic: they only assume the models its
fixture group provides.  Importing them here is all it takes to have them run
against Snowflake, and ``query/core/conftest.py`` declares the table group they
share.
"""
from rhosocial.activerecord.testsuite.feature.query.cross_database.test_cross_database_compatibility import *  # noqa: F401,F403
