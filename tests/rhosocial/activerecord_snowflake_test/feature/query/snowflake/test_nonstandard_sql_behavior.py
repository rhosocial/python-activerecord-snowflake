# tests/rhosocial/activerecord_snowflake_test/feature/query/snowflake/test_nonstandard_sql_behavior.py
"""
Snowflake-specific tests for non-standard SQL behavior.

This module contains tests that verify Snowflake's lenient handling of SQL statements
that violate the SQL standard. These tests are intentionally placed in the
backend-specific directory (feature/query/snowflake/) rather than in the testsuite
because the behavior being tested is NOT SQL-standard compliant.
"""
import pytest
from decimal import Decimal

from rhosocial.activerecord.testsuite.feature.query.conftest import async_order_fixtures


@pytest.mark.asyncio
async def test_aggregate_with_order_by_no_group_by(async_order_fixtures):
    """
    Test that Snowflake allows ORDER BY in aggregate queries without GROUP BY.
    """
    AsyncUser, AsyncOrder, AsyncOrderItem = async_order_fixtures

    user = AsyncUser(username='snowflake_agg_user', email='snowflake_agg@example.com', age=30)
    await user.save()

    order = AsyncOrder(
        user_id=user.id,
        order_number='MARIADB-AGG-001',
        total_amount=Decimal('100.00')
    )
    await order.save()

    async_query = AsyncOrder.query()
    async_query = async_query.order_by(AsyncOrder.c.order_number)

    count = await async_query.where(AsyncOrder.c.user_id == user.id).count()
    assert count == 1


@pytest.mark.asyncio
async def test_exists_with_retained_order_by(async_order_fixtures):
    """
    Test that Snowflake allows exists() on a query with retained ORDER BY.
    """
    AsyncUser, AsyncOrder, AsyncOrderItem = async_order_fixtures

    user = AsyncUser(username='snowflake_exists_user', email='snowflake_exists@example.com', age=30)
    await user.save()

    order = AsyncOrder(
        user_id=user.id,
        order_number='MARIADB-EXISTS-001',
        total_amount=Decimal('50.00')
    )
    await order.save()

    async_query = AsyncOrder.query()

    _ = await async_query.order_by(AsyncOrder.c.order_number).one()

    exists = await async_query.where(
        AsyncOrder.c.order_number == 'MARIADB-EXISTS-001'
    ).exists()
    assert exists is True


def test_group_by_select_star_non_standard(order_fixtures):
    """
    Test that Snowflake allows SELECT * with incomplete GROUP BY columns.
    """
    User, Order, OrderItem = order_fixtures

    user = User(username='test_user', email='test@example.com', age=30)
    user.save()

    for i in range(3):
        Order(user_id=user.id, order_number=f'ORD-{i:03d}', total_amount=Decimal(f'{(i+1)*100.00}')).save()

    results = Order.query().group_by(Order.c.user_id).group_by(Order.c.order_number).all()
    assert len(results) == 3


@pytest.mark.asyncio
async def test_group_by_select_star_non_standard_async(async_order_fixtures):
    """
    Async version: Test that Snowflake allows SELECT * with incomplete GROUP BY columns.
    """
    AsyncUser, AsyncOrder, AsyncOrderItem = async_order_fixtures

    user = AsyncUser(username='test_user', email='test@example.com', age=30)
    await user.save()

    for i in range(3):
        order = AsyncOrder(user_id=user.id, order_number=f'ORD-{i:03d}', total_amount=Decimal(f'{(i+1)*100.00}'))
        await order.save()

    results = await AsyncOrder.query().group_by(AsyncOrder.c.user_id).group_by(AsyncOrder.c.order_number).all()
    assert len(results) == 3