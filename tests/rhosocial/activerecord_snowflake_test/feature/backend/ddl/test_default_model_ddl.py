# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_default_model_ddl.py
"""Default-type model rendering — Snowflake.

``DefaultUser`` declares plain Python types with no ``UseSqlType``; Snowflake
derives the column types via its own suggestion mapping.
"""

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.examples.ddl_default_types import DefaultUser


def _render() -> str:
    sql, _ = DefaultUser.generate_create_table(dialect=SnowflakeDialect()).to_sql()
    return sql


def test_default_user_has_no_explicit_sql_types():
    assert DefaultUser.__table_field_sql_types__ == {}


def test_snowflake_default_user_ddl_columns():
    sql = _render()
    assert 'CREATE TABLE "default_users"' in sql
    assert '"id" INTEGER PRIMARY KEY' in sql
    assert '"username" TEXT NOT NULL' in sql
    assert '"email" TEXT NOT NULL' in sql
    assert '"is_active" BOOLEAN NOT NULL' in sql
    assert '"balance" DOUBLE NOT NULL' in sql
    assert '"created_at" DATETIME NOT NULL' in sql
    assert '"metadata" TEXT NOT NULL' in sql
    assert '"avatar" BLOB NOT NULL' in sql
    assert '"birthday" DATE' in sql