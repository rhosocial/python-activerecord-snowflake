# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## [v1.0.0.dev1] - 2025-05-16

### Added

- Snowflake backend implementation (`SnowflakeBackend`, `AsyncSnowflakeBackend`) with sync/async parity via thread pool wrapper
- `SnowflakeDialect` with version-aware feature detection, double-quote identifier formatting, and pyformat parameter placeholders (`%s`)
- `SnowflakeConnectionConfig` with Snowflake-specific fields: account, warehouse, schema, role, authenticator, PAT/token/OAuth/private key authentication, session keep-alive, and timeout controls
- Type adapters: `SnowflakeVariantAdapter` (dict/list ↔ VARIANT), `SnowflakeArrayAdapter` (list ↔ ARRAY), `SnowflakeBooleanAdapter` (bool ↔ 0/1), `SnowflakeDecimalAdapter` (Decimal ↔ numeric), `SnowflakeTimestampAdapter` (datetime ↔ timestamp)
- Type helpers: `SnowflakeVariant` and `SnowflakeArray` wrapper classes with serialization support
- Snowflake-specific protocols: `SnowflakeTimeTravelSupport`, `SnowflakeVariantSupport`, `SnowflakeArraySupport`, `SnowflakeCloneSupport`, `SnowflakeStageSupport`
- Snowflake-specific mixins implementing protocols: `SnowflakeTimeTravelMixin`, `SnowflakeVariantMixin`, `SnowflakeArrayMixin`, `SnowflakeCloneMixin`, `SnowflakeStageMixin`
- Snowflake-specific SQL formatting: time travel (`AT/BEFORE`), VARIANT path access (`col:path::type`), `ARRAY_CONSTRUCT`, `CLONE TABLE`, `COPY INTO` from stage
- Transaction management with `SnowflakeTransactionManager` and `AsyncSnowflakeTransactionManager` (READ COMMITTED only, with `RuntimeWarning` for unsupported isolation levels)
- 22 standard SQL dialect capabilities: CTE (including recursive), window functions, JSON (via VARIANT), MERGE, QUALIFY, upsert (via MERGE), lateral join, advanced grouping, views, schema, indexes, constraints, introspection, and more
- Named connection examples: `spider2_snow`, `analytics_dev`, `analytics_prod`
- Named query examples: `daily_sales_report`, `time_travel_query`, `variant_data_query`, `merge_upsert`, `three_part_query`
- Named procedure example: `DataLoadProcedure` (COPY INTO → validate → MERGE)
- Test suite with 172 unit tests covering dialect formatting, capability detection, type adapters, config, mock backend, and protocol conformance
- Integration tests against real Snowflake (Spider 2.0 Snow dataset) with gold result comparison, auto-skipped when no credentials configured
- GitHub Actions CI workflow testing Python 3.8–3.14 and free-threaded 3.14t
- GitHub Actions publish workflow for TestPyPI and PyPI via Trusted Publishers (OIDC)
