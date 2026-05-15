# Snowflake Backend Knowledge Base

## Connection Parameters

Snowflake uses a fundamentally different connection model from MySQL/PostgreSQL:

### Required Parameters
- `account`: Snowflake account identifier (e.g., `RSRSBDK-YDB67606`)
- `username`: Snowflake username
- `password`: Password or PAT token

### Key Optional Parameters
- `warehouse`: Virtual warehouse for compute (e.g., `COMPUTE_WH_PARTICIPANT`)
- `database`: Default database context
- `schema`: Default schema within database
- `role`: Security role (e.g., `PARTICIPANT`, `SYSADMIN`)
- `authenticator`: Authentication method (`snowflake`, `snowflake_jwt`, `oauth`, `externalbrowser`)

### Authentication Methods
1. **Password**: Basic username/password
2. **PAT (Programmatic Access Token)**: JWT token for automation/CI
   - Generated via Snowsight: Settings > Authentication > Programmatic access tokens
   - Or via SQL: `ALTER USER ADD PROGRAMMATIC ACCESS TOKEN ...`
3. **SSO (externalbrowser)**: Browser-based SSO
4. **Key Pair**: Private key authentication
5. **OAuth**: OAuth 2.0 token

## Three-Part Naming

Snowflake uses a three-level namespace: `database.schema.table`

```sql
-- Must use three-part naming when database is not set in connection
SELECT * FROM IOWA_LIQUOR_SALES.IOWA_LIQUOR_SALES.SALES LIMIT 10;

-- Two-part naming works when database is set in connection
SELECT * FROM IOWA_LIQUOR_SALES.SALES LIMIT 10;
```

## Identifier Quoting

- Double quotes for identifiers: `"COLUMN_NAME"`
- Unquoted identifiers are uppercased by Snowflake
- Quoted identifiers preserve case (case-sensitive)

## Data Types

### Semi-Structured Types
- **VARIANT**: Universal type for JSON/Avro/Parquet data
  - Path access: `variant_col:path` (colon notation)
  - Cast: `variant_col:path::VARCHAR`
  - FLATTEN: Explode arrays/objects into rows
- **ARRAY**: Ordered sequences
  - Construction: `[1, 2, 3]` or `ARRAY_CONSTRUCT(1, 2, 3)`
  - Access: `arr[0]`
- **OBJECT**: Key-value pairs (similar to Python dict)

### Temporal Types
- **TIMESTAMP_LTZ**: Local timezone
- **TIMESTAMP_NTZ**: No timezone
- **TIMESTAMP_TZ**: With timezone

### Numeric Types
- **NUMBER(p, s)**: Exact numeric (default p=38, s=0)
- **FLOAT**: Approximate numeric (IEEE 754)

## Time Travel

Snowflake allows querying historical data:

```sql
-- Query as of a specific timestamp
SELECT * FROM my_table AT(TIMESTAMP => '2024-01-01 00:00:00');

-- Query data N seconds ago
SELECT * FROM my_table AT(OFFSET => 3600);

-- Query before a specific statement
SELECT * FROM my_table BEFORE(STATEMENT => 'uuid');
```

Retention periods:
- Standard edition: 1 day
- Enterprise edition: Up to 90 days (configurable)

## MERGE

Snowflake supports ANSI MERGE with extensions:

```sql
MERGE INTO target t
USING source s
ON t.id = s.id
WHEN MATCHED THEN UPDATE SET t.value = s.value
WHEN NOT MATCHED THEN INSERT (id, value) VALUES (s.id, s.value);
```

## QUALIFY Clause

Snowflake-specific clause for filtering window function results:

```sql
SELECT product_id, sales_date, amount,
       ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY amount DESC) AS rn
FROM sales
QUALIFY rn = 1;
```

## CLONE

Zero-copy cloning for databases, schemas, and tables:

```sql
CREATE TABLE my_table_clone CLONE my_table;
CREATE SCHEMA my_schema_clone CLONE my_schema;
```

## Stage and COPY INTO

Data loading via stages:

```sql
-- Create internal stage
CREATE STAGE my_stage;

-- Load data from stage
COPY INTO my_table FROM @my_stage/data.csv FILE_FORMAT = (TYPE = 'CSV');

-- Load from external stage (S3)
COPY INTO my_table FROM s3://my-bucket/data/ CREDENTIALS = (AWS_KEY_ID='...' AWS_SECRET_KEY='...');
```

## Warehouse Management

- Warehouses auto-suspend after inactivity (default 5 min)
- Use `client_session_keep_alive=True` for long-running operations
- Warehouse sizes: X-Small, Small, Medium, Large, X-Large, 2X-Large, etc.
- Credit consumption is proportional to warehouse size

## Error Handling

Common Snowflake error patterns:
- `002003`: Connection/session errors
- `002043`: Authentication errors
- `002622**: SQL compilation errors
- `002604**: Timeout errors
- `002301`: Integrity constraint violations
