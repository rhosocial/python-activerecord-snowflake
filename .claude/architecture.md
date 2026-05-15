# Snowflake Backend Architecture

| Item | Value |
|------|-------|
| **Database** | Snowflake Cloud Data Warehouse |
| **Python Driver** | snowflake-connector-python >= 3.0.0 |
| **Python Version** | 3.8+ (including 3.13t/3.14t free-threaded) |
| **Async Strategy** | Thread pool wrapper (no native async driver) |
| **Package** | rhosocial-activerecord-snowflake |

## Directory Structure

```text
src/rhosocial/activerecord/backend/impl/snowflake/
├── __init__.py              # Public API exports
├── __main__.py              # CLI entry point
├── backend.py               # SnowflakeBackend (sync)
├── async_backend.py         # AsyncSnowflakeBackend (thread pool)
├── config.py                # SnowflakeConnectionConfig
├── dialect.py               # SnowflakeDialect
├── transaction.py           # SnowflakeTransactionManager (sync)
├── async_transaction.py     # AsyncSnowflakeTransactionManager
├── mixins.py                # Shared non-I/O mixins
├── protocols.py             # Snowflake-specific protocols
├── adapters.py              # Type adapters
└── types.py                 # SnowflakeVariant, SnowflakeArray
```

## Snowflake-Specific Features

| Feature | Protocol | Description |
|---------|----------|-------------|
| Time Travel | `SnowflakeTimeTravelSupport` | AT/BEFORE point-in-time queries |
| VARIANT Type | `SnowflakeVariantSupport` | Semi-structured data (JSON-like) |
| ARRAY Type | `SnowflakeArraySupport` | Native array operations |
| CLONE | `SnowflakeCloneSupport` | Zero-copy table/schema/database cloning |
| Stage | `SnowflakeStageSupport` | Data staging and COPY INTO |

## Key Differences from Other Backends

- **No RETURNING clause**: Must use separate SELECT after INSERT
- **Three-part naming**: `database.schema.table` required
- **Warehouse-based compute**: Connections specify warehouse; auto-suspend may drop idle connections
- **PAT authentication**: JWT tokens instead of passwords for automation
- **READ COMMITTED only**: Snowflake does not support other isolation levels
- **Double-quote identifiers**: Case-sensitive when quoted

## Expression-Dialect System

All SQL generation follows the Expression-Dialect separation pattern:
- Expression classes define **what** to express (structure)
- Dialect methods define **how** to express it (formatting)

Never generate SQL directly in Expression classes — always delegate to the dialect.
