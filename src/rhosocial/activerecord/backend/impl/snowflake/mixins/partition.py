# src/rhosocial/activerecord/backend/impl/snowflake/mixins/partition.py
"""Snowflake partition/clustering mixin.

Snowflake has no declarative (RANGE/LIST/HASH) table partitioning:

* Standard tables are micro-partitioned automatically; the only user control
  is ``CLUSTER BY`` clustering keys (see ``SnowflakeTableModifierMixin``).
* External tables support ``PARTITION BY ( <col> [, ...] )``, a partition
  column list with no VALUES boundaries.

Accordingly this mixin reports the generic declarative-partitioning
capability bits as ``False`` and rejects the generic ``PartitionClause``
(the RANGE/LIST/HASH form) as unsupported Snowflake syntax, while providing
the external-table ``PARTITION BY`` formatter.
"""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.mixins.partition import PartitionMixin

if TYPE_CHECKING:
    from ..expression.partition import SnowflakeExternalPartitionClause


class SnowflakePartitionMixin(PartitionMixin):
    """Snowflake partition implementation.

    Snowflake standard tables use automatic micro-partitioning and, optionally,
    ``CLUSTER BY``. Declarative RANGE/LIST/HASH partitioning does not exist;
    external tables declare partition columns via ``PARTITION BY (cols)``.
    """

    def supports_table_partitioning(self) -> bool:
        """Snowflake has no user-defined declarative table partitioning."""
        return False

    def supports_partitioned_table_creation(self) -> bool:
        """Snowflake standard CREATE TABLE does not take a PARTITION BY clause."""
        return False

    def supports_partition_metadata_introspection(self) -> bool:
        return False

    def supports_range_table_partitioning(self) -> bool:
        return False

    def supports_list_table_partitioning(self) -> bool:
        return False

    def supports_hash_table_partitioning(self) -> bool:
        return False

    def supports_subpartitioning(self) -> bool:
        return False

    def supports_add_partition(self) -> bool:
        return False

    def supports_drop_partition(self) -> bool:
        return False

    def supports_truncate_partition(self) -> bool:
        return False

    def supports_reorganize_partition(self) -> bool:
        return False

    def supports_attach_partition(self) -> bool:
        return False

    def supports_detach_partition(self) -> bool:
        return False

    def supports_external_table_partitioning(self) -> bool:
        """Snowflake external tables support ``PARTITION BY (cols)``."""
        return True

    def format_partition_clause(self, expr) -> Tuple[str, tuple]:
        """Reject the generic declarative ``PartitionClause`` on Snowflake.

        Snowflake has no RANGE/LIST/HASH declarative partitioning; use
        ``CLUSTER BY`` (``SnowflakeClusterByClause``) for standard tables or
        ``SnowflakeExternalPartitionClause`` for external tables.

        Raises:
            UnsupportedFeatureError: always.
        """
        raise UnsupportedFeatureError(
            self.name,
            "declarative table partitioning",
            suggestion="Snowflake standard tables use automatic micro-partitioning; "
            "use CLUSTER BY for data layout, or SnowflakeExternalPartitionClause "
            "for external-table PARTITION BY (cols).",
        )

    def format_external_partition_clause(
        self, expr: "SnowflakeExternalPartitionClause"
    ) -> Tuple[str, tuple]:
        """Format ``PARTITION BY ( <col> [, ...] )`` for external tables.

        Args:
            expr: SnowflakeExternalPartitionClause carrying the partition columns.

        Returns:
            Tuple of (SQL string, parameters tuple).
        """
        parts = []
        params = []
        for column in expr.columns:
            column_sql, column_params = column.to_sql()
            parts.append(column_sql)
            params.extend(column_params)
        return f" PARTITION BY ({', '.join(parts)})", tuple(params)
