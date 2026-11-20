# Capability boundaries & fail-fast

This backend declares what Snowflake can do through `supports_*` capability
probes on the dialect. A probe answering `True` means a formatter will render a
native Snowflake clause; a probe answering `False` means the request is
**refused with `UnsupportedFeatureError` rather than silently emulated**.

> 💡 *AI prompt: "What happens when I call a formatter for a feature whose `supports_*` probe is False? Why is refusal better than emulation here?"*

## Answered true

Among the features this backend explicitly answers `True` are:

- CTEs, including recursive CTEs (but not `MATERIALIZED` hints — see below);
- window functions, `QUALIFY`, `LATERAL` joins, `GROUPING SETS` / `ROLLUP` /
  `CUBE`, advanced aggregation;
- `MERGE` and upsert (see [MERGE & upsert](../features/merge.md));
- views (`CREATE OR REPLACE`, `IF [NOT] EXISTS`);
- constraints, sequences, identity columns, `INSERT OVERWRITE`;
- introspection and JSON operations via `VARIANT` / `GET_PATH`
  (see [VARIANT & ARRAY](../features/semi_structured.md)).

## Answered false — refused, not faked

A `False` probe is a decision, not an omission. Representative examples:

| Probe | Why it is `False` here |
|-------|------------------------|
| `supports_materialized_cte()` | Snowflake's `WITH` grammar has no `MATERIALIZED` / `NOT MATERIALIZED` hint — materialisation is the optimizer's choice. |
| `supports_auto_increment_column()` | Core's two-word `AUTO_INCREMENT` marker has no Snowflake spelling; use the parameterised `IDENTITY(seed, step)` column property instead. |
| `supports_identity_generation_always()` | Snowflake's `IDENTITY` permits manual values (effectively `BY DEFAULT`); there is no `GENERATED ALWAYS` form. |
| `supports_sequence_minvalue()` / `maxvalue()` / `cycle()` / `cache()` | Snowflake's own `SEQUENCES` view reports these as "Not applicable". |
| `supports_alter_sequence_start()` | `ALTER SEQUENCE` cannot change the initial value after creation. |
| `supports_drop_table_cascade()` | No standard `CASCADE` on `DROP TABLE`. |
| `supports_alter_column_properties()` | No independent `ALTER COLUMN SET DEFAULT` clause. |
| `supports_alter_table_index_actions()` | No traditional indexes to create/drop. |
| `format_json_arrow_expression()` (ARROW mode) | Snowflake has no `->` / `->>` operators; use `JSONPathMode.FUNCTION` / `GET_PATH`. |

The pattern is consistent: when an engine has no spelling for a clause, emitting
it anyway would produce a syntax error — or worse, a statement that succeeds
with different semantics. Refusing with a suggestion is the useful outcome.

## Probes are not grants, and `False` is not an empty answer

Two distinctions matter when reading a probe:

1. **`False` vs. an empty result.** A `False` says the question cannot be asked
   of this engine. An empty list says it was asked and nothing was found. An
   operator reading "no unused indexes" for an engine that keeps no such
   counter would be reading a report nobody produced.
2. **Capability vs. privilege.** Probes describe the server, not this account's
   grants. A `True` introspection probe means the server can answer; if the
   connected role may not read the view, the engine's error arrives at
   execution. See [Database introspection](../introspection/README.md).

Most probes are constants on the dialect. A few `RETURNING`-related probes
consult the connector version through `version_at_least((7, 32, 0))`; all
introspection probes are constants, so no introspection family is gated on a
server version. What gates an introspection answer is a privilege or an account
limit, not a version floor.

## The CLI gate

The command-line `introspect` surface derives its advertised types from the same
capability map the handler consults. On the synchronous path, a declined type is
refused with exit code 2 before the introspector is reached. The `--use-async`
path writes out its own branches and does **not** consult the gate — one more
reason to treat async as experimental rather than equivalent.

## Next steps

- [Three-part naming & identifiers](../features/naming.md)
- [Database introspection](../introspection/README.md)
