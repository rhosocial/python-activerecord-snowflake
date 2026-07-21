# src/rhosocial/activerecord/backend/impl/snowflake/mixins/partition.py
"""Snowflake partition mixin — partition DDL support for external tables."""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.mixins.partition import PartitionMixin

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import PartitionClause


class SnowflakePartitionMixin(PartitionMixin):
    """Snowflake partition implementation.

    Snowflake supports PARTITION BY on external tables.
    Standard tables use automatic micro-partitioning.
    """

    def supports_table_partitioning(self) -> bool:
        return True

    def supports_partitioned_table_creation(self) -> bool:
        return True

    def supports_partition_metadata_introspection(self) -> bool:
        return False

    def supports_range_table_partitioning(self) -> bool:
        return True

    def supports_list_table_partitioning(self) -> bool:
        return True

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

    def format_partition_clause(self, expr: "PartitionClause") -> Tuple[str, tuple]:
        method = expr.method.upper()
        cols = ", ".join(
            key.to_sql()[0] for key in expr.keys
        )
        partition_defs = expr.dialect_options.get("partitions", [])
        if partition_defs:
            parts = []
            for p in partition_defs:
                name = p.get("name", "")
                if method == "RANGE":
                    values = p.get("values", [])
                    parts.append(f"PARTITION {name} VALUES LESS THAN ({', '.join(values)})")
                elif method == "LIST":
                    values = p.get("values", [])
                    parts.append(f"PARTITION {name} VALUES IN ({', '.join(values)})")
            if parts:
                clause = f"PARTITION BY {method} ({cols}) (\n  " + ",\n  ".join(parts) + "\n)"
                return clause, ()
        return f"PARTITION BY {method} ({cols})", ()
