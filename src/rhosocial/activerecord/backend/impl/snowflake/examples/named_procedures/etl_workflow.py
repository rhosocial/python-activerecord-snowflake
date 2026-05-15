"""Snowflake ETL workflow procedure example.

Demonstrates a multi-step ETL procedure using the imperative Procedure API:
1. Load raw data from stage (COPY INTO)
2. Transform and validate
3. MERGE into target table

Usage:
    from rhosocial.activerecord.backend.impl.snowflake.examples.named_procedures.etl_workflow import DataLoadProcedure
    from rhosocial.activerecord.backend.impl.snowflake import SnowflakeBackend
    from rhosocial.activerecord.backend.named_query.procedure import ProcedureRunner

    backend = SnowflakeBackend(connection_config=config)
    backend.connect()

    runner = ProcedureRunner(
        "rhosocial.activerecord.backend.impl.snowflake.examples.named_procedures.etl_workflow.DataLoadProcedure"
    )
    runner.load()
    result = runner.run(backend, user_params={"stage_name": "raw_data_stage", "target_table": "sales_clean"})
    print(result.success)
"""
from typing import Dict, Any

from rhosocial.activerecord.backend.named_query.procedure import Procedure, ProcedureContext


class DataLoadProcedure(Procedure):
    """ETL procedure: Stage → Transform → MERGE into target.

    Orchestrates a Snowflake data loading workflow:
    1. COPY INTO raw table from stage
    2. Validate and transform data
    3. MERGE cleaned data into target table

    Parameters:
        stage_name: Name of the Snowflake stage containing source files.
        target_table: Name of the target table for MERGE operation.
        file_format: Optional file format specification (default: CSV).
    """

    stage_name: str
    target_table: str
    file_format: str = "TYPE = CSV FIELD_OPTIONALLY_ENCLOSED_BY = '\"'"

    def run(self, ctx: ProcedureContext) -> None:
        ctx.log("Starting ETL workflow")

        # Step 1: Load raw data from stage
        ctx.log(f"Loading data from stage @{self.stage_name}")
        load_result = ctx.execute(
            "rhosocial.activerecord.backend.impl.snowflake.examples.named_queries.snow_queries.three_part_query",
            params={"database": "RAW", "schema": "STAGING", "table": "incoming_data"},
            bind="raw_data",
        )

        # Step 2: Validate loaded data
        ctx.log("Validating loaded records")
        validate_result = ctx.execute(
            "rhosocial.activerecord.backend.impl.snowflake.examples.named_queries.snow_queries.variant_data_query",
            params={"table": "raw.incoming_data"},
            bind="validated",
        )

        # Step 3: MERGE into target table
        ctx.log(f"Merging into {self.target_table}")
        merge_result = ctx.execute(
            "rhosocial.activerecord.backend.impl.snowflake.examples.named_queries.snow_queries.merge_upsert",
            params={"source": "validated_data", "target": self.target_table, "key_column": "id"},
            output=True,
        )

        ctx.log("ETL workflow completed successfully")
