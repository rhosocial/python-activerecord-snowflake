"""
This is the root pytest configuration file for the rhosocial-activerecord-snowflake package's test suite.

Its primary responsibility is to configure the environment so that the external
`rhosocial-activerecord-testsuite` can find and use the backend-specific
implementations (Providers) defined within this project.
"""
import os
import pytest

# Set the environment variable that the testsuite uses to locate the provider registry.
os.environ.setdefault(
    'TESTSUITE_PROVIDER_REGISTRY',
    'providers.registry:provider_registry'
)
