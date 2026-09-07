# src/rhosocial/activerecord/backend/impl/snowflake/mixins/ddl_spec.py
"""Snowflake ``build_spec`` implementation (DDL feature-spec claiming).

Composed into ``SnowflakeDialect``. Claims the Snowflake-specific Specs
defined in ``..ddl_spec`` via ``isinstance`` and translates them into the
Snowflake expression layer. All other Specs fall through to the generic
``DDLSpecBuildingMixin`` base translation.
"""

from typing import Any, Optional

from rhosocial.activerecord.backend.dialect.mixins.ddl_spec import DDLSpecBuildingMixin
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.statements import PartitionStrategy
from rhosocial.activerecord.backend.expression.statements.ddl_spec import (
    ColumnPatchSpec,
    DDLSpec,
)

from ..ddl_spec import (
    SnowflakeArrayColumnSpec,
    SnowflakeExternalPartition,
    SnowflakeObjectColumnSpec,
    SnowflakeVariantColumnSpec,
)
from ..expression import (
    SnowflakeArrayType,
    SnowflakeObjectType,
    SnowflakeVariantType,
)


class SnowflakeDDLSpecMixin(DDLSpecBuildingMixin):
    """Snowflake-specific ``build_spec`` claiming and translation."""

    def build_spec(self, spec: "DDLSpec") -> Optional[Any]:
        """Claim Snowflake Specs; otherwise defer to the generic build."""
        if isinstance(spec, SnowflakeExternalPartition):
            return self._build_snowflake_external_partition(spec)
        if isinstance(spec, SnowflakeVariantColumnSpec):
            return ColumnPatchSpec(
                column=spec.column,
                patched_data_type=SnowflakeVariantType(self),
            )
        if isinstance(spec, SnowflakeArrayColumnSpec):
            return ColumnPatchSpec(
                column=spec.column,
                patched_data_type=SnowflakeArrayType(self),
            )
        if isinstance(spec, SnowflakeObjectColumnSpec):
            return ColumnPatchSpec(
                column=spec.column,
                patched_data_type=SnowflakeObjectType(self),
            )
        return super().build_spec(spec)

    def _build_snowflake_external_partition(self, spec: "SnowflakeExternalPartition"):
        """Translate an external-table partition Spec to ``SnowflakePartitionClause``.

        Standard internal-table creation does not take a partition clause —
        whether the built clause is consumed is the caller/backend's decision.
        """
        from ..expression.partition import SnowflakePartitionClause

        return SnowflakePartitionClause(
            self,
            method=PartitionStrategy.RANGE,
            keys=[Column(self, c) for c in spec.columns],
        )