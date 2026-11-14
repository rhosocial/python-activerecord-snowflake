# tests/rhosocial/activerecord_snowflake_test/feature/basic/fields/test_field_column_mapping.py
# ruff: noqa: F401,F403 - bridge file: imports are pytest fixtures
"""Bridge file for field/column mapping tests from the testsuite."""
from rhosocial.activerecord.testsuite.feature.basic.conftest import (
    mapped_models_fixtures,
    mixed_models_fixtures,
    async_mapped_models_fixtures,
    async_mixed_models_fixtures,
)
from rhosocial.activerecord.testsuite.feature.basic.fields.test_field_column_mapping import *
