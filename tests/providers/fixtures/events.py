"""No procedural CreateTableExpression factories for Snowflake.

All Snowflake DDL is loaded directly from the *.sql* schema files under
tests/rhosocial/activerecord_snowflake_test/feature/<feature>/schema/.
The TABLE_EXPRESSIONS dictionary is intentionally empty so that
provider code falls back to loading the schema file.
"""
from typing import Callable, Dict

TABLE_EXPRESSIONS: Dict[str, Callable] = {}
