# Three-part naming & identifiers

Snowflake resolves objects in a three-level namespace. This is the most visible
difference between this backend and a local database, and the dialect owns the
rendering so model code stays portable.

## The namespace

```
database.schema.table
```

- With `database` and `schema` set in the connection config, an unqualified
  model name resolves against that context.
- With only `database` set, a two-part name (`schema.table`) works.
- With no database context — for example, a CLI invocation given only an
  account — fully qualified three-part names are required.

```sql
SELECT * FROM "MYDB"."PUBLIC"."users";   -- three-part
SELECT * FROM "PUBLIC"."users";          -- two-part, database in context
```

The same rule applies to views, stages, streams and other named objects.

## Identifier quoting and case

- Identifiers are rendered with **double quotes**: `"COLUMN_NAME"`.
- Snowflake folds an **unquoted** identifier to upper case; a **quoted**
  identifier preserves its case and is case-sensitive.
- Because quoting is case-sensitive, pass the catalogue's own spelling when
  naming a database or object programmatically. An introspection result key
  may arrive upper-cased from the service; the parser layer normalises keys
  before handing records to core code.

This matters for aliases too: time-travel clauses and aggregate projections
render aliases in upper case (`"NULL_COUNT"`) because that is how Snowflake
returns them.

## Placeholders

The driver uses **pyformat** (`%s`) placeholders; bind values travel as a
separate parameter tuple and are never spliced into statement text:

```python
sql, params = User.query().where(User.c.age >= 18).to_sql()
# sql:    'SELECT ... WHERE "age" >= %s'
# params: (18,)
```

The bind order follows the placeholders as rendered, not the order in which an
expression happened to be constructed. A named-relation renderer keeps the
object name, the time-travel suffix and the alias as separate concerns, so a
three-level name and its `AT(...)` clause do not interfere.

## Cross-schema references

A relation may carry its own qualifier that overrides the connection default;
joins can therefore mix qualifiers. Each side is rendered independently, and
every identifier in a qualified name is quoted. See the introspection chapter
for how cross-database and cross-schema listings are scoped.

## Next steps

- [VARIANT & ARRAY](semi_structured.md)
- [Database introspection](../introspection/README.md)
