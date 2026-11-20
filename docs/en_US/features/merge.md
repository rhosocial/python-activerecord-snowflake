# MERGE & upsert

Snowflake has no DML-level `RETURNING` clause and no `INSERT ... ON CONFLICT`
form. Conditional upserts are done with ANSI `MERGE`, which this backend
declares through `supports_merge()` and `supports_upsert()` (both `True`).

## The statement

```sql
MERGE INTO target t
USING source s
ON t.id = s.id
WHEN MATCHED THEN UPDATE SET t.value = s.value
WHEN NOT MATCHED THEN INSERT (id, value) VALUES (s.id, s.value);
```

The dialect supports `MERGE` with complex match conditions. At the expression
level a merge is built from a `MergeStatement` with a target relation, a source
relation, an `ON` predicate, and `when_matched` / `when_not_matched` actions of
type `UPDATE` or `INSERT`:

```python
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.predicates import ComparisonPredicate
from rhosocial.activerecord.backend.expression.statements.dml import (
    MergeAction, MergeActionType, MergeStatement,
)

stmt = MergeStatement(
    dialect=dialect,
    target_table=target,
    source=source,
    on_condition=ComparisonPredicate(
        dialect, "=",
        Column(dialect, "id", table="target"),
        Column(dialect, "id", table="src"),
    ),
    when_matched=[MergeAction(action_type=MergeActionType.UPDATE)],
    when_not_matched=[MergeAction(action_type=MergeActionType.INSERT)],
)
sql, params = stmt.to_sql()
```

> This chapter shows dialect-level API usage. For model-level persistence and
> the query builder, see the [core library documentation](https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US).

## No `RETURNING`

Do not expect `INSERT ... RETURNING id` (or the UPDATE/DELETE equivalents) to
work here. The supported pattern is a `MERGE` for the write plus a separate
query when you need the resulting row. A few `supports_returning_*` probes in
the dialect consult the connector version via `version_at_least((7, 32, 0))`;
they are not a promise that DML-level `RETURNING` is available on this engine.
See [Capability boundaries](../introduction/capability_boundaries.md).

## INSERT OVERWRITE

Snowflake also supports `INSERT OVERWRITE`, exposed by `SnowflakeDMLMixin` and
`supports_insert_overwrite()`:

```python
from rhosocial.activerecord.backend.impl.snowflake.expression.dml import SnowflakeInsertExpression

stmt = SnowflakeInsertExpression(dialect=dialect, ..., overwrite=True)
# INSERT OVERWRITE INTO ...
```

`INSERT OVERWRITE` truncates the target table **inside the same transaction**,
which avoids the implicit commit a separate `TRUNCATE` would cause. The flag is
specific to `SnowflakeInsertExpression`; a plain core insert keeps its normal
rendering, and asking for overwrite on a non-plain `INSERT INTO` form is a
`ValueError`.

## Next steps

- [Time travel](time_travel.md)
- [Capability boundaries & fail-fast](../introduction/capability_boundaries.md)
