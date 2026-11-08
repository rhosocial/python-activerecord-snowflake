# tests/live/test_seconds_between_integration.py
"""``seconds_between`` against a real Snowflake account.

These cases are the values the unit tests cannot evaluate: the sign, the
fraction, and the millisecond resolution. The module is skipped unless the
account's connection variables are set, so it is safe to collect in CI.

The name carries ``integration`` on purpose: CI runs ``pytest tests/ -k
"not integration"``, which deselects this file by its path as well as by its
marker.
"""

import os
from datetime import datetime

import pytest

from rhosocial.activerecord.backend.expression import (
    Literal,
    QueryStatement,
    seconds_between,
)
from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.config import (
    SnowflakeConnectionConfig,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

_REQUIRED_ENV = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_WAREHOUSE",
)
_HAVE_ACCOUNT = all(os.getenv(name) for name in _REQUIRED_ENV)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _HAVE_ACCOUNT,
        reason="Missing Snowflake env vars: " + ", ".join(
            name for name in _REQUIRED_ENV if not os.getenv(name)
        ),
    ),
]


@pytest.fixture(scope="module")
def live_backend():
    config = SnowflakeConnectionConfig(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ.get("SNOWFLAKE_PASSWORD"),
        private_key_path=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH"),
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
    )
    backend = SnowflakeBackend(connection_config=config)
    backend.connect()
    yield backend
    backend.disconnect()


def _elapsed(backend, start: datetime, end: datetime) -> float:
    dialect = backend.dialect
    expr = seconds_between(
        dialect,
        Literal(dialect, start, inline=True),
        Literal(dialect, end, inline=True),
    )
    query = QueryStatement(dialect, select=[expr])
    sql, params = query.to_sql()
    result = backend.execute(
        sql, params, options=ExecutionOptions(stmt_type=StatementType.DQL)
    )
    row = result.data[0]
    return float(next(iter(row.values())))


class TestSecondsBetweenLive:
    def test_positive_elapsed_keeps_the_fraction(self, live_backend):
        value = _elapsed(
            live_backend,
            datetime(2026, 1, 1, 0, 0, 0),
            datetime(2026, 1, 1, 0, 0, 5, 250000),
        )
        assert value == pytest.approx(5.25)

    def test_reversed_operands_are_negative(self, live_backend):
        value = _elapsed(
            live_backend,
            datetime(2026, 1, 1, 0, 0, 5, 250000),
            datetime(2026, 1, 1, 0, 0, 0),
        )
        assert value == pytest.approx(-5.25)

    def test_same_instant_is_zero(self, live_backend):
        instant = datetime(2026, 1, 1, 0, 0, 0)
        assert _elapsed(live_backend, instant, instant) == 0.0

    def test_textbook_half_second(self, live_backend):
        value = _elapsed(
            live_backend,
            datetime(2026, 1, 1, 0, 0, 0),
            datetime(2026, 1, 1, 0, 0, 0, 500000),
        )
        assert value == pytest.approx(0.5)

    def test_sub_millisecond_is_below_the_documented_resolution(
        self, live_backend
    ):
        """``DATEDIFF`` counts whole milliseconds, so less than 1 ms is lost."""
        value = _elapsed(
            live_backend,
            datetime(2026, 1, 1, 0, 0, 0),
            datetime(2026, 1, 1, 0, 0, 0, 900),
        )
        assert abs(value) <= 0.001
