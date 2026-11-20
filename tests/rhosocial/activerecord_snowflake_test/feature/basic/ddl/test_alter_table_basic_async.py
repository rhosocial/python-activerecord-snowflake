# tests/rhosocial/activerecord_snowflake_test/feature/basic/ddl/test_alter_table_basic_async.py
"""
ALTER TABLE IF [NOT] EXISTS tests (async) for the Snowflake backend.

Thin bridge that runs the shared testsuite contract against a bare dialect.
The async variant differs only in the fixture it requests -- no connection or
database is involved -- so the contract itself is imported verbatim.
"""

from rhosocial.activerecord.testsuite.feature.basic.ddl.test_alter_table_if_exists_async import *  # noqa: F403
