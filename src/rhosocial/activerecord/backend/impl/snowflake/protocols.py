"""Snowflake backend-specific protocol definitions.

This module defines protocols for features exclusive to Snowflake,
which are not part of the SQL standard and not supported by other
mainstream databases.
"""
from typing import Protocol, runtime_checkable, Any, Optional


@runtime_checkable
class SnowflakeTimeTravelSupport(Protocol):
    """Snowflake time travel query protocol.

    Feature Source: Snowflake native (not SQL standard)

    Snowflake supports querying historical data at a specific point in time
    using AT/BEFORE clauses:
    - AT(TIMESTAMP => 'timestamp'): Query data as of a specific timestamp
    - AT(OFFSET => N): Query data N seconds ago
    - AT(STATEMENT => 'uuid'): Query data as of a statement
    - BEFORE(STATEMENT => 'uuid'): Query data before a statement
    - BEFORE(TIMESTAMP => 'timestamp'): Query data before a timestamp

    Official Documentation:
    - https://docs.snowflake.com/en/sql-reference/constructs/at-before
    """

    def supports_time_travel(self) -> bool:
        """Whether time travel queries are supported."""
        ...

    def format_time_travel_at_timestamp(self, timestamp: str) -> str:
        """Format AT(TIMESTAMP => ...) clause."""
        ...

    def format_time_travel_at_offset(self, seconds: int) -> str:
        """Format AT(OFFSET => ...) clause."""
        ...

    def format_time_travel_before_timestamp(self, timestamp: str) -> str:
        """Format BEFORE(TIMESTAMP => ...) clause."""
        ...


@runtime_checkable
class SnowflakeVariantSupport(Protocol):
    """Snowflake VARIANT semi-structured data type protocol.

    Feature Source: Snowflake native (not SQL standard)

    Snowflake VARIANT type can store semi-structured data (JSON, Avro, ORC, Parquet).
    Key operations:
    - Path access: variant_col:path (dot notation) or variant_col['path']
    - Type casting: variant_col:path::type
    - FLATTEN: Explode semi-structured data into rows

    Official Documentation:
    - https://docs.snowflake.com/en/sql-reference/data-types-semistructured
    """

    def supports_variant_type(self) -> bool:
        """Whether VARIANT type is supported."""
        ...

    def format_variant_path_access(self, column: str, path: str) -> str:
        """Format VARIANT path access expression."""
        ...

    def format_variant_cast(self, column: str, path: str, target_type: str) -> str:
        """Format VARIANT path access with explicit cast."""
        ...


@runtime_checkable
class SnowflakeArraySupport(Protocol):
    """Snowflake ARRAY type protocol.

    Feature Source: Snowflake native (not SQL standard)

    Snowflake ARRAY type supports:
    - Array construction: [1, 2, 3] or ARRAY_CONSTRUCT(1, 2, 3)
    - Array access: arr[0] or arr[INDEX]
    - ARRAY_APPEND, ARRAY_INSERT, ARRAY_REMOVE, etc.

    Official Documentation:
    - https://docs.snowflake.com/en/sql-reference/data-types-semistructured
    """

    def supports_array_type(self) -> bool:
        """Whether ARRAY type is supported."""
        ...

    def format_array_construct(self, elements: str) -> str:
        """Format array construction expression."""
        ...

    def format_array_access(self, array_expr: str, index: str) -> str:
        """Format array element access expression."""
        ...


@runtime_checkable
class SnowflakeCloneSupport(Protocol):
    """Snowflake CLONE protocol.

    Feature Source: Snowflake native (not SQL standard)

    Snowflake supports cloning databases, schemas, and tables:
    - CREATE TABLE ... CLONE source_table
    - CREATE SCHEMA ... CLONE source_schema
    - CREATE DATABASE ... CLONE source_database

    Clones are zero-copy operations that share storage with the source.

    Official Documentation:
    - https://docs.snowflake.com/en/sql-reference/sql/create-clone
    """

    def supports_clone(self) -> bool:
        """Whether CLONE operations are supported."""
        ...

    def format_clone_table(self, target: str, source: str) -> str:
        """Format CREATE TABLE ... CLONE statement."""
        ...


@runtime_checkable
class SnowflakeStageSupport(Protocol):
    """Snowflake stage (data staging area) protocol.

    Feature Source: Snowflake native (not SQL standard)

    Snowflake stages are locations where data files are stored for
    loading/unloading:
    - Internal stages: Snowflake-managed storage
    - External stages: Cloud storage (S3, Azure, GCS)
    - PUT/GET: Upload/download files to/from stages
    - COPY INTO: Load data from stages into tables

    Official Documentation:
    - https://docs.snowflake.com/en/sql-reference/sql/create-stage
    - https://docs.snowflake.com/en/sql-reference/sql/copy-into-table
    """

    def supports_stages(self) -> bool:
        """Whether stage operations are supported."""
        ...

    def format_copy_into_table(
        self, table: str, stage: str, file_format: Optional[str] = None
    ) -> str:
        """Format COPY INTO table FROM stage statement."""
        ...
