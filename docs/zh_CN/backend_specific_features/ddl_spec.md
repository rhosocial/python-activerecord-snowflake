# DDL 特征 Spec

Snowflake 实现了核心 DDL 特征认领协议（`dialect.build_spec`）。本章说明
Snowflake 方言认领哪些 Spec、如何翻译，以及它新增的 Snowflake 特定 Spec。

## 认领机制

`Model.generate_create_table(dialect)` 时，生成器把每个声明的 Spec 交给
`dialect.build_spec(spec)`：

- **接受** → 方言构造并返回表达式层实例，进入 `CreateTableExpression`；
- **不接受** → 返回 `None`，该 Spec 被静默忽略。

## 通用 Spec

全部通用 Spec 由核心默认翻译认领：

| Spec | Snowflake 翻译 |
|------|----------------|
| `CheckSpec` | `TableConstraint(CHECK)`，惰性谓词生成时求值 |
| `UniqueSpec` | `TableConstraint(UNIQUE)` |
| `NotNullSpec` | `ColumnConstraint(NOT NULL)` |
| `PrimaryKeySpec` | 单列→列级 PK / 复合→表级 PK |
| `DefaultSpec` | `ColumnConstraint(DEFAULT)`，参数化 `Literal` |
| `ForeignKeySpec` | `ForeignKeyConstraint` |
| `IndexSpec` | `IndexDefinition`（Snowflake 无常规索引） |
| `JsonColumnSpec` | 列类型补丁 → `JsonType` |

## Snowflake 特定 Spec

定义于 `rhosocial.activerecord.backend.impl.snowflake.ddl_spec`；以
`isinstance` 认领、由 `SnowflakeDDLSpecMixin` 翻译。仅 Snowflake 方言认领。

### 外部表分区

```python
from rhosocial.activerecord.backend.impl.snowflake.ddl_spec import (
    SnowflakeExternalPartition,
)

class Events(ActiveRecord):
    __table_partition__ = [
        SnowflakeExternalPartition(columns=["created_date", "region"]),
    ]
```

Snowflake 的 `PARTITION BY` 适用于外部表；该 Spec 翻译为
`SnowflakePartitionClause`。

### 半结构化列 Spec

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

分别渲染为原生 `VARIANT`、`ARRAY`、`OBJECT` 类型。
