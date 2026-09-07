# src/rhosocial/activerecord/backend/impl/snowflake/ddl_spec.py
"""Snowflake-specific DDL feature specs.

Plain declaration objects (no dialect at definition time) recognized by the
Snowflake dialect's ``build_spec`` via ``isinstance``. Only the Snowflake
dialect claims these specs; every other backend silently ignores them
(``build_spec`` returns ``None``).

Snowflake's ``PARTITION BY`` applies to external tables; a standard
``CREATE TABLE`` in this backend takes no partition clause, so the
partition spec here is only meaningful for external-table flows.
"""

from typing import Sequence

from rhosocial.activerecord.backend.expression.statements.ddl_spec import (
    ColumnTypeSpec,
    PartitionSpec,
)


class SnowflakeExternalPartition(PartitionSpec):
    """Snowflake external-table ``PARTITION BY (col, ...)`` declaration.

    Renders ``PARTITION BY (cols)`` for external-table DDL; a standard
    internal table creation ignores it (backend decision).
    """

    __slots__ = ("columns",)

    def __init__(self, columns: Sequence[str]):
        if not columns:
            raise ValueError("SnowflakeExternalPartition requires at least one column")
        self.columns = list(columns)


class SnowflakeVariantColumnSpec(ColumnTypeSpec):
    """A Snowflake ``VARIANT`` column (semi-structured JSON)."""

    __slots__ = ()


class SnowflakeArrayColumnSpec(ColumnTypeSpec):
    """A Snowflake ``ARRAY`` column."""

    __slots__ = ()


class SnowflakeObjectColumnSpec(ColumnTypeSpec):
    """A Snowflake ``OBJECT`` column."""

    __slots__ = ()