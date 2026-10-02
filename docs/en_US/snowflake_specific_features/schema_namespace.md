# docs/en_US/snowflake_specific_features/schema_namespace.md

# Snowflake Schema Namespaces

> This page covers what is specific to this backend: what a `schema_name` names
> here, why one level of qualification is all the expression layer carries, how
> a qualified name is rendered, what a table alias does to column references,
> which schema an unqualified name resolves against, and how `SEARCH_PATH`
> differs from the PostgreSQL `search_path` it is named after.
>
> The model-level API — declaring `__schema_name__`, when the schema reaches the
> SQL, the DDL boundary, the cross-backend support matrix — is documented in the
> core library guide `docs/modeling/schema_namespace.md`, which lives in the
> `python-activerecord` repository
> ([`docs/en_US/modeling/schema_namespace.md`][core-en]).

[core-en]: https://github.com/rhosocial/python-activerecord/tree/main/docs/en_US/modeling/schema_namespace.md

## How this page was verified

Every SQL fragment below was rendered by the expression layer with
`SnowflakeDialect` and no live server:

```
PYTHONPATH=src .venv3.14-ubuntu26.04/bin/python
```

`SnowflakeDialect` takes its version as a tuple; `(8, 0, 0)` is the default and
what most of the examples use. The user-defined TYPE DDL needs `(10, 8, 0)` or
newer and says so where it appears.

Statements that describe the server rather than the renderer — how
`CURRENT_SCHEMA()` resolves, what `SEARCH_PATH` defaults to, whether a
schema-qualified name reaches a different database — are Snowflake's own
documented behaviour and were not exercised against a live instance in this
repository. Each is marked where it appears. This page was written against
`rhosocial-activerecord-snowflake` 1.0.0.dev2.

## Snowflake is the only backend with a schema layer of its own

This is the first thing to settle, because it changes what a `schema_name` means
before any SQL is written.

The core guide's backend support matrix records what `schema_name` names on each
backend. In short: this family either has no namespace at all (SQLite, Firebird)
or uses the word for the outermost container — MySQL and MariaDB treat `schema`
as a synonym for `database`, ClickHouse has no `CREATE SCHEMA` and uses the word
for its database, BigQuery calls it a dataset — or, like PostgreSQL, SQL Server
and Oracle, has a real schema layer inside a database.

Snowflake is the only one where the schema is a level **of its own, inside** a
database, and its documentation says so directly:

> A database is a logical grouping of schemas. Each database belongs to a single
> Snowflake account.
>
> A schema is a logical grouping of database objects (tables, views, etc.). Each
> schema belongs to a single database.
>
> Together, a database and schema comprise a *namespace* in Snowflake.
>
> — [Database, schema, & share DDL][ddl-database]

The consequence follows from the second sentence. A schema is owned by exactly one
database, so a schema name alone does not identify an object:

> A fully-qualified schema object (table, view, file format etc.) has the form:
>
> `<database_name>.<schema_name>.<object_name>`
>
> — [Object name resolution][name-resolution]

> **A `schema_name` is one level of the two that are needed.** The other level is
> the database, and the database comes from the connection, not from the model.
> This is stated in the core guide's backend support matrix as well.

[ddl-database]: https://docs.snowflake.com/en/sql-reference/ddl-database
[name-resolution]: https://docs.snowflake.com/en/sql-reference/name-resolution

### What this means for a model

`__schema_name__` names the schema; the database is a property of the connection
that owns the model. Two connections pointed at `TESTDB` and `REPORTING`, both
with `__schema_name__ = "app"`, address two unrelated tables, and the framework
emits identical SQL for both:

```sql
SELECT "app"."orders"."id" FROM "app"."orders"
```

The isolation comes from the connection's database, not from the rendered
reference. Reach another database's object and the rendered name has to carry
the database — which, as the next section shows, nothing in the expression layer
can currently produce.

Two things in Snowflake's own name resolution bear on this and are worth reading
alongside the rendering:

- **Omitting the database is not the same as omitting the schema.** A two-part
  name `schema.object` is augmented with the current database; the current
  database is set at session start and changed by `USE DATABASE`. A *one*-part
  name is different again: in DDL and DML it is augmented with the current
  database **and** the current schema, while in a query it is resolved through
  the search path.
