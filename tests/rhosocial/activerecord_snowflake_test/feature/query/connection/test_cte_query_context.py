# tests/rhosocial/activerecord_snowflake_test/feature/query/connection/test_cte_query_context.py
"""
CTEQuery Context Test Module for Snowflake backend.

This module imports and runs the shared tests from the testsuite package,
ensuring Snowflake backend compatibility for CTEQuery connection pool context awareness.
"""


# Import shared tests from testsuite package
from rhosocial.activerecord.testsuite.feature.query.connection.test_cte_query_context import *  # noqa: F403
from rhosocial.activerecord.testsuite.feature.query.connection.test_cte_query_context_async import *  # noqa: F403

