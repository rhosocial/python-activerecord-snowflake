# tests/integration/test_seconds_between_integration.py
"""``seconds_between`` against a real Snowflake account.

These cases are the values the unit tests cannot evaluate: the sign, the
fraction, and the millisecond resolution. The connection comes from the
``integration_backend`` fixture this directory already defines, and the
directory's ``conftest`` skips the whole module when the account's connection
variables are unset, so it is safe to collect in CI.

The name carries ``integration`` on purpose: CI runs ``pytest tests -k
"not integration"``, and the root ``conftest`` also deselects anything whose
path contains ``integration``, so this file is skipped on both grounds.
"""

from datetime import datetime

import pytest

from rhosocial.activerecord.backend.expression import (
    Literal,
    QueryStatement,
    seconds_between,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType


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
    def test_positive_elapsed_keeps_the_fraction(self, integration_backend):
        value = _elapsed(
            integration_backend,
            datetime(2026, 1, 1, 0, 0, 0),
            datetime(2026, 1, 1, 0, 0, 5, 250000),
        )
        assert value == pytest.approx(5.25)

    def test_reversed_operands_are_negative(self, integration_backend):
        value = _elapsed(
            integration_backend,
            datetime(2026, 1, 1, 0, 0, 5, 250000),
            datetime(2026, 1, 1, 0, 0, 0),
        )
        assert value == pytest.approx(-5.25)

    def test_same_instant_is_zero(self, integration_backend):
        instant = datetime(2026, 1, 1, 0, 0, 0)
        assert _elapsed(integration_backend, instant, instant) == 0.0

    def test_textbook_half_second(self, integration_backend):
        value = _elapsed(
            integration_backend,
            datetime(2026, 1, 1, 0, 0, 0),
            datetime(2026, 1, 1, 0, 0, 0, 500000),
        )
        assert value == pytest.approx(0.5)

    def test_sub_millisecond_is_below_the_documented_resolution(
        self, integration_backend
    ):
        """``DATEDIFF`` counts whole milliseconds, so less than 1 ms is lost."""
        value = _elapsed(
            integration_backend,
            datetime(2026, 1, 1, 0, 0, 0),
            datetime(2026, 1, 1, 0, 0, 0, 900),
        )
        assert abs(value) <= 0.001
