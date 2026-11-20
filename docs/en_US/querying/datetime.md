# Date and Time Differences

This page covers the two temporal difference expressions and how the Snowflake
dialect renders them. Both are core nodes; the dialect owns the spelling.

## `seconds_between(start, end)`

`seconds_between` answers one question: how many seconds elapsed from `start`
to `end`. The result is signed (`end - start`) and fractional, so a later end is
positive, an earlier end is negative, and equal instants are exactly zero.

```python
from rhosocial.activerecord.backend.expression import Column, seconds_between

elapsed = seconds_between(
    dialect,
    Column(dialect, "queued_at"),
    Column(dialect, "started_at"),
).as_("queue_seconds")
sql, params = elapsed.to_sql()
# Snowflake:
# sql: 'DATEDIFF(MILLISECOND, "queued_at", "started_at") / 1000.0 AS "queue_seconds"'
# params: ()
```

The column-side spelling reaches the same node:

```python
queue_seconds = Model.c.queued_at.seconds_between(Model.c.started_at)
```

Here `Model.c.queued_at` is the receiver, so the call reads "seconds from
`queued_at` to `started_at`" — the receiver is the start and the argument is
the end, the same order as the factory.

### Snowflake's spelling

Snowflake has no interval subtraction that produces a duration: `TIMESTAMP -
TIMESTAMP` is not a number there. Its difference function counts a named unit's
boundaries, so the dialect names the finest unit a timestamp can keep
(`MILLISECOND`) and divides the integer back into seconds:

```sql
DATEDIFF(MILLISECOND, start, end) / 1000.0
```

`DATEDIFF` itself subtracts its first argument from its second, which is why
`start` is written first. The divisor is `1000.0` rather than `1000`: integer
division would truncate a half-second duration to zero, while the decimal
divisor keeps the fraction.

### Resolution and rounding limit

A Snowflake timestamp can store microseconds or nanoseconds, but
`DATEDIFF(MILLISECOND, ...)` counts whole millisecond boundaries. The
sub-millisecond part is truncated **before** the division, so:

- a duration of `0.0009` seconds renders as `0.0`;
- at most `0.001` seconds can be lost per call;
- a duration of `5.250` seconds is exact to the millisecond (`5.25`).

Rounding is the caller's decision, not the node's. A caller who needs
microsecond accuracy cannot recover it from this expression; the dialect
deliberately does not claim whole seconds, because that would make every
fractional duration wrong rather than merely coarse. If sub-millisecond
precision matters, compute it with a `DATEDIFF(MICROSECOND, ...)` expression
directly.

### Bind order and alias

Each operand is rendered where it appears in the SQL. The Snowflake spelling
writes `start` before `end`, so with bound literals:

```python
expr = seconds_between(
    dialect, Literal(dialect, start), Literal(dialect, end)
).as_("elapsed")
# sql:    'DATEDIFF(MILLISECOND, %s, %s) / 1000.0 AS "elapsed"'
# params: (start, end)
```

The bind parameters follow the placeholders, not the order the constructor
happened to receive them. `.as_("...")` survives through `apply_alias`, and the
alias is appended after the division, so the whole expression is the select
item.

## `date_diff(unit, start, end)`

`date_diff` is the whole-unit sibling of `seconds_between`. Snowflake renders
it with the same function and capitalised unit:

```python
from rhosocial.activerecord.backend.expression import Column, date_diff

DATEDIFF(DAY, "started_at", "ended_at")
```

A named unit has nothing to be half of, so `date_diff` counts units crossed
rather than a fractional duration. Use `seconds_between` when the answer is a
duration and `date_diff` when it is a count.

## What a backend implements

The node delegates to one dialect method:

```python
def format_seconds_between_expression(self, expr) -> Tuple[str, Tuple]:
```

`expr.start` and `expr.end` are expressions; render each with `to_sql()` and
return SQL for `end - start` in seconds together with the bind parameters in
placeholder order. Call `self.apply_alias(...)` so `.as_()` survives. Core raises
`UnsupportedFeatureError` for a dialect that has not adapted the node, so an
unadapted backend refuses rather than renders a wrong number.
