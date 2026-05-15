# Project Overview: rhosocial-activerecord-snowflake

## Project Name
- **Repository Name**: python-activerecord-snowflake
- **Python Package Name**: rhosocial-activerecord-snowflake

## Project Purpose

This project is a Snowflake backend implementation for the `rhosocial-activerecord` Python package. It provides Snowflake cloud data warehouse support with the elegant ActiveRecord pattern interface, including VARIANT/ARRAY semi-structured types, time travel queries, and MERGE operations.

## Key Design Principles

1. **Backend Implementation**: Extends core ActiveRecord with Snowflake-specific features
2. **Driver**: Uses `snowflake-connector-python` for database connectivity
3. **Namespace Package**: Integrates with the rhosocial namespace package architecture
4. **Async via Thread Pool**: Since snowflake-connector-python has no native async driver, `AsyncSnowflakeBackend` wraps sync operations in `asyncio.run_in_executor()`
5. **Cloud-Native Awareness**: Snowflake's three-level namespace (database.schema.table), warehouse-based compute, and PAT authentication are first-class concerns

## Python Version Support

- **Supported**: Python 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14 (standard GIL builds)
- **Free-threaded**: Python 3.14t (experimental, pending `cffi` 3.14t support verification)
- **NOT supported**: Python 3.13t — `snowflake-connector-python` depends on `cryptography` which depends on `cffi`, and `cffi` does not support free-threaded CPython 3.13

## Current Status

This project is under active development. Key features implemented:

- SnowflakeDialect with version-aware feature detection
- SnowflakeBackend (sync) and AsyncSnowflakeBackend (async via thread pool)
- SnowflakeConnectionConfig with account, warehouse, schema, role, authenticator support
- Type adapters: VARIANT, ARRAY, Boolean, Decimal, Timestamp
- Protocol definitions: TimeTravel, Variant, Array, Clone, Stage
- Transaction management (Snowflake only supports READ COMMITTED)

## Snowflake-Specific Considerations

- **No RETURNING clause**: Snowflake does not support `RETURNING` — use MERGE or separate queries instead
- **Three-part naming**: Tables must be referenced as `database.schema.table`
- **Double-quote identifiers**: `"COLUMN_NAME"` (Snowflake is case-sensitive when quoted)
- **pyformat placeholders**: `%s` style (snowflake-connector-python uses pyformat)
- **PAT authentication**: Programmatic Access Tokens (JWT) for CI/automation
- **Warehouse lifecycle**: Virtual warehouses auto-suspend; consider `client_session_keep_alive=True`

## Version Control and Changelog

This project adheres to the same version control, branching, commit message, and changelog management standards as the main `python-activerecord` project.
