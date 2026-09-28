# src/rhosocial/activerecord/backend/impl/snowflake/backend/__init__.py
"""Snowflake backend implementations.

Every backend keeps both classes in this package: the sync class in
``backend.py`` and the async class in ``async_backend.py``. So the sync class
is at ``impl.snowflake.backend.backend`` and the async class at
``impl.snowflake.backend.async_backend``.
"""

from .backend import SnowflakeBackend