- **There is a spelling for reaching past the current schema.**
  `<database_name>..<object_name>` — two dots — names an object in the `PUBLIC`
  schema of the named database. Snowflake's documentation notes this notation is
  provided for compatibility with systems such as SQL Server and Netezza, and
  discourages its use in new queries. Nothing in this backend produces it:
  `format_table` emits exactly one dot between two segments, so there is no way
  to ask for the empty middle one.

## One level of qualification is what the expression layer carries

This is a limitation of this library, not of Snowflake. Stated plainly:

> **The table, view, column and index expressions in this backend accept a
> `schema_name` and nothing above it. There is no `database_name` field on
> `TableExpression`, `Column`, `WildcardExpression` or `QualifiedIdentifierExpression`,
> and no dialect hook that would add one. A schema is always rendered as exactly
> one quoted segment, so a dotted value stays inside that segment.**

```python
TableExpression(d, "orders", schema_name="TESTDB.app").to_sql()[0]
# "TESTDB.app"."orders"    -- a schema literally named "TESTDB.app"
```

The database level reaches a statement by two other routes, and neither is a
model-level namespace:

- **The connection.** `SnowflakeConnectionConfig.database` is handed to
  `snowflake.connector.connect()` as the connection's `database`, and
  `SnowflakeConnectionConfig.schema` (or the legacy `schema_name` spelling) as its
  `schema`. That is the pair the connector uses to establish the session's
  current database and schema. Choosing a different database therefore means
  choosing a different connection, not a different `schema_name`.
- **Raw SQL.** A statement that must name an object in another database has to be
  written by hand. The dialect also supports Snowflake's `IDENTIFIER()` form,
  which binds a fully qualified name as a parameter value rather than
  concatenating it:

  ```python
  SnowflakeIdentifierExpression(d, "TESTDB.app.orders").to_sql()
  # ('IDENTIFIER(%s)', ('TESTDB.app.orders',))
  ```

  That is a way to get a three-part name past the connection, not a way to get
  one out of `TableExpression`.

### The one place two levels are accepted

Snowflake's user-defined TYPE DDL is the exception, and it is a real exception
rather than a general capability:

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

`SnowflakeCreateTypeExpression`, `SnowflakeAlterTypeExpression` and
`SnowflakeDropTypeExpression` each take `database_name` alongside `schema_name`,
and refuse to take the database alone:

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

That check runs **when the expression is built**, not while rendering, which is
the opposite of the empty-string rule described further down. The TYPE DDL also
requires a server version of 10.8 or newer; on an older dialect all three
statements raise `UnsupportedFeatureError` before any of this is reached.

Nothing about `TableExpression` follows this shape. Do not assume a three-part
name is reachable for a table because it is reachable for a type.

### `CREATE SCHEMA` and `DROP SCHEMA` cannot name their database

The same limitation applies to schema DDL, and it decides where a schema lands.
`CreateSchemaExpression` and `DropSchemaExpression` each carry one `schema_name`
and no database field:

```python
CreateSchemaExpression(d, "ar_crm").to_sql()[0]
# CREATE SCHEMA "ar_crm"

DropSchemaExpression(d, "ar_crm").to_sql()[0]
# DROP SCHEMA "ar_crm"
```

Snowflake's `CREATE SCHEMA` takes no database qualifier — its reference opens
with "Creates a new schema in the current database" and the grammar is
`CREATE [ OR REPLACE ] [ TRANSIENT ] SCHEMA [ IF NOT EXISTS ] <name>`. Creating a
schema in a different database therefore means issuing the statement on a
connection already attached to that database. This is Snowflake's documented
grammar and was not verified against a live instance.

`CREATE SCHEMA` also sets the new schema as the session's current schema, so a
migration that creates a schema silently moves the current schema for every
later statement on that connection. `OR REPLACE` and `IF NOT EXISTS` are mutually
exclusive in Snowflake; this expression renders only the latter.

`UNDROP SCHEMA` is this backend's own expression and takes a bare name with no
namespace slot at all:

```python
SnowflakeUndropExpression(d, "ar_crm", object_type=SnowflakeUndropObjectType.SCHEMA).to_sql()[0]
# UNDROP SCHEMA "ar_crm"
```

