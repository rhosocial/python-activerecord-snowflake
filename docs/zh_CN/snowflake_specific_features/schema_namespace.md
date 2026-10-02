# docs/zh_CN/snowflake_specific_features/schema_namespace.md

# Snowflake Schema 命名空间

> 本文只讲本后端特有的部分：`schema_name` 在这里指向什么、表达式层为什么只带一级
> 限定、限定名如何渲染、表别名如何影响列引用、不加限定的名字最终落在哪个 schema
> 上，以及 `SEARCH_PATH` 与名字相近的 PostgreSQL `search_path` 有哪些实质差别。
>
> 模型层的通用部分——怎么在模型上声明 `__schema_name__`、schema 何时进入 SQL、
> DDL 的边界、各后端支持矩阵——由核心库（`python-activerecord` 仓库）的
> `docs/modeling/schema_namespace.md` 讲，见
> [`docs/zh_CN/modeling/schema_namespace.md`][core-zh]。

[core-zh]: https://github.com/rhosocial/python-activerecord/tree/main/docs/zh_CN/modeling/schema_namespace.md

## 本文结论的验证方式

文中每一段 SQL 都由 `SnowflakeDialect` 配合表达式层渲染得出，没有连接真实服务端：

```
PYTHONPATH=src .venv3.14-ubuntu26.04/bin/python
```

`SnowflakeDialect` 以元组形式接收版本号，`(8, 0, 0)` 是默认值，本页大部分示例用的
就是它。用户自定义 TYPE 的 DDL 需要 `(10, 8, 0)` 或更高版本，出现在相关位置时会
写明。

描述服务端而非渲染器的部分——`CURRENT_SCHEMA()` 如何解析、`SEARCH_PATH` 的默认值、
带 schema 限定的名字能否走到另一个 database——来自 Snowflake 自身的文档，本仓库
没有在真实实例上验证过。凡属此类内容均在正文中标明。本文对应
`rhosocial-activerecord-snowflake` 1.0.0.dev2。

## Snowflake 是唯一有独立 schema 层的后端

这一点要先说清楚，因为在写任何 SQL 之前，它就已经决定了 `schema_name` 的含义。

核心库的后端支持矩阵记录了各家 `schema_name` 各自指向什么。大致的情形是：这一族
后端要么根本没有命名空间层（SQLite、Firebird），要么用这个词指最外层的容器——
MySQL 与 MariaDB 把 `schema` 当作 `database` 的同义词，ClickHouse 没有
`CREATE SCHEMA`、用这个词指它的 database，BigQuery 称之为 dataset——再要么像
PostgreSQL、SQL Server 与 Oracle 那样，在 database 内部有一层真正的 schema。

只有 Snowflake 的 schema 是 database **之内**独立的一层，官方文档写得很直接：

> A database is a logical grouping of schemas. Each database belongs to a single
> Snowflake account.
>
> A schema is a logical grouping of database objects (tables, views, etc.). Each
> schema belongs to a single database.
>
> Together, a database and schema comprise a *namespace* in Snowflake.
>
> —— [Database, schema, & share DDL][ddl-database]

结论由第二句推出：一个 schema 只属于一个 database，所以单凭 schema 名不足以定位
一个对象。

> A fully-qualified schema object (table, view, file format etc.) has the form:
>
> `<database_name>.<schema_name>.<object_name>`
>
> —— [Object name resolution][name-resolution]

> **`schema_name` 只是所需两级中的一级。** 另一级是 database，而 database 来自连接，
> 不来自模型。核心库的支持矩阵同样记着这一点。

[ddl-database]: https://docs.snowflake.com/en/sql-reference/ddl-database
[name-resolution]: https://docs.snowflake.com/en/sql-reference/name-resolution

### 对模型意味着什么

`__schema_name__` 负责 schema；database 是持有该模型的连接的属性。两个分别指向
`TESTDB` 与 `REPORTING` 的连接，即便都写着 `__schema_name__ = "app"`，命中的也是
两张互不相干的表，而框架为两者生成的是同一句 SQL：

```sql
SELECT "app"."orders"."id" FROM "app"."orders"
```

隔离来自连接所挂的 database，而不是渲染出来的限定名。要访问另一个 database 里的
对象，渲染出的名字就必须带上 database——而下一节会说明，当前的表达式层做不到这件事。

Snowflake 自身的名字解析里有两条规则值得和上面的渲染放在一起看：

- **省掉 database 与省掉 schema 不是一回事。** 两段式名字 `schema.object` 会被补上
  当前 database；当前 database 在会话建立时设定，之后由 `USE DATABASE` 改变。只有一
  段的名字又不一样：在 DDL 与 DML 里补上当前 database **和** 当前 schema，在查询里
  则走搜索路径。
- **确实存在一种越过当前 schema 的写法。** `<database_name>..<object_name>`——两个点
  号——指向指定 database 的 `PUBLIC` schema 里的对象。Snowflake 文档说明这种记法是为
  兼容 SQL Server、Netezza 之类的系统而提供，并不建议在新查询中使用。本后端生成不了
  这种形式：`format_table` 在两段之间恰好输出一个点号，没有办法要求中间那段为空。

## 表达式层只带一级限定

这是本库的限制，不是 Snowflake 的限制。说清楚：

