# src/rhosocial/activerecord/backend/impl/snowflake/protocols/__init__.py
"""Snowflake backend-specific protocol definitions.

This package defines protocols for features exclusive to Snowflake,
which are not part of the SQL standard and not supported by other
mainstream databases.
"""

from .time_travel import SnowflakeTimeTravelSupport
from .variant import SnowflakeVariantSupport
from .array import SnowflakeArraySupport
from .clone import SnowflakeCloneSupport
from .stage import SnowflakeStageSupport
from .partition import SnowflakePartitionSupport
from .warehouse import SnowflakeWarehouseSupport
from .stream import SnowflakeStreamSupport
from .task import SnowflakeTaskSupport
from .pipe import SnowflakePipeSupport
from .file_format import SnowflakeFileFormatSupport
from .routine import SnowflakeRoutineSupport
from .undrop import SnowflakeUndropSupport
from .materialized_view import SnowflakeMaterializedViewSupport
from .dynamic_identifier import SnowflakeDynamicIdentifierSupport
from .table_modifier import SnowflakeTableModifierSupport
from .sample import SnowflakeSampleSupport
from .pivot import SnowflakePivotSupport
from .dml import SnowflakeDMLSupport
from .show import SnowflakeShowSupport

__all__ = [
    "SnowflakeTimeTravelSupport",
    "SnowflakeVariantSupport",
    "SnowflakeArraySupport",
    "SnowflakeCloneSupport",
    "SnowflakeStageSupport",
    "SnowflakePartitionSupport",
    "SnowflakeWarehouseSupport",
    "SnowflakeStreamSupport",
    "SnowflakeTaskSupport",
    "SnowflakePipeSupport",
    "SnowflakeFileFormatSupport",
    "SnowflakeRoutineSupport",
    "SnowflakeUndropSupport",
    "SnowflakeMaterializedViewSupport",
    "SnowflakeDynamicIdentifierSupport",
    "SnowflakeTableModifierSupport",
    "SnowflakeSampleSupport",
    "SnowflakePivotSupport",
    "SnowflakeDMLSupport",
    "SnowflakeShowSupport",
]
