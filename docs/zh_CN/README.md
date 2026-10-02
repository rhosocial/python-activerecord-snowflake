# rhosocial-activerecord Snowflake 后端文档

Snowflake 后端是 [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord)
的 Snowflake 后端实现。它使用 `snowflake-connector-python` 驱动。Snowflake 采用
`<database>.<schema>.<object>` 三级命名空间，是本项目中唯一一个 `schema` 作为独立
命名层级、而非 database 另一种叫法的后端。

## 目录 (Table of Contents)

- **[Schema 命名空间](snowflake_specific_features/schema_namespace.md)**：声明
  `__schema_name__`、三段式列引用、别名处理、`CURRENT_SCHEMA()`、`SEARCH_PATH`，
  以及单级限定的局限

## 关键结论速览

| 问题 | 结论 |
|---|---|
| `schema_name` 指什么？ | database 之内的 schema，是独立的一层 |
| 限定表渲染为 | `"app"."orders"` |
| 列引用 | 未取别名的范围为三段：`"app"."orders"."id"` |
| 取别名之后 | `"o"."id"` |
| 当前 schema | `CURRENT_SCHEMA()` |
| `CREATE SCHEMA` / `DROP SCHEMA` | 支持 |
| schema DDL 的 `AUTHORIZATION` | 不支持 |

## 相关文档

- **[Schema 命名空间（核心库指南）](https://github.com/rhosocial/python-activerecord/tree/docs/docs/modeling/schema_namespace.md)**：
  所有后端共同遵循的、与方言无关的规则

---

> ⚠️ **依赖说明**：本后端依赖核心库 `rhosocial-activerecord`，请与核心库一并安装，
> 不要单独安装本后端。