> **本后端的表、视图、列、索引表达式只接受 `schema_name`，不接受它上面的任何一级。
> `TableExpression`、`Column`、`WildcardExpression`、
> `QualifiedIdentifierExpression` 都没有 `database_name` 字段，也没有可以补上的方言
> 钩子。schema 一律渲染成恰好一个带引号的段，因此写进去的点号会留在这一段内部。**

```python
TableExpression(d, "orders", schema_name="TESTDB.app").to_sql()[0]
# "TESTDB.app"."orders"    -- 一个名字就叫 "TESTDB.app" 的 schema
```

database 这一级只能从另外两条途径进入语句，两条都不是模型级的命名空间：

- **连接。** `SnowflakeConnectionConfig.database` 作为连接的 `database` 交给
  `snowflake.connector.connect()`，`SnowflakeConnectionConfig.schema`（或旧的
  `schema_name` 写法）作为其 `schema`。这一对参数就是驱动用来建立会话当前 database
  与当前 schema 的东西。因此换一个 database 意味着换一个连接，而不是换一个
  `schema_name`。
- **手写 SQL。** 必须指名另一个 database 里对象的语句只能手写。本方言另外支持
  Snowflake 的 `IDENTIFIER()` 形式，它把全限定名作为参数值绑定，而不是拼接进 SQL：

  ```python
  SnowflakeIdentifierExpression(d, "TESTDB.app.orders").to_sql()
  # ('IDENTIFIER(%s)', ('TESTDB.app.orders',))
  ```

  这是把三段式名字送到服务端的途径，不是从 `TableExpression` 里取到三段式名字的途径。

### 唯一接受两级的入口

Snowflake 的用户自定义 TYPE DDL 是例外，而且是一个实打实的例外，不是通用能力：

```python
from rhosocial.activerecord.backend.impl.snowflake.expression import (
    SnowflakeCreateTypeExpression,
    SnowflakeScalarTypeDefinition,
    SnowflakeVarcharType,
)

definition = SnowflakeScalarTypeDefinition(d, SnowflakeVarcharType(d))

SnowflakeCreateTypeExpression(
    d, "label", definition, database_name="TESTDB", schema_name="app",
).to_sql()[0]
# CREATE TYPE "TESTDB"."app"."label" AS VARCHAR

SnowflakeCreateTypeExpression(
    d, "label", definition, schema_name="app",
).to_sql()[0]
# CREATE TYPE "app"."label" AS VARCHAR
```

`SnowflakeCreateTypeExpression`、`SnowflakeAlterTypeExpression` 与
`SnowflakeDropTypeExpression` 都在 `schema_name` 之外接受 `database_name`，并且拒绝
只给 database 的写法：

```
ValueError: schema_name is required when database_name is provided
```

```python
SnowflakeAlterTypeExpression(d, "label", [action], database_name="TESTDB",
                             schema_name="app").to_sql()[0]
# ALTER TYPE "TESTDB"."app"."label" SET COMMENT = 'c'

SnowflakeDropTypeExpression(d, "label", database_name="TESTDB", schema_name="app").to_sql()[0]
# DROP TYPE "TESTDB"."app"."label"
```

这项检查发生在**构造表达式时**，而不是渲染时，与后文空串那条规则正好相反。TYPE 的
DDL 还要求服务端版本在 10.8 及以上；版本更低时这三条语句都会在到达这里之前抛出
`UnsupportedFeatureError`。

`TableExpression` 不具备这个形态。不要因为 TYPE 能写出三段式，就认为表也能。

### `CREATE SCHEMA` 与 `DROP SCHEMA` 无法指定 database

同样的限制也落在 schema DDL 上，并直接决定新 schema 落在哪里。
`CreateSchemaExpression` 与 `DropSchemaExpression` 各自只带一个 `schema_name`，没有
database 字段：

```python
CreateSchemaExpression(d, "ar_crm").to_sql()[0]
# CREATE SCHEMA "ar_crm"

DropSchemaExpression(d, "ar_crm").to_sql()[0]
# DROP SCHEMA "ar_crm"
```

Snowflake 的 `CREATE SCHEMA` 没有 database 限定——参考文档的第一句就是「Creates a
new schema in the current database」，语法为 `CREATE [ OR REPLACE ] [ TRANSIENT ]
SCHEMA [ IF NOT EXISTS ] <name>`。要在别的 database 里建 schema，只能在已经挂到那个
database 的连接上执行这条语句。以上是 Snowflake 文档给出的语法，未在真实实例上验证。

`CREATE SCHEMA` 还会把新建的 schema 设为会话的当前 schema，因此迁移脚本里建完 schema
之后，同一连接上后续每一条语句的当前 schema 都变了。Snowflake 里 `OR REPLACE` 与
`IF NOT EXISTS` 互斥，而本表达式只渲染后者。

`UNDROP SCHEMA` 是本后端自己的表达式，只接受一个裸名，完全没有放命名空间的位置：

```python
SnowflakeUndropExpression(d, "ar_crm", object_type=SnowflakeUndropObjectType.SCHEMA).to_sql()[0]
# UNDROP SCHEMA "ar_crm"
```

`ALTER SCHEMA` 完全没有建模。核心表达式层里没有 `AlterSchemaExpression`，因此下面这
五个能力标志即便 Snowflake 原生支持该语句也都回答 `False`：

