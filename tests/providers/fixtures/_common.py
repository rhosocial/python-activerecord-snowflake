"""Snowflake-specific DDL post-processing helpers.

The Snowflake dialect generates canonical DDL directly, so no
storage-option quote stripping is needed.  Our test schemas are loaded
directly from the *.sql* files under
tests/rhosocial/activerecord_snowflake_test/feature/<feature>/schema/
rather than from procedural CreateTableExpression builders.
"""
from __future__ import annotations

from typing import Tuple

from rhosocial.activerecord.backend.expression import (
    CreateTableExpression,
    DropTableExpression,
    TableExpression,
)


def to_snowflake_ddl_sql(expr: CreateTableExpression) -> Tuple[str, tuple]:
    """Generate Snowflake DDL for a CreateTableExpression.

    The Snowflake dialect emits canonical DDL directly, so no post-processing
    is required.  Currently treatment just delegates to ``expr.to_sql()``.
    """
    return expr.to_sql()


def create_table_sql(expr: CreateTableExpression) -> Tuple[str, tuple]:
    """Public alias for :func:`to_snowflake_ddl_sql`."""
    return to_snowflake_ddl_sql(expr)


def drop_table(dialect, table_name: str) -> DropTableExpression:
    """Build a canonical ``DROP TABLE IF EXISTS`` expression."""
    return DropTableExpression(
        dialect=dialect,
        table=TableExpression(dialect, table_name),
        if_exists=True,
    )
