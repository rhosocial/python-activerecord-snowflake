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
from rhosocial.activerecord.backend.expression.core import Column, Literal
from rhosocial.activerecord.backend.impl.snowflake.expression.table import (
    SnowflakeTableExpression,
)
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


def _split_qualified(dialect, qualified: str, alias: str) -> SnowflakeTableExpression:
    """Turn a dotted name into a table reference with its own namespaces.

    A caller writing ``"RAW.STAGING.incoming"`` means three levels, and each
    needs its own quoting. Handing the whole string over as the table name would
    quote it as one identifier -- ``"RAW.STAGING.incoming"`` -- which is a
    different name that happens to look similar.
    """
    parts = qualified.split(".")
    if len(parts) == 1:
        return SnowflakeTableExpression(dialect, parts[0], alias=alias)
    if len(parts) == 2:
        return SnowflakeTableExpression(dialect, parts[1], schema_name=parts[0], alias=alias)
    if len(parts) == 3:
        return SnowflakeTableExpression(
            dialect, parts[2], schema_name=parts[1], database_name=parts[0], alias=alias
        )
    raise ValueError(
        f"table name has {len(parts)} parts, expected name, schema.name or "
        f"database.schema.name: {qualified!r}"
    )


def merge_upsert(dialect, source: str, target: str, key_column: str = "id"):
    """MERGE INTO upsert operation.

    Snowflake MERGE is the standard way to perform upserts since
    Snowflake does not support INSERT ... ON CONFLICT or RETURNING.

    Args:
        dialect: SnowflakeDialect instance.
        source: Source table name. May be qualified, e.g. ``RAW.STAGING.new``.
        target: Target table name. May be qualified independently of the source;
            a merge across two schemas is ordinary here, and neither side's
            database qualifies the other.
        key_column: Column used for match condition.
    """
    return MergeExpression(
        dialect,
        _split_qualified(dialect, target, "target"),
        _split_qualified(dialect, source, "src"),
        Column(dialect, key_column, table="target") == Column(dialect, key_column, table="src"),
        when_matched=[
            MergeAction(dialect, action_type=MergeActionType.UPDATE),
        ],
        when_not_matched=[
            MergeAction(dialect, action_type=MergeActionType.INSERT),
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
    return QueryExpression(
        dialect,
        select=[Column(dialect, '*')],
        from_=SnowflakeTableExpression(dialect, table, schema_name=schema, database_name=database),
    )