```python
dialect.supports_alter_schema()                 # False
dialect.supports_alter_schema_rename()          # False
dialect.supports_alter_schema_swap()            # False
dialect.supports_alter_schema_set_property()    # False
dialect.supports_alter_schema_managed_access()  # False
```

schema 这一组其余的能力标志：

```python
dialect.supports_schema()                       # True
dialect.supports_create_schema()                # True
dialect.supports_drop_schema()                  # True
dialect.supports_schema_if_not_exists()         # True
dialect.supports_schema_if_exists()             # True
dialect.supports_schema_cascade()               # True
dialect.supports_schema_authorization()         # False
dialect.supports_undrop_schema()                # True
```

`supports_schema_authorization()` 的 `False` 是会生效的：给 `CreateSchemaExpression`
传 `authorization=` 会抛异常，而不是把这个子句渲染出来。

```python
CreateSchemaExpression(d, "ar_crm", authorization="app_user").to_sql()
# UnsupportedFeatureError: 'Snowflake' dialect does not support CREATE SCHEMA
# AUTHORIZATION.
```

`if_not_exists`、`if_exists` 与 `cascade` 则都会渲染：

```python
CreateSchemaExpression(d, "ar_crm", if_not_exists=True).to_sql()[0]
# CREATE SCHEMA IF NOT EXISTS "ar_crm"

DropSchemaExpression(d, "ar_crm", if_exists=True, cascade=True).to_sql()[0]
# DROP SCHEMA IF EXISTS "ar_crm" CASCADE
```

## `schema_name` 在这里指向什么

database 这一层说清楚之后，值本身仍按 Snowflake 自己的定义来：当前 database 里的一个
schema。同一个 database 里的两个 schema 是互不相干的命名空间，`"app"."orders"` 与
`"crm"."orders"` 是两张碰巧同名的表。

渲染用双引号，每一段各自成为一个带引号的标识符：

| 表达式 | SQL |
|---|---|
| `TableExpression(d, "orders", schema_name="app")` | `"app"."orders"` |
| `TableExpression(d, "orders")` | `"orders"` |
| `TableExpression(d, "orders", schema_name="app", alias="o")` | `"app"."orders" AS "o"` |

`QualifiedIdentifierExpression` 的渲染方式相同；需要在 `FROM` 之外拿到一个两段式名字
时用它：

```python
QualifiedIdentifierExpression(d, "app", "orders").to_sql()[0]
# "app"."orders"
```

### 引号与大小写

`format_identifier` 默认加引号，并把值里自带的双引号写成两个，因此本该提前闭合引用的
字符仍留在同一个标识符内部：

```python
TableExpression(d, "orders", schema_name='app"x').to_sql()[0]
# "app""x"."orders"

TableExpression(d, "orders", schema_name="My Schema").to_sql()[0]
# "My Schema"."orders"
```

关键的一点是**渲染层从不折叠大小写**。`schema_name` 按写下来的样子原样输出：

```python
TableExpression(d, "orders", schema_name="ar_xcrm").to_sql()[0]
# "ar_xcrm"."orders"
```

这一点之所以要紧，是因为 Snowflake 自己的规则恰好朝相反方向折叠。标识符要求一节
写道：

> - When an identifier is unquoted, it is stored and resolved in uppercase.
> - When an identifier is double-quoted, it is stored and resolved exactly as
>   entered, including case.
>
> —— [Identifier requirements][identifiers-syntax]

[identifiers-syntax]: https://docs.snowflake.com/en/sql-reference/identifiers-syntax

也就是说，在 Snowflake 上 `"ar_xcrm"` 与 `"AR_XCRM"` 是两个不同的 schema，而不加引号
的 `ar_xcrm` 与 `AR_XCRM` 是同一个。用 `CREATE SCHEMA ar_xcrm` 建出来的 schema 存成
`AR_XCRM`，`"ar_xcrm"` **找不到**它。建 schema 时用模型所采用的那套引号，或者把模型
里的写法改成服务端实际存下来的大小写。

丢掉引号的办法有两种，都是有意为之：

```python
TableExpression(d, "orders", schema_name="app", schema_need_quote=False).to_sql()[0]
# app."orders"     -- 服务端读作 APP
```

`schema_need_quote=False`（以及按角色对应的 `name_need_quote`、
`alias_need_quote`）会走到不加引号的分支，那里 Snowflake 适用大写规则。对保留字再传
`need_quote=False`，还会额外发出 `IdentifierQuotingWarning`。

