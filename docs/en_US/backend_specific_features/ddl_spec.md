# DDL Feature Specs

Snowflake implements the core DDL feature-spec claiming protocol
(`dialect.build_spec`). This chapter documents which Specs the Snowflake
dialect claims, how it translates them, and the Snowflake-specific Specs it
adds.

## How claiming works

At `Model.generate_create_table(dialect)` time the generator hands each
declared Spec to `dialect.build_spec(spec)`:

- **Accepted** → the dialect builds and returns an expression-layer instance,
  which lands in the `CreateTableExpression`;
- **Not accepted** → returns `None`, and the Spec is silently ignored.

## Generic Specs

All generic Specs are claimed and translated by the core default:

| Spec | Snowflake translation |
|------|-----------------------|
| `CheckSpec` | `TableConstraint(CHECK)`, lazy predicates evaluated at build time |
| `UniqueSpec` | `TableConstraint(UNIQUE)` |
| `NotNullSpec` | `ColumnConstraint(NOT NULL)` |
| `PrimaryKeySpec` | column-level PK (single) / table-level composite PK |
| `DefaultSpec` | `ColumnConstraint(DEFAULT)` with a parameterized `Literal` |
| `ForeignKeySpec` | `ForeignKeyConstraint` |
| `IndexSpec` | `IndexDefinition` (Snowflake has no conventional indexes) |
| `JsonColumnSpec` | column type patch → `JsonType` |

## Snowflake-specific Specs

Defined in `rhosocial.activerecord.backend.impl.snowflake.ddl_spec`; claimed
via `isinstance` and translated by `SnowflakeDDLSpecMixin`. Only the
Snowflake dialect claims these.

### External-table Partition

```python
from rhosocial.activerecord.backend.impl.snowflake.ddl_spec import (
    SnowflakeExternalPartition,
)

class Events(ActiveRecord):
    __table_partition__ = [
        SnowflakeExternalPartition(columns=["created_date", "region"]),
    ]
```

Snowflake's `PARTITION BY` applies to external tables; the Spec translates to
`SnowflakePartitionClause`.

### Semi-structured Column Specs

```python
from rhosocial.activerecord.backend.impl.snowflake.ddl_spec import (
    SnowflakeVariantColumnSpec,
    SnowflakeArrayColumnSpec,
    SnowflakeObjectColumnSpec,
)

class T(ActiveRecord):
    __table_constraints__ = [
        SnowflakeVariantColumnSpec("data"),
        SnowflakeArrayColumnSpec("arr"),
        SnowflakeObjectColumnSpec("obj"),
    ]
```

Rendered as the native `VARIANT`, `ARRAY`, `OBJECT` types respectively.
