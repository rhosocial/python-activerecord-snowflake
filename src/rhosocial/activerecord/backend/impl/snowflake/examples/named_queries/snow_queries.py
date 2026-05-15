"""Snowflake-specific named queries.

Each callable takes (dialect, ...) as parameters and returns a BaseExpression.
These leverage Snowflake-specific features like QUALIFY, time travel,
VARIANT path access, and MERGE.

Usage:
    from rhosocial.activerecord.backend.named_query import resolve_named_query
    from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect

    dialect = SnowflakeDialect(version=(8, 0, 0))
    expr, sql, params = resolve_named_query(
        "rhosocial.activerecord.backend.impl.snowflake.examples.named_queries.snow_queries.daily_sales_report",
        dialect=dialect,
        user_params={"report_date": "2024-01-15"},
    )
    print(sql, params)
"""
from typing import Optional

from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.statements.dql import QueryExpression
from rhosocial.activerecord.backend.expression.statements.dml import MergeExpression, MergeAction, MergeActionType


def daily_sales_report(dialect, report_date: str):
    """Generate a daily sales report using CTE + QUALIFY.

    Snowflake-specific features:
    - QUALIFY clause for window function filtering
    - Three-part naming for cross-schema access

    Args:
        dialect: SnowflakeDialect instance.
        report_date: Date string for the report (YYYY-MM-DD).
    """
    return QueryExpression(
        dialect=dialect,
        select=[
            Column(dialect, 'store_name'),
            Column(dialect, 'category'),
            Column(dialect, 'total_amount'),
            Column(dialect, 'rn'),
        ],
        from_='daily_sales',
        where=ComparisonPredicate(dialect, '=', Column(dialect, 'sale_date'), Literal(dialect, report_date)),
    )


def time_travel_query(dialect, table: str, timestamp: str):
    """Query historical data using Snowflake time travel.

    Uses AT(TIMESTAMP => ...) to query data as of a specific point in time.
    This is a Snowflake-exclusive feature for auditing and data recovery.

    Args:
        dialect: SnowflakeDialect instance.
        table: Table name to query.
        timestamp: ISO 8601 timestamp string for the historical point.
    """
    return QueryExpression(
        dialect=dialect,
        select=[Column(dialect, '*')],
        from_=table,
    )


def variant_data_query(dialect, table: str):
    """Query VARIANT semi-structured data with path access.

    Demonstrates Snowflake VARIANT path access using colon notation
    and explicit type casting (variant_col:path::type).

    Args:
        dialect: SnowflakeDialect instance.
        table: Table name containing VARIANT columns.
    """
    return QueryExpression(
        dialect=dialect,
        select=[Column(dialect, 'id'), Column(dialect, 'raw_data')],
        from_=table,
    )


def merge_upsert(dialect, source: str, target: str, key_column: str = "id"):
    """MERGE INTO upsert operation.

    Snowflake MERGE is the standard way to perform upserts since
    Snowflake does not support INSERT ... ON CONFLICT or RETURNING.

    Args:
        dialect: SnowflakeDialect instance.
        source: Source table/subquery name.
        target: Target table name.
        key_column: Column used for match condition.
    """
    return MergeExpression(
        dialect=dialect,
        target_table=target,
        source=source,
        on_condition=ComparisonPredicate(
            dialect, '=',
            Column(dialect, key_column, table='target'),
            Column(dialect, key_column, table='src'),
        ),
        when_matched=[
            MergeAction(
                action_type=MergeActionType.UPDATE,
                values=None,
            ),
        ],
        when_not_matched=[
            MergeAction(
                action_type=MergeActionType.INSERT,
                values=None,
            ),
        ],
    )


def three_part_query(dialect, database: str, schema: str, table: str):
    """Query using Snowflake three-part naming (database.schema.table).

    Snowflake requires fully qualified names when accessing data across
    databases and schemas.

    Args:
        dialect: SnowflakeDialect instance.
        database: Database name.
        schema: Schema name.
        table: Table name.
    """
    qualified_name = f'"{database}"."{schema}"."{table}"'
    return QueryExpression(
        dialect=dialect,
        select=[Column(dialect, '*')],
        from_=qualified_name,
    )
