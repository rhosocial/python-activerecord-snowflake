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
provider_registry.register("feature.basic.IBasicSyncProvider", BasicProvider)
provider_registry.register("feature.basic.IBasicAsyncProvider", BasicProvider)

from .basic_connection import BasicConnectionProvider
provider_registry.register("feature.basic.connection.IBasicConnectionProvider", BasicConnectionProvider)

from .query import QueryProvider
provider_registry.register("feature.query.IQueryProvider", QueryProvider)
provider_registry.register("feature.query.IQuerySyncProvider", QueryProvider)
provider_registry.register("feature.query.IQueryAsyncProvider", QueryProvider)

from .events import EventsProvider
provider_registry.register("feature.events.IEventsProvider", EventsProvider)
provider_registry.register("feature.events.IEventsSyncProvider", EventsProvider)
provider_registry.register("feature.events.IEventsAsyncProvider", EventsProvider)

from .mixins import MixinsProvider
provider_registry.register("feature.mixins.IMixinsProvider", MixinsProvider)
provider_registry.register("feature.mixins.IMixinsSyncProvider", MixinsProvider)
provider_registry.register("feature.mixins.IMixinsAsyncProvider", MixinsProvider)

from .query_connection import QueryConnectionProvider
provider_registry.register("feature.query.connection.IQueryConnectionProvider", QueryConnectionProvider)