值里写点号同样不构成分隔符，见[常见错误](#常见错误)。

## 在模型上声明

```python
from typing import ClassVar, Optional

class Order(ActiveRecord):
    __table_name__ = "orders"
    __schema_name__ = "app"                 # -> "app"."orders"
    c: ClassVar[FieldProxy] = FieldProxy()

    id: Optional[int] = None
    user_id: Optional[int] = None
    total: Optional[float] = None
```

`__schema_name__` 可选，不写就是 `None`，即不加限定。一旦设上，模型构造出的每一条语句
都带上这个命名空间——`SELECT`、`WHERE`、`ORDER BY`、`GROUP BY`、`HAVING` 一视同仁：

```python
Order.query().select(Order.c.id).to_sql()[0]
# SELECT "app"."orders"."id" FROM "app"."orders"

Order.query().where(Order.c.id > 1).to_sql()[0]
# SELECT * FROM "app"."orders" WHERE "app"."orders"."id" > %s

Order.query().group_by(Order.c.user_id).order_by(Order.c.id).limit(5).to_sql()[0]
# SELECT * FROM "app"."orders" GROUP BY "app"."orders"."user_id"
#   ORDER BY "app"."orders"."id" ASC LIMIT %s

Order.query().group_by(Order.c.user_id).having(Order.c.total > 10).to_sql()[0]
# SELECT * FROM "app"."orders" GROUP BY "app"."orders"."user_id"
#   HAVING "app"."orders"."total" > %s
```

命名空间会落到 `FROM` 里的范围上，也会落到未加限定的列引用上；它**不会**落到已经带
了 schema 的列引用上，原因见下一节。

不设 `__schema_name__` 的模型渲染为不加限定，由连接决定落在哪里：

```python
PlainOrder.query().select(PlainOrder.c.id).to_sql()[0]
# SELECT "plain_orders"."id" FROM "plain_orders"
```

`SELECT *` 无需限定，渲染时也不带任何限定：

```python
Order.query().to_sql()[0]
# SELECT * FROM "app"."orders"
```

命名空间只读一次，入口是 `schema_name()`，随每个列表达式构造时一并带下去。事后再改
`__schema_name__`，已经建好的表达式不会跟着变——重建条件，或改完再新建。这条绑定规则
在核心库文档里有完整说明。

## 三段式列引用与别名

不带别名的范围既可以用关系名寻址，也可以用限定名寻址，因此在没有别名生效时，本后端
输出三段式。`SnowflakeDialect` 没有覆盖 `format_column`，走的是核心渲染器：

```python
Column(d, "id", table="orders", schema_name="app").to_sql()[0]
# "app"."orders"."id"

Column(d, "id", table="orders").to_sql()[0]
# "orders"."id"
```

带别名的范围会**取代**关系名，能用来标识它的只剩别名，列引用里的 schema 也随之被去掉。
这一步发生在列表达式**构造**时，而不是渲染时：只要表别名生效，`FieldProxy` 就把
`schema_name` 置为 `None`。

```python
Order.query().select(Order.c.with_table_alias("o").id).to_sql()[0]
# SELECT "o"."id" FROM "app"."orders"
```

两条边界仍然生效。

只带 schema 而不带表的列依旧被拒绝，因为没有可用来解析前缀的对象：

```
ValueError: Snowflake: cannot qualify column 'id' with schema 'app' because no
table was given; a column reference needs a table (or an alias) to be
schema-qualified
```

另外，手工构造的 `Column` 会绕过别名这道防线。`Column(d, "id", table="o",
schema_name="app")` 渲染出 `"app"."o"."id"`——给一个在语句里被另行取了别名的范围带上
schema 限定。框架构造的查询不会走到这个形态，手工构造的 `Column` 会。Snowflake 是否接受
这样引用一个带别名的范围，此处未验证。

与 PostgreSQL 不同，本方言不会因为列引用带了**列别名**就去掉 schema：

```python
Order.query().select(Order.c.id.as_("x")).to_sql()[0]
# SELECT "app"."orders"."id" AS "x" FROM "app"."orders"
```

这是核心渲染器的产出，本方言并未覆盖它。这里的范围没有别名，因此三段式引用与上面的
规则并不冲突。

### 给范围取别名

表达式层会把带别名的范围渲染成 Snowflake 期望的形式：

```python
TableExpression(d, "orders", schema_name="app", alias="o").to_sql()[0]
# "app"."orders" AS "o"
```

在模型层，范围别名只能来自 join。范围别名与列访问器用同一个名字构造，并与
`join(..., alias=...)` 配对：

```python
Order.query().join(
    User, on=Order.c.user_id == User.c.with_table_alias("u").id, alias="u"
).select(Order.c.id, User.c.with_table_alias("u").name).to_sql()[0]
# SELECT "app"."orders"."id", "u"."name" FROM "app"."orders"
#   JOIN "crm"."users" AS "u" ON "app"."orders"."user_id" = "u"."id"
```

范围保留自己的 schema，变化的只有列前缀。自连接与其它后端一样，两侧都要取别名：

```python
Order.query().join(
    Order,
    on=Order.c.with_table_alias("c").id == Order.c.with_table_alias("p").user_id,
    alias="p",
).select(Order.c.with_table_alias("c").id, Order.c.with_table_alias("p").id).to_sql()[0]
# SELECT "c"."id", "p"."id" FROM "app"."orders"
#   JOIN "app"."orders" AS "p" ON "c"."id" = "p"."user_id"
```

join 条件里仍然指向未取别名的范围时，框架会拒绝：

```
ValueError: cannot join crm.users with alias 'u' using a condition that still
refers to crm.users: an aliased range can only be addressed by its alias. Build
the condition from users.c.with_table_alias('u') so the reference and the alias
agree.
```

只给列这一侧取别名，范围仍然没有别名，得到的是服务端拒绝的 SQL，而不是框架拒绝的
SQL：

```python
Order.query().select(Order.c.with_table_alias("o").id).to_sql()[0]
# SELECT "o"."id" FROM "app"."orders"        <- "o" 不在作用域内
```

### 跨 schema 的 join

两侧各自限定自己的范围，因此一条语句跨越两个 schema 不需要任何额外配置：

```python
Order.query().join(User, on=Order.c.user_id == User.c.id).select(
    Order.c.id, User.c.name
).to_sql()[0]
# SELECT "app"."orders"."id", "crm"."users"."name"
#   FROM "app"."orders" JOIN "crm"."users"
#   ON "app"."orders"."user_id" = "crm"."users"."id"
```

跨 schema 就是上限。跨 database 的 join 要求两侧范围都带上各自的 database，而表达式层
生成不出这种形式，见
[表达式层只带一级限定](#表达式层只带一级限定)。

## 集合运算

`UNION`、`INTERSECT` 与 `EXCEPT` 自身不指名任何对象，因此没有可限定的东西。每一个分支
保留自己的命名空间：

```python
Order.query().select(Order.c.id).union(User.query().select(User.c.id)).to_sql()[0]
# SELECT "app"."orders"."id" FROM "app"."orders"
#   UNION SELECT "crm"."users"."id" FROM "crm"."users"
```

对两个绑定了 schema 的模型做 `UNION` 不需要特殊处理。对两个 database 做 `UNION` 则要求
每个分支都带上自己的 database，这里表达不了。

## CTE

CTE 是为余下整条查询命名的，不属于 database，因此它自己的名字是裸名。渲染出 `WITH`
子句时，核心渲染器用 `format_identifier` 输出这个名字，不加任何限定——里面的查询仍然
带着模型的 schema：

```python
from rhosocial.activerecord.backend.expression import CTEExpression, WithQueryExpression

inner = QueryExpression(
    dialect=d,
    select=[Column(d, "id", table="orders", schema_name="app")],
    from_=[TableExpression(d, "orders", schema_name="app")],
)

WithQueryExpression(d, [CTEExpression(d, "recent_orders", inner)], main).to_sql()[0]
# WITH "recent_orders" AS (SELECT "app"."orders"."id" FROM "app"."orders")
#   SELECT "recent_orders"."id" FROM "recent_orders"
```

**在本后端，查询构造器走不到这条路上。**
`SnowflakeDialect.supports_basic_cte()` 回答 `False`，构造 `CTEQuery` 时就会抛出异常，
一条 SQL 都还没开始拼：

```python
from rhosocial.activerecord.query.cte_query import CTEQuery

CTEQuery(backend)
# UnsupportedFeatureError: 'Snowflake' dialect does not support CTE (Common Table
# Expressions). Suggestion: This backend does not support CTE queries. Check
# dialect.supports_basic_cte() before building a CTEQuery.
```

这是本后端能力标志上的缺口，而不是对 Snowflake 的判断——Snowflake 支持 `WITH`，同一
方言上 `supports_recursive_cte()` 回答的就是 `True`。两个标志彼此独立，而 `CTEQuery`
检查的是前一个。

## DDL 自带 schema

`__schema_name__` 决定读写的命名空间。构造 DDL 时**不会**去读它——迁移脚本必须自己写明
它指的是哪个 schema——但凡是会指名某个带 schema 的对象的语句，都接受各自的
`schema_name`，因此限定不必再手工拼装。

```python
DropTableExpression(d, TableExpression(d, "orders", schema_name="app"),
                    if_exists=True).to_sql()[0]
# DROP TABLE IF EXISTS "app"."orders"

TruncateExpression(d, "orders", schema_name="app").to_sql()[0]
# TRUNCATE TABLE "app"."orders"

CreateIndexExpression(d, "idx_orders_id", "orders", ["id"], schema_name="app").to_sql()[0]
# CREATE INDEX "app"."idx_orders_id" ON "app"."orders" ("id")

DropIndexExpression(d, "idx_orders_id", schema_name="app").to_sql()[0]
# DROP INDEX "app"."idx_orders_id"

CreateViewExpression(d, "v_orders", query, schema_name="app").to_sql()[0]
# CREATE VIEW "app"."v_orders"  AS SELECT "app"."orders"."id" FROM "app"."orders"

DropViewExpression(d, "v_orders", schema_name="app", if_exists=True).to_sql()[0]
# DROP VIEW IF EXISTS "app"."v_orders"

DropMaterializedViewExpression(d, "v_orders", schema_name="app", if_exists=True).to_sql()[0]
# DROP MATERIALIZED VIEW IF EXISTS "app"."v_orders"

CreateSequenceExpression(d, "s_orders", schema_name="app").to_sql()[0]
# CREATE SEQUENCE "app"."s_orders" NO CYCLE
```

`CreateIndexExpression` 只有一个 `schema_name`，并且同时管住两个名字：索引与它所建的表
落在同一个 schema。

DML 语句的限定方式相同，传入带限定的 `TableExpression`：

```python
InsertExpression(d, TableExpression(d, "users", schema_name="app"), source,
                 columns=["id", "name"]).to_sql()[0]
# INSERT INTO "app"."users" ("id", "name")

UpdateExpression(d, TableExpression(d, "users", schema_name="app"),
                 {"name": value}).to_sql()[0]
# UPDATE "app"."users" SET "name" = %s WHERE "app"."users"."id" = %s

DeleteExpression(d, [TableExpression(d, "users", schema_name="app")]).to_sql()[0]
# DELETE FROM "app"."users" WHERE "app"."users"."id" = %s
```

软删除会针对模型的范围重建一条 `UPDATE`，因此 `restore()` 与 `delete()` 一样把命名空间
带下去；这条路径由核心库文档覆盖。

有两条语句在 Snowflake 上是被拒绝而不是被限定的：

```python
TruncateExpression(d, "orders", schema_name="app", restart_identity=True).to_sql()
# UnsupportedFeatureError: Snowflake TRUNCATE has no RESTART IDENTITY option.

RefreshMaterializedViewExpression(d, "v_orders", schema_name="app").to_sql()
# UnsupportedFeatureError: 'Snowflake' dialect does not support REFRESH
# MATERIALIZED VIEW.
```

`SHOW` 通过自己的 scope 子句触达 schema，那也是一个单段标识符，因此同样只带一级：

```python
SnowflakeShowExpression(d, SnowflakeShowObjectType.SCHEMAS).to_sql()[0]
# SHOW SCHEMAS

SnowflakeShowExpression(d, SnowflakeShowObjectType.TABLES,
                        in_scope=SnowflakeShowScope.SCHEMA, in_name="app").to_sql()[0]
# SHOW TABLES IN SCHEMA "app"
```

### 本后端无法限定的 schema 级对象

Snowflake 放在 schema **内部**的大多数对象类型完全没有放命名空间的位置。
`SnowflakeCreateStageExpression`、`SnowflakeCreatePipeExpression`、
`SnowflakeCreateTaskExpression`、`SnowflakeCreateStreamExpression`、
`SnowflakeCreateFileFormatExpression`、`SnowflakeCreateFunctionExpression`、
`SnowflakeCreateProcedureExpression` 以及它们各自的 `Drop` 版本，只接受一个裸
`name`，此外什么都没有：

```python
SnowflakeCreateStageExpression(d, "s_int", url="s3://bucket/k").to_sql()[0]
# CREATE STAGE "s_int" URL = 's3://bucket/k'

SnowflakeDropStageExpression(d, "s_int", if_exists=True).to_sql()[0]
# DROP STAGE IF EXISTS "s_int"
```

`SnowflakeCreateWarehouseExpression` 等 warehouse 相关语句处境相同，但在那里是
对的——warehouse 是 account 级对象，不属于 schema 级。

对这些 schema 级类型来说，后果是对象一律落在会话的当前 schema 里，表达式层没有任何
办法指定别的地方。能用的只有连接配置上的 `schema`。

## 不加限定的名字落在哪里

不加限定的名字由服务端解析，不由框架解析。这里涉及两套机制，值得分开讲。

### 当前 schema

Snowflake 同时维护一个当前 database 与一个当前 schema。当前 schema 永远属于当前
database：会话建立时按连接配置初始化，由 `USE SCHEMA` 改变，`CREATE SCHEMA` 也会隐式
改变它。`USE DATABASE` 会把它重置为该 database 的默认值，通常是 `PUBLIC`。

在 DDL 与 DML 语句里，不加限定的名字会补上当前 database **和**当前 schema；在查询里则
走搜索路径，也就是下一节的内容。

当前 schema 由后端向服务端读取：

```python
backend.get_current_schema()
await async_backend.get_current_schema()
```

渲染出来是

```sql
SELECT CURRENT_SCHEMA()
```

括号不可省略：`CURRENT_SCHEMA` 是函数，不带括号时 Snowflake 会把这个记号读成列引用。
框架始终输出调用形式，裸形式只会出现在手写的 SQL 里。返回 `None` 表示搜索路径没有解析
到任何存在的 schema。

`CURRENT_SCHEMA()` 不接受参数，也不能与 `CURRENT_SCHEMAS()` 混用——两者的差别见下一节。
`CURRENT_DATABASE()` 是 database 层对应的那个，本后端的内省用它来报告 catalog 名。

### `SEARCH_PATH` 与 PostgreSQL `search_path` 的差别

`SEARCH_PATH` 是 Snowflake 自己的会话参数，不是从 PostgreSQL 搬过来的同名物。其文档
定义如下：

> Type: Session — Can be set for Account, User, Session
>
> Data Type: String
>
> Specifies the path to search to resolve unqualified object names in queries.
>
> Values: Comma-separated list of identifiers. An identifier can be a fully or
> partially qualified schema name.
>
> Default: `$current, $public`

与 PostgreSQL 的 `search_path` 相比，有三处差别在实践中会碰到：

- **它是会话参数，用 `ALTER SESSION` 设置，**可以设在 account、user 或 session 任一层。
  PostgreSQL 那个是 libpq 的连接参数，连接时固定。Snowflake 文档还额外加了一条
  PostgreSQL 没有的限制：*"You cannot set this parameter within a client connection
  string, such as a JDBC or ODBC connection string. You must establish a session before
  setting a search path."*
- **它的表项可以用 database 限定。** `testdb.public` 是合法表项，这正是不加限定的名字在
  查询中走到当前 database 之外某个 schema 的办法。PostgreSQL 的表项则是当前 database
  内的 schema 名。
- **它支持两个伪变量。** `$current` 指当前 schema，`$public` 指当前 database 的
  `PUBLIC` schema。伪变量名不区分大小写，并且可以随意使用——即使当前 database 没有
  `PUBLIC` schema，`$public` 依然合法。其它表项则必须指向一个存在的 schema，否则赋值
  被拒绝，参数保留原来的值。

参数本身的值是字符串，但**解析后的列表不是**：`CURRENT_SCHEMAS()` 返回一个全限定
schema 的数组，伪变量已展开，不存在或不可见的 schema 已被剔除：

```sql
SELECT CURRENT_SCHEMAS();
-- ["TEST_DB1.BILLING", "TEST_DB1.PUBLIC"]
```

这正是与 PostgreSQL 实质上的差别：PostgreSQL 的 `SHOW search_path` 返回的是一个
schema 名的字符串，既没有 database 这一层，也没有展开这一步。参数的字面值用
`SHOW PARAMETERS LIKE 'search_path'` 查看。

还有两条行为，此处引用文档而非实测：参数值每次使用时都会重新解释，因此改变当前
schema 就会改变 `$current` 的含义；路径上的 schema 被删除，或者当前 database 换成
不带那些未限定 schema 的另一个，都不会报错。`SEARCH_PATH` 在视图与 UDF 内部也不起作用
——那里的不加限定名字只在视图或 UDF 自己的 schema 里解析。

### 本后端如何暴露它

`SnowflakeConnectionConfig` **没有** `search_path` 字段。它有两个与命名空间相关的字段，
职责不同：

- **`schema`**（也接受旧的 `schema_name` 写法）作为连接的 `schema` 交给
  `snowflake.connector.connect()`。它设置会话的当前 schema，也是没有
  `__schema_name__` 的模型最终依赖的东西。`backend._resolve_configured_schema()` 读的
  就是它；内省器在没有指定 schema 时据此决定去哪里找。
- **`session_parameters`** 是一个 `Dict[str, Any]`，原样转交给
  `snowflake.connector.connect()`。驱动会把这个字典并入登录时应用的会话参数，
  `SEARCH_PATH` 就是这样设置的：

  ```python
  SnowflakeConnectionConfig(
      ...,
      database="TESTDB",
      session_parameters={"SEARCH_PATH": "$current, testdb.public"},
  )
  ```

  这个参数是否满足 Snowflake「必须先建立会话」的限制，此处未验证——本仓库没有真实的
  Snowflake 实例，而且那条限制的措辞针对的是客户端连接串，并没有专门点名 Python 驱动。
  `ALTER SESSION SET SEARCH_PATH = ...` 是文档给出的做法，不需要这类假设。

没有 `search_path` 快捷字段，也没有按查询或按事务的覆盖手段：一条语句落在哪个 schema
由连接固定，换地方就得另开连接。

## 内省读的是连接，不是服务端

内省器通过后端的 `_resolve_configured_schema()` 选取 schema，该方法从配置上读
`schema`（其次是旧的 `schema_name`），方法不存在时直接回落到读配置。它不会调用
`CURRENT_SCHEMA()`。

由此产生的一条结论值得写明：**配置上没有 schema 的连接，会让内省器去查 `""`**，而这在
`INFORMATION_SCHEMA` 里匹配不到任何东西。生成的查询是对
`INFORMATION_SCHEMA.TABLES` 与 `INFORMATION_SCHEMA.COLUMNS` 的 `TABLE_SCHEMA = ?`，
因此绑定了 schema 的连接与没有绑定 schema 的连接，对「正在查看什么」这件事并不一致。
只要模型声明了 `__schema_name__`，就在配置上把 `schema` 设上，哪怕驱动会话的默认值本来
就是对的。

## 空串，以及它在哪一步被拦下

`""` 是一个错误，不是「不加限定」的写法——那件事由 `None` 表达。它会被拒绝，但**不是
在表达式构造时**。构造阶段表达式只收集参数——那时它的方言可能都还没定下来——严格校验
发生在渲染阶段，那时语句才是完整的。因此失败来得比预期晚：

```python
class Bad(ActiveRecord):
    __table_name__ = "empties"
    __schema_name__ = ""

Bad.schema_name()                        # ''           -- 不报错
Bad.c.id                                 # Column       -- 不报错
Bad.query()                              # ActiveQuery  -- 不报错
Bad.query().select(Bad.c.id)             # ActiveQuery  -- 不报错
Bad.query().select(Bad.c.id).to_sql()    # ValueError   -- 到这里才报错
```

异常信息会指明出问题的那个表达式：

```
ValueError: Column.schema_name must be a non-empty string; use None for an
unqualified reference
```

```
ValueError: TableExpression.schema_name must be a non-empty string; use None for
an unqualified reference
```

纯空白串与空串同样被拒绝——检查会先去掉空白，因此 `"   "` 也过不去。非字符串值另有一条
信息：

```
ValueError: TableExpression.schema_name must be a string or None, not int
```

之所以要拒绝而不是把 `""` 当作没有：`format_table` 用
`bool(expr.schema_name)` 判断要不要加限定，`""` 为假，于是走不加限定的分支。本想要
`"app"."orders"` 的调用方会拿到 `"orders"`，没有异常、没有警告，也没有行数变化可供
察觉。在 Snowflake 上那就是会话当前 schema 里的表，或者搜索路径上第一个存在的 schema
里的表——语句照样执行，只是写到了别处。

有**两处不适用**这条规则，在依赖它之前值得知道：

- **Snowflake 的 TYPE DDL。** `SnowflakeCreateTypeExpression`、
  `SnowflakeAlterTypeExpression` 与 `SnowflakeDropTypeExpression` 自己渲染命名空间，
  不走核心层的校验，因此空值会渲染出一个空的带引号段，而不是抛异常：

  ```python
  SnowflakeDropTypeExpression(d, "label", schema_name="").to_sql()[0]
  # DROP TYPE ""."label"
  ```

  它们自己的检查范围更窄：只给 `database_name` 而不给 `schema_name` 会被拒绝，且发生在
  构造阶段。

- **`TruncateExpression`** 抛的是 `TableExpression` 的措辞，因为它内部通过一个
  `TableExpression` 渲染表名。信息指的是执行校验的那个对象，而不是你写下的那条语句。

## 常见错误

**把 `__schema_name__` 当成足以定位对象的东西。** 在本后端它只是两级中的一级。
`"app"."orders"` 指的是**连接所挂的那个** database 里 schema `app` 的 `orders` 表，
渲染出的 SQL 里没有任何信息说明是哪一个 database。两个连接、两个 database、同一句
SQL。见 [Snowflake 是唯一有独立 schema 层的后端](#snowflake-是唯一有独立-schema-层的后端)。

**指望能把 database 渲染出来。** `TableExpression`、`Column`、
`WildcardExpression` 与 `QualifiedIdentifierExpression` 都没有 database 字段，写进去的
点号会留在同一个带引号的段内。Snowflake 的 TYPE DDL 是唯一同时接受两级的表达式族。见
[表达式层只带一级限定](#表达式层只带一级限定)。

**建了 schema 却指望它在别的 database 里。** `CreateSchemaExpression` 没有 database
字段，Snowflake 的 `CREATE SCHEMA` 语法也没有 database 限定：schema 会落在会话的当前
database 里。请使用已经挂到目标 database 的连接。

**以为 `ALTER SCHEMA` 可用。** Snowflake 支持这条语句，本后端没有建模。不存在
`AlterSchemaExpression`，五个 `supports_alter_schema*()` 标志都回答 `False`。

**`__table_name__` 里的点号不是命名空间。** 标识符作为一个整体加引号：

```python
class User(ActiveRecord):
    __table_name__ = "app.users"

User.query().select(User.c.id).to_sql()[0]
# SELECT "app.users"."id" FROM "app.users"    -- 一张名字就叫 "app.users" 的表
```

**`__schema_name__` 里的点号同样不是命名空间。** 每一段各自加引号，点号留在段内：

```python
TableExpression(d, "orders", schema_name="TESTDB.app").to_sql()[0]
# "TESTDB.app"."orders"     -- 一个名字就叫 "TESTDB.app" 的 schema
```

**声明小写 schema 之后发现找不到。** 渲染层保留大小写，Snowflake 则把未加引号的标识符
折叠成大写。`CREATE SCHEMA app` 存成 `APP`，`__schema_name__ = "app"` 渲染出 `"app"`，
两者对不上。见[引号与大小写](#引号与大小写)。

**join 只给一侧取别名，或只给列那一侧取别名。** 范围别名与列访问器要用同一个名字，并与
`join(..., alias=...)` 配对。见[给范围取别名](#给范围取别名)。

**指望构造时就抛异常。** 在语句渲染之前，没有任何环节会拒绝不合法的 `schema_name`。
模型层的错误因此能一路存活到查询构造完成那一刻，在拼装 SQL 的环节才失败。

**在配置上找 `search_path`。** 没有这个字段。`schema` 设置会话的当前 schema，
`session_parameters` 转发 Snowflake 自己的参数。见
[`SEARCH_PATH` 与 PostgreSQL `search_path` 的差别](#search_path-与-postgresql-search_path-的差别)。

**模型绑定了 schema，却没在配置上设 `schema`。** 内省读的是配置，不是
`CURRENT_SCHEMA()`，没有可读时就查 `""`。见
[内省读的是连接，不是服务端](#内省读的是连接不是服务端)。

**以为 CTE 查询能构造出来。** 本方言的 `supports_basic_cte()` 回答 `False`，
`CTEQuery` 会抛异常。见 [CTE](#cte)。

## 建议的分层

- **只有一个 schema** —— 不设 `__schema_name__`，同时在连接配置上设好 `schema`，让内省
  与语句解析落在同一个地方。
- **一个 database 一个 schema，一个 database 一条连接** —— 这才是 Snowflake 命名空间
  真正的形状。因为区分 schema 的是 database，而 database 属于连接，所以在这种形态下
  用 `__schema_name__` 加限定的收益最小：搜索路径与当前 schema 已经带上了它。
  `__schema_name__` 留给那些偏离连接 schema 的模型。
- **一个 database 里多个 schema** —— 在偏离的那些模型上设 `__schema_name__`。跨 schema
  的 join 不需要额外配置，两侧各自限定自己的范围。代价是每一条碰到该模型的语句都会出现
  三段式列引用——不带别名的范围会把 schema 一路带到底。
- **多个 database** —— 每个 database 一条连接，而不是把 `schema_name` 写得更宽。一条
  跨越两个 database 的语句，用当前的表达式层表达不出来。