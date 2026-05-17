"""Test Provider Registry for Snowflake backend.

This module registers concrete implementations of test suite interfaces
for the Snowflake backend.
"""
from rhosocial.activerecord.testsuite.core.registry import ProviderRegistry

# Create a single, global instance of the ProviderRegistry.
provider_registry = ProviderRegistry()

# Register basic providers
from .basic import BasicProvider
provider_registry.register("feature.basic.IBasicProvider", BasicProvider)

from .basic_connection import BasicConnectionProvider
provider_registry.register("feature.basic.connection.IBasicConnectionProvider", BasicConnectionProvider)
