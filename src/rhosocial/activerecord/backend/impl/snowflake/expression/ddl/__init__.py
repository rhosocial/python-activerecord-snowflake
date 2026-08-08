# src/rhosocial/activerecord/backend/impl/snowflake/expression/ddl/__init__.py
"""Snowflake DDL expressions.

Directory structure:
- warehouse.py: CREATE / ALTER / DROP WAREHOUSE expressions
- stage.py:     CREATE / ALTER / DROP STAGE and COPY INTO expressions
"""
from .warehouse import (
    SnowflakeAlterWarehouseMode,
    SnowflakeCreateWarehouseExpression,
    SnowflakeAlterWarehouseExpression,
    SnowflakeDropWarehouseExpression,
)
from .stage import (
    SnowflakeCopyIntoMode,
    SnowflakeCreateStageExpression,
    SnowflakeAlterStageExpression,
    SnowflakeDropStageExpression,
    SnowflakeCopyIntoExpression,
)

__all__ = [
    "SnowflakeAlterWarehouseMode",
    "SnowflakeCreateWarehouseExpression",
    "SnowflakeAlterWarehouseExpression",
    "SnowflakeDropWarehouseExpression",
    "SnowflakeCopyIntoMode",
    "SnowflakeCreateStageExpression",
    "SnowflakeAlterStageExpression",
    "SnowflakeDropStageExpression",
    "SnowflakeCopyIntoExpression",
]
