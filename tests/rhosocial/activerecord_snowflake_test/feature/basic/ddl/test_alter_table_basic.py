# tests/rhosocial/activerecord_snowflake_test/feature/basic/ddl/test_alter_table_basic.py
"""
ALTER TABLE IF [NOT] EXISTS tests (sync) for the Snowflake backend.

Thin bridge that runs the shared testsuite contract against a bare dialect.
"""

from rhosocial.activerecord.testsuite.feature.basic.ddl.test_alter_table_if_exists import *  # noqa: F403