# tests/rhosocial/activerecord_snowflake_test/feature/basic/test_field_column_mapping.py
"""Bridge file for field/column mapping tests from the testsuite."""
from rhosocial.activerecord.testsuite.feature.basic.conftest import (
    mapped_models_fixtures,
    mixed_models_fixtures,
    async_mapped_models_fixtures,
    async_mixed_models_fixtures,
)
from rhosocial.activerecord.testsuite.feature.basic.test_field_column_mapping import *
from rhosocial.activerecord.testsuite.feature.basic.test_field_column_mapping_async import *  # noqa: F403

