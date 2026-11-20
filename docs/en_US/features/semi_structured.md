# VARIANT & ARRAY

Snowflake stores semi-structured data natively. This backend exposes that
through dedicated field types, expression nodes and type adapters, rather than
flattening everything into text columns.

## Capability probes

| Probe | Answer | Notes |
|-------|--------|-------|
| `supports_variant_type()` | `True` | `VARIANT` columns and path/cast expressions |
| `supports_array_type()` | `True` | `ARRAY` columns |
| `supports_arrays()` | `True` | Native arrays |
| `supports_json_type()` | `True` | JSON lives in `VARIANT` |
| `supports_json_function(name)` | only `GET_PATH` | Arrow operators are refused |

## VARIANT

`VARIANT` holds JSON, Avro, ORC or Parquet-shaped semi-structured values.

**Path access** uses Snowflake's colon notation, and a cast appends `::`:

```sql
payload:customer:name
payload:customer:name::VARCHAR
```

The corresponding expression formatters render `expr.column:expr.path` and
`expr.column:expr.path::<target type>`. There is no `FLATTEN` wrapper here — a
path expression stays a scalar select item unless you write the flatten in the
query itself.

**JSON path operations** use `GET_PATH`. Shared JSONPath input is translated to
Snowflake's variant-path notation by dropping the leading `$.`:

```
$.customer.name  →  customer.name
```

The `->` / `->>` arrow operators do **not** exist in Snowflake. Asking for ARROW
mode raises `UnsupportedFeatureError`; use `JSONPathMode.FUNCTION` (which
renders `GET_PATH`) or `AUTO`. Where the shared `->>` meaning is "text", the
formatter appends `::VARCHAR` to the `GET_PATH` result.

## ARRAY

`ARRAY` is an ordered sequence:

```sql
[1, 2, 3]                    -- array literal
ARRAY_CONSTRUCT(1, 2, 3)     -- equivalent constructor
arr[0]                       -- zero-based element access
```

The ``SnowflakeArraySupport`` protocol declares the type; element access and
array functions are rendered by the dialect's expression and function support.

## Type adapters

| Adapter | Python ↔ Snowflake | Details |
|---------|--------------------|---------|
| `SnowflakeVariantAdapter` | `dict` / `list` ↔ `VARIANT` | `json.dumps` on write, `json.loads` on read; values already decoded by the driver pass through unchanged |
| `SnowflakeArrayAdapter` | `list` ↔ `ARRAY` | Same JSON round-trip |
| `SnowflakeVectorAdapter` | neutral `Vector` | Python `list` for `ARRAY` columns; JSON text `[1.0, 2.0]` for `VECTOR` / text bindings |

Both JSON adapters accept optional `default` and `object_hook` callables that
are forwarded to `json.dumps` / `json.loads`, so a neutral-type codec can be
plugged in without changing the adapter. `ensure_ascii=False` preserves
non-ASCII text on write.

### Neutral types with no native column

The backend pins one wire form per neutral type:

| Neutral type | Column | Wire form |
|--------------|--------|-----------|
| Geometry family | `GEOGRAPHY` / `GEOMETRY` | WKT text on write; WKT or GeoJSON accepted on read |
| `BitString` | `BINARY` | Whole bytes only — a bit length not divisible by 8 is rejected |
| `Range` / `Multirange` | `VARCHAR` | Lossless JSON with element type and bound inclusivity |
| `MacAddress` | `VARCHAR` | Canonical lowercase colon-separated text |

Snowflake `GEOGRAPHY` is spherical/WGS84 and `GEOMETRY` is planar; both accept
WKT. Set `GEOGRAPHY_OUTPUT_FORMAT='GeoJSON'` in `session_parameters` if you
prefer GeoJSON on read.

## Timestamps

`SnowflakeTimestampAdapter` handles the three timestamp flavours through a
`timestamp_type` option: `"ntz"` (default, naive), `"ltz"` (normalise to UTC for
storage, display in session timezone) and `"tz"` (preserve the offset). For the
`seconds_between` precision limit, see [Date and time differences](../querying/datetime.md).

## Next steps

- [Time travel](time_travel.md)
- [MERGE & upsert](merge.md)
