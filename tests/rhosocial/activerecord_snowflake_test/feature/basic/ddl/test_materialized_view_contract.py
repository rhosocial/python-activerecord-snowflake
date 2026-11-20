# tests/rhosocial/activerecord_snowflake_test/feature/basic/ddl/test_materialized_view_contract.py
"""Thin bridge that runs the shared materialized-view contract here.

This is a DB-free expression/dialect contract: the provider hands over an
adapted dialect and every assertion runs on SQL rendering, with no live
Snowflake account required.
"""

from rhosocial.activerecord.testsuite.feature.basic.ddl.test_materialized_view_contract import *  # noqa: F401,F403