`ALTER SCHEMA` is not modelled at all. There is no `AlterSchemaExpression` in the
core expression layer, so the five capability flags below answer `False` even
though Snowflake supports the statement natively:

```python
dialect.supports_alter_schema()                 # False
dialect.supports_alter_schema_rename()          # False
dialect.supports_alter_schema_swap()            # False
dialect.supports_alter_schema_set_property()    # False
dialect.supports_alter_schema_managed_access()  # False
```

The remaining schema flags:

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

`supports_schema_authorization()` answers `False` and is enforced: passing
`authorization=` to `CreateSchemaExpression` raises rather than rendering the
clause.

```python
CreateSchemaExpression(d, "ar_crm", authorization="app_user").to_sql()
# UnsupportedFeatureError: 'Snowflake' dialect does not support CREATE SCHEMA
# AUTHORIZATION.
```

`if_not_exists`, `if_exists` and `cascade` are all rendered:

```python
CreateSchemaExpression(d, "ar_crm", if_not_exists=True).to_sql()[0]
# CREATE SCHEMA IF NOT EXISTS "ar_crm"

DropSchemaExpression(d, "ar_crm", if_exists=True, cascade=True).to_sql()[0]
# DROP SCHEMA IF EXISTS "ar_crm" CASCADE
```

## What a `schema_name` names here

With the database settled, the value itself is Snowflake's own: a schema inside
the current database. Two schemas in the same database are unrelated namespaces,
so `"app"."orders"` and `"crm"."orders"` are two tables that happen to share a
name.

Rendering uses double quotes, one quoted identifier per segment:

| Expression | SQL |
|---|---|
| `TableExpression(d, "orders", schema_name="app")` | `"app"."orders"` |
| `TableExpression(d, "orders")` | `"orders"` |
| `TableExpression(d, "orders", schema_name="app", alias="o")` | `"app"."orders" AS "o"` |

`QualifiedIdentifierExpression` renders the same way, and is the expression to
reach for when a two-part name is needed outside a `FROM`:

```python
QualifiedIdentifierExpression(d, "app", "orders").to_sql()[0]
# "app"."orders"
```

### Quoting and case

`format_identifier` quotes by default and escapes an embedded double quote by
doubling it, so a name that would otherwise terminate the reference stays inside
one identifier:

```python
TableExpression(d, "orders", schema_name='app"x').to_sql()[0]
# "app""x"."orders"

TableExpression(d, "orders", schema_name="My Schema").to_sql()[0]
# "My Schema"."orders"
```

The important point is that **the renderer never folds case**. `schema_name` is
emitted exactly as written, in the case it was written in:

```python
TableExpression(d, "orders", schema_name="ar_xcrm").to_sql()[0]
# "ar_xcrm"."orders"
```

That matters because Snowflake's own rule folds the other way. From the
identifier requirements:

> - When an identifier is unquoted, it is stored and resolved in uppercase.
> - When an identifier is double-quoted, it is stored and resolved exactly as
>   entered, including case.
>
> — [Identifier requirements][identifiers-syntax]

[identifiers-syntax]: https://docs.snowflake.com/en/sql-reference/identifiers-syntax

So `"ar_xcrm"` and `"AR_XCRM"` are two different schemas on Snowflake, while
`ar_xcrm` and `AR_XCRM` are the same one. A schema created through
`CREATE SCHEMA ar_xcrm` is stored as `AR_XCRM` and will **not** be found by
`"ar_xcrm"`. Create schemas with the quoting the models use, or declare the
models with the case the server stored.

Two ways to lose the quoting, both deliberate:

```python
TableExpression(d, "orders", schema_name="app", schema_need_quote=False).to_sql()[0]
# app."orders"     -- the server reads this as APP
```

`schema_need_quote=False` (and its per-role siblings `name_need_quote` and
`alias_need_quote`) reach the unquoted branch, where Snowflake applies the
uppercase rule. `need_quote=False` on a reserved word additionally emits an
`IdentifierQuotingWarning`.

