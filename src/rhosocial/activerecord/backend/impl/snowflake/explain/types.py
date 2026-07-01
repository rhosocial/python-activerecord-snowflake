# src/rhosocial/activerecord/backend/impl/snowflake/explain/types.py
"""Snowflake EXPLAIN plan result types.

Snowflake supports:
- EXPLAIN <query>: Returns query plan as tabular result.
- EXPLAIN USING TABULAR <query>: Structured plan output.

Reference: https://docs.snowflake.com/en/sql-reference/sql/explain
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SnowflakeExplainRow:
    """Single row from a Snowflake EXPLAIN output.

    Snowflake EXPLAIN returns columns:
      - step: execution step number
      - id: operation id
      - parent_operators: parent operation ids
      - operation: operation type (e.g., TableScan, Filter, Join)
      - objects: database objects accessed
      - alias: alias if applicable
      - expressions: expressions evaluated
      - partitions_total: total partitions
      - partitions_assigned: partitions assigned
      - bytes: estimated bytes
    """

    step: Optional[int] = None
    id: Optional[int] = None
    parent_operators: Optional[str] = None
    operation: Optional[str] = None
    objects: Optional[str] = None
    alias: Optional[str] = None
    expressions: Optional[str] = None
    partitions_total: Optional[int] = None
    partitions_assigned: Optional[int] = None
    bytes: Optional[int] = None
    raw: Optional[Dict[str, Any]] = None


@dataclass
class SnowflakeExplainResult:
    """Result of a Snowflake EXPLAIN query."""

    rows: List[SnowflakeExplainRow]
    query_text: Optional[str] = None

    @property
    def total_steps(self) -> int:
        return len(self.rows)

    @property
    def total_cost_estimate(self) -> int:
        return sum(r.bytes or 0 for r in self.rows)

    def get_operations(self) -> List[str]:
        return [r.operation for r in self.rows if r.operation]