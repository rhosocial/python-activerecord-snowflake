"""Test Provider Registry for Snowflake backend.

This module registers concrete implementations of test suite interfaces
for the Snowflake backend.
"""
from rhosocial.activerecord.testsuite.core.registry import ProviderRegistry

# Create a single, global instance of the ProviderRegistry.
provider_registry = ProviderRegistry()

# TODO: Register providers when implementations are complete:
# from .basic import BasicProvider
# provider_registry.register("feature.basic.IBasicProvider", BasicProvider)
# from .events import EventsProvider
# provider_registry.register("feature.events.IEventsProvider", EventsProvider)
# from .mixins import MixinsProvider
# provider_registry.register("feature.mixins.IMixinsProvider", MixinsProvider)
# from .query import QueryProvider
# provider_registry.register("feature.query.IQueryProvider", QueryProvider)