A dot inside the value is not a separator either — see
[Common mistakes](#common-mistakes).

## Declaring one on a model

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

`__schema_name__` is optional and defaults to `None`, which means unqualified.
When it is set, every statement the model builds carries the namespace — `SELECT`,
`WHERE`, `ORDER BY`, `GROUP BY` and `HAVING` alike:

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

The schema reaches the `FROM` range and every unqualified column reference. It
does **not** reach a qualified column reference — see the next section.

A model without `__schema_name__` renders unqualified and leaves the choice to
the connection:

```python
PlainOrder.query().select(PlainOrder.c.id).to_sql()[0]
# SELECT "plain_orders"."id" FROM "plain_orders"
```

`SELECT *` needs no qualification and is rendered without any:

```python
Order.query().to_sql()[0]
# SELECT * FROM "app"."orders"
```

The namespace is read once, through `schema_name()`, and reaches each column
expression as it is built. Changing `__schema_name__` afterwards does not rewrite
an expression that already exists — rebuild the condition, or build it after the
change. The core guide describes the binding in full.

## Three-part column references, and what an alias does to them

Snowflake permits an unaliased range to be addressed by its relation name or by
its qualified name, so this backend emits the three-part form whenever no alias
is in effect. `SnowflakeDialect` does not override `format_column`, so the core
renderer applies:

```python
Column(d, "id", table="orders", schema_name="app").to_sql()[0]
# "app"."orders"."id"

Column(d, "id", table="orders").to_sql()[0]
# "orders"."id"
```

An aliased range **replaces** the relation name, so the alias is the only thing
left to address it by, and the schema is dropped from the column. The suppression
happens when the column expression is *constructed*, not when it is rendered:
`FieldProxy` sets `schema_name` to `None` as soon as a table alias is in effect.

```python
Order.query().select(Order.c.with_table_alias("o").id).to_sql()[0]
# SELECT "o"."id" FROM "app"."orders"
```

Two boundaries remain in force.

A column that carries a schema but no table is refused, because there is nothing
to resolve the prefix against:

```
ValueError: Snowflake: cannot qualify column 'id' with schema 'app' because no
table was given; a column reference needs a table (or an alias) to be
schema-qualified
```

And a hand-built `Column` bypasses the alias guard. `Column(d, "id", table="o",
schema_name="app")` renders `"app"."o"."id"` — the schema-qualified form of a
range that the statement aliases differently. No query the framework builds
reaches that shape; a hand-built `Column` does. Whether Snowflake accepts that
reference for an aliased range was not verified here.

Unlike PostgreSQL, this dialect does not drop the schema from a column reference
that carries a *column* alias:

```python
Order.query().select(Order.c.id.as_("x")).to_sql()[0]
# SELECT "app"."orders"."id" AS "x" FROM "app"."orders"
```

That is the core rendering, which the dialect does not override. The range is
unaliased, so a three-part reference to it is consistent with the rule above.

### Aliasing the range

The expression layer renders an aliased range in the form Snowflake expects:

```python
TableExpression(d, "orders", schema_name="app", alias="o").to_sql()[0]
# "app"."orders" AS "o"
```

At model level the range alias comes only from a join. Build the range alias and
the column accessor from the same name, and pair them with `join(..., alias=...)`:

```python
Order.query().join(
    User, on=Order.c.user_id == User.c.with_table_alias("u").id, alias="u"
).select(Order.c.id, User.c.with_table_alias("u").name).to_sql()[0]
# SELECT "app"."orders"."id", "u"."name" FROM "app"."orders"
#   JOIN "crm"."users" AS "u" ON "app"."orders"."user_id" = "u"."id"
```

The range keeps its schema; only the column prefix changes. A self-join aliases
both sides, as on any backend:

```python
Order.query().join(
    Order,
    on=Order.c.with_table_alias("c").id == Order.c.with_table_alias("p").user_id,
    alias="p",
).select(Order.c.with_table_alias("c").id, Order.c.with_table_alias("p").id).to_sql()[0]
# SELECT "c"."id", "p"."id" FROM "app"."orders"
#   JOIN "app"."orders" AS "p" ON "c"."id" = "p"."user_id"
```

The framework refuses a join whose condition still addresses the unaliased
range:

```
ValueError: cannot join crm.users with alias 'u' using a condition that still
refers to crm.users: an aliased range can only be addressed by its alias. Build
the condition from users.c.with_table_alias('u') so the reference and the alias
agree.
```

Aliasing only the column side leaves the range unaliased, and the result is SQL
the server rejects rather than SQL the framework refuses:

```python
Order.query().select(Order.c.with_table_alias("o").id).to_sql()[0]
# SELECT "o"."id" FROM "app"."orders"        <- "o" is not in scope
```

### Cross-schema joins

Each side qualifies its own range, so one statement can span two schemas with no
extra configuration:

```python
Order.query().join(User, on=Order.c.user_id == User.c.id).select(
    Order.c.id, User.c.name
).to_sql()[0]
# SELECT "app"."orders"."id", "crm"."users"."name"
#   FROM "app"."orders" JOIN "crm"."users"
#   ON "app"."orders"."user_id" = "crm"."users"."id"
```

Cross-**schema** is the limit. A cross-**database** join needs both ranges to
carry their database, and nothing in the expression layer can render that — see
[One level of qualification is what the expression layer carries](#one-level-of-qualification-is-what-the-expression-layer-carries).

## Set operations

`UNION`, `INTERSECT` and `EXCEPT` name no object of their own, so there is
nothing for them to qualify. Each branch keeps its own namespace:

```python
Order.query().select(Order.c.id).union(User.query().select(User.c.id)).to_sql()[0]
# SELECT "app"."orders"."id" FROM "app"."orders"
#   UNION SELECT "crm"."users"."id" FROM "crm"."users"
```

A `UNION` over two schema-bound models needs no special handling. A `UNION` over
two databases would need each branch to carry its database, and cannot be
expressed here.

## CTEs

A CTE is named for the rest of the query, not for the database, so its own name
is bare. Where a `WITH` clause is rendered, the core renderer emits the name
through `format_identifier` and qualifies nothing — the query inside it still
carries the model's schema:

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

**The query builder does not reach that path on this backend.**
`SnowflakeDialect.supports_basic_cte()` answers `False`, so constructing a
`CTEQuery` raises before any SQL is built:

```python
from rhosocial.activerecord.query.cte_query import CTEQuery

CTEQuery(backend)
# UnsupportedFeatureError: 'Snowflake' dialect does not support CTE (Common Table
# Expressions). Suggestion: This backend does not support CTE queries. Check
# dialect.supports_basic_cte() before building a CTEQuery.
```

That is a gap in this backend's capability flags rather than a statement about
Snowflake, which supports `WITH` — `supports_recursive_cte()` on the same
dialect answers `True`. The two flags are independent, and the basic one is what
`CTEQuery` checks.

## DDL takes a schema of its own

`__schema_name__` selects the read/write namespace. It is **not** consulted when
DDL is built — a migration has to name the schema it means — but every statement
that names a schema-bearing object accepts a `schema_name` of its own, so
qualification no longer has to be assembled by hand.

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

`CreateIndexExpression` has one `schema_name` and it covers both names: the index
and the table it is built on land in the same schema.

The DML statements qualify the same way, taking a qualified `TableExpression`:

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

Because soft delete rebuilds an `UPDATE` against the model's range, `restore()`
carries the namespace down the same way `delete()` does; the core guide covers
that path.

Two statements are refused on Snowflake rather than qualified:

```python
TruncateExpression(d, "orders", schema_name="app", restart_identity=True).to_sql()
# UnsupportedFeatureError: Snowflake TRUNCATE has no RESTART IDENTITY option.

RefreshMaterializedViewExpression(d, "v_orders", schema_name="app").to_sql()
# UnsupportedFeatureError: 'Snowflake' dialect does not support REFRESH
# MATERIALIZED VIEW.
```

`SHOW` reaches a schema through its own scope clause, which is a single
identifier and so also carries one level:

```python
SnowflakeShowExpression(d, SnowflakeShowObjectType.SCHEMAS).to_sql()[0]
# SHOW SCHEMAS

SnowflakeShowExpression(d, SnowflakeShowObjectType.TABLES,
                        in_scope=SnowflakeShowScope.SCHEMA, in_name="app").to_sql()[0]
# SHOW TABLES IN SCHEMA "app"
```

### Schema-level objects this backend cannot qualify

Most of the object kinds Snowflake keeps *inside* a schema have no namespace slot
at all. `SnowflakeCreateStageExpression`, `SnowflakeCreatePipeExpression`,
`SnowflakeCreateTaskExpression`, `SnowflakeCreateStreamExpression`,
`SnowflakeCreateFileFormatExpression`, `SnowflakeCreateFunctionExpression`,
`SnowflakeCreateProcedureExpression` and their `Drop` counterparts take a bare
`name` and nothing else:

```python
SnowflakeCreateStageExpression(d, "s_int", url="s3://bucket/k").to_sql()[0]
# CREATE STAGE "s_int" URL = 's3://bucket/k'

SnowflakeDropStageExpression(d, "s_int", if_exists=True).to_sql()[0]
# DROP STAGE IF EXISTS "s_int"
```

`SnowflakeCreateWarehouseExpression` and the other warehouse statements are in
the same position, which is correct there — a warehouse is an account-level
object, not a schema-level one.

For the schema-level kinds this means the object always lands in the session's
current schema, with no way to say otherwise through the expression layer. The
connection's `schema` is the only lever.

## Which schema an unqualified name resolves against

An unqualified name is resolved by the server, not by the framework. Two different
mechanisms are involved and they are worth separating.

### The current schema

Snowflake maintains a current database and a current schema. The current schema
always belongs to the current database; it is initialised from the connection's
settings at session start, changed by `USE SCHEMA`, and implicitly changed by
`CREATE SCHEMA`. `USE DATABASE` resets it to the database's default, normally
`PUBLIC`.

In DDL and DML statements, an unqualified name is augmented with the current
database **and** the current schema. In a query it goes through the search path
instead, which is the subject of the next section.

The backend reads the current schema from the server:

```python
backend.get_current_schema()
await async_backend.get_current_schema()
```

which renders

```sql
SELECT CURRENT_SCHEMA()
```

The parentheses are required: `CURRENT_SCHEMA` is a function, and without them
Snowflake reads the token as a column reference. The framework always emits the
call form; the bare form only appears in SQL written by hand. `None` means the
search path resolves to no existing schema.

`CURRENT_SCHEMA()` takes no arguments. It is not interchangeable with
`CURRENT_SCHEMAS()` — the next section covers the difference. `CURRENT_DATABASE()`
is the counterpart at the database level, and is what this backend's introspection
uses to report the catalog name.

### `SEARCH_PATH`, and how it differs from PostgreSQL's `search_path`

`SEARCH_PATH` is Snowflake's own session parameter, not a PostgreSQL one carried
over. Its documented definition:

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

Three differences from PostgreSQL's `search_path` matter in practice:

- **It is a session parameter, set with `ALTER SESSION`,** at any of the account,
  user or session levels. PostgreSQL's is a libpq connection parameter, fixed at
  connect time. Snowflake's documentation adds a restriction PostgreSQL does not
  have: *"You cannot set this parameter within a client connection string, such
  as a JDBC or ODBC connection string. You must establish a session before
  setting a search path."*
- **Its entries may be qualified with a database.** `testdb.public` is a valid
  entry, which is how an unqualified name in a query reaches a schema outside the
  current database. PostgreSQL's entries are schema names in the current
  database.
- **It supports two pseudo-variables.** `$current` is the current schema and
  `$public` is the current database's `PUBLIC` schema. Their names are
  case-insensitive, and they may be used freely — `$public` is valid even when
  the current database has no `PUBLIC` schema. Any other entry must name a schema
  that exists, or the assignment is rejected and the previous value is retained.

The parameter's own value is a string, but **the resolved list is not**:
`CURRENT_SCHEMAS()` returns an array of fully qualified schemas, with the
pseudo-variables expanded and non-existent or invisible schemas omitted:

```sql
SELECT CURRENT_SCHEMAS();
-- ["TEST_DB1.BILLING", "TEST_DB1.PUBLIC"]
```

That is the practical difference from PostgreSQL, where `SHOW search_path`
returns a single string of schema names with no database level and no expansion
step. The literal parameter value is readable with `SHOW PARAMETERS LIKE
'search_path'`.

Two more documented behaviours, quoted rather than measured: the value is
reinterpreted on every use, so changing the current schema changes what
`$current` means; and a schema in the path being dropped, or the current database
being changed so that unqualified entries no longer exist, raises no error.
`SEARCH_PATH` is also not used inside views or UDFs — unqualified names there
resolve in the view's or UDF's schema only.

### How this backend exposes it

`SnowflakeConnectionConfig` has **no** `search_path` field. It has two fields
that touch the namespace, and they do different jobs:

- **`schema`** (with `schema_name` accepted as a legacy spelling) is handed to
  `snowflake.connector.connect()` as the connection's `schema`. This sets the
  session's current schema, and it is what a model without `__schema_name__`
  falls back on. `backend._resolve_configured_schema()` reads it, and the
  introspector uses it to decide which schema to look in when none is named.
- **`session_parameters`** is a `Dict[str, Any]` forwarded verbatim to
  `snowflake.connector.connect()`. The connector merges the dict into the session
  parameters it applies at login, which is how `SEARCH_PATH` is reached:

  ```python
  SnowflakeConnectionConfig(
      ...,
      database="TESTDB",
      session_parameters={"SEARCH_PATH": "$current, testdb.public"},
  )
  ```

  Whether that argument satisfies Snowflake's "must establish a session first"
  restriction was not verified here — this repository has no live Snowflake
  instance, and the restriction is worded against client connection strings
  rather than against the Python connector specifically. `ALTER SESSION SET
  SEARCH_PATH = ...` is the documented way and needs no such assumption.

There is no `search_path` shortcut and no per-query or per-transaction override:
the schema a statement lands in is fixed by the connection, and moving it means
opening another connection.

## Introspection reads the connection, not the server

The introspector picks its schema from the backend's `_resolve_configured_schema()`,
which reads `schema` (then the legacy `schema_name`) off the config, and falls
back to the config directly when that method is absent. It does not call
`CURRENT_SCHEMA()`.

The consequence is worth stating: **a connection whose config carries no schema
makes the introspector look in `""`**, which matches nothing in
`INFORMATION_SCHEMA`. The generated queries are `TABLE_SCHEMA = ?` against
`INFORMATION_SCHEMA.TABLES` and `INFORMATION_SCHEMA.COLUMNS`, so a
schema-bound connection and a schema-less connection do not agree on what is
being inspected. Set `schema` on the config whenever the models declare
`__schema_name__`, even if the connector's session default would have been
right.

## The empty string, and when it is caught

`""` is a mistake, not a way of saying "unqualified" — that is what `None` means.
It is rejected, but **not when the expression is built**. An expression only
collects parameters at that point — its dialect may not even be settled yet — so
strict validation happens while the statement is rendered, where the statement is
known to be whole. The failure therefore arrives later than you would expect:

```python
class Bad(ActiveRecord):
    __table_name__ = "empties"
    __schema_name__ = ""

Bad.schema_name()                        # ''           -- no error
Bad.c.id                                 # Column       -- no error
Bad.query()                              # ActiveQuery  -- no error
Bad.query().select(Bad.c.id)             # ActiveQuery  -- no error
Bad.query().select(Bad.c.id).to_sql()    # ValueError   -- here
```

The message names the expression at fault:

```
ValueError: Column.schema_name must be a non-empty string; use None for an
unqualified reference
```

```
ValueError: TableExpression.schema_name must be a non-empty string; use None for
an unqualified reference
```

A blank string is rejected the same way as an empty one — the check strips
whitespace first, so `"   "` is refused too. A non-string is rejected with its
own message:

```
ValueError: TableExpression.schema_name must be a string or None, not int
```

The reason to reject rather than treat `""` as absent: `format_table` decides
whether to qualify from `bool(expr.schema_name)`, which is false for `""`, and
takes the unqualified branch. A caller who asked for `"app"."orders"` would get
`"orders"` with no error, no warning and no affected-row count to notice it by.
On Snowflake that is the table in the session's current schema, or in the first
schema on the search path that exists — so the statement runs, and writes to
somewhere else.

Two places do **not** apply this rule, and both are worth knowing before relying
on it:

- **The Snowflake TYPE DDL.** `SnowflakeCreateTypeExpression`,
  `SnowflakeAlterTypeExpression` and `SnowflakeDropTypeExpression` render the
  namespace themselves rather than through the core validator, so an empty value
  produces an empty quoted segment instead of raising:

  ```python
  SnowflakeDropTypeExpression(d, "label", schema_name="").to_sql()[0]
  # DROP TYPE ""."label"
  ```

  Their own check is narrower: `database_name` without `schema_name` is refused,
  at construction.

- **`TruncateExpression`** raises the `TableExpression` wording, because it
  renders its table through a `TableExpression` internally. The message names the
  object that validated the value, not the statement you wrote.

## Common mistakes

**Treating `__schema_name__` as enough to locate an object.** On this backend it
is one of two levels. `"app"."orders"` addresses the `orders` table in the schema
`app` **of whatever database the connection is attached to**, and nothing in the
rendered SQL says which. Two connections, two databases, one identical statement.
See
[Snowflake is the only backend with a schema layer of its own](#snowflake-is-the-only-backend-with-a-schema-layer-of-its-own).

**Expecting a database to be renderable.** `TableExpression`, `Column`,
`WildcardExpression` and `QualifiedIdentifierExpression` have no database field,
and a dotted value stays inside one quoted segment. The Snowflake TYPE DDL is the
only family that accepts both levels. See
[One level of qualification is what the expression layer carries](#one-level-of-qualification-is-what-the-expression-layer-carries).

**Creating a schema and expecting it in another database.** `CreateSchemaExpression`
has no database field, and Snowflake's `CREATE SCHEMA` grammar has no database
qualifier: the schema lands in the session's current database. Use a connection
already attached to the target database.

**Expecting `ALTER SCHEMA` to be available.** Snowflake supports the statement;
this backend does not model it. There is no `AlterSchemaExpression` and the five
`supports_alter_schema*()` flags answer `False`.

**A dot in `__table_name__` is not a namespace.** The identifier is quoted as a
single unit:

```python
class User(ActiveRecord):
    __table_name__ = "app.users"

User.query().select(User.c.id).to_sql()[0]
# SELECT "app.users"."id" FROM "app.users"    -- a table named literally "app.users"
```

**A dot in `__schema_name__` is not a namespace either.** Each segment is quoted
separately, so a dot inside one stays inside that one:

```python
TableExpression(d, "orders", schema_name="TESTDB.app").to_sql()[0]
# "TESTDB.app"."orders"     -- a schema literally named "TESTDB.app"
```

**Declaring a lowercase schema and finding it missing.** The renderer preserves
case, and Snowflake folds unquoted identifiers to upper case. `CREATE SCHEMA app`
stores `APP`; `__schema_name__ = "app"` renders `"app"` and will not find it. See
[Quoting and case](#quoting-and-case).

**Aliasing only one side of a join, or only the column side.** Build the range
alias and the column accessor from the same name, and pair them with
`join(..., alias=...)`. See [Aliasing the range](#aliasing-the-range).

**Expecting construction to raise.** Nothing rejects a bad `schema_name` until the
statement renders. A model-level mistake therefore survives every step up to and
including query building, and fails at the point the SQL is assembled.

**Looking for `search_path` on the config.** There is no such field. `schema`
sets the session's current schema; `session_parameters` forwards Snowflake's own
parameters. See
[`SEARCH_PATH`, and how it differs from PostgreSQL's `search_path`](#search_path-and-how-it-differs-from-postgresqls-search_path).

**Leaving the config's `schema` unset while the models are schema-bound.**
Introspection reads the config, not `CURRENT_SCHEMA()`, and looks in `""` when
there is nothing to read. See
[Introspection reads the connection, not the server](#introspection-reads-the-connection-not-the-server).

**Assuming a CTE query can be built.** `supports_basic_cte()` answers `False` on
this dialect, so `CTEQuery` raises. See [CTEs](#ctes).

## Recommended layering

- **Single schema** — set no `__schema_name__`, and set `schema` on the
  connection config so introspection looks in the same place the statements
  resolve against.
- **One schema per database, connection per database** — the shape Snowflake's
  namespace actually has. Because the database is what disambiguates the schema,
  and the database belongs to the connection, this is the case where qualifying
  with `__schema_name__` buys the least: the search path and the current schema
  already carry it. Use `__schema_name__` for the models that deviate from the
  connection's schema.
- **Several schemas in one database** — set `__schema_name__` on the models that
  deviate. Cross-schema joins work without extra configuration, each side
  qualifying its own range. The cost is a three-part column reference on every
  statement that touches the model, since an unaliased range carries its schema
  all the way through.
- **Several databases** — a separate connection per database, not a wider
  `schema_name`. A single statement spanning two databases cannot be expressed
  through the current expression layer.