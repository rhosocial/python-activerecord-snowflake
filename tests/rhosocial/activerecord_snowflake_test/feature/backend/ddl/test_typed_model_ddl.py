# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_typed_model_ddl.py
"""Cross-backend UseSqlType demonstration — Snowflake rendering.

The shared ``TypedUser`` model (core generic types) renders Snowflake-native
SQL without any per-dialect string mappings. Dialect instantiation needs no
DB server; only ``to_sql()`` is exercised here.
"""

from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.examples.ddl_types import TypedUser


def _render() -> str:
    sql, _ = TypedUser.generate_create_table(dialect=SnowflakeDialect()).to_sql()
    return sql


def test_snowflake_typed_user_ddl_columns():
    sql = _render()
    assert 'CREATE TABLE "typed_users"' in sql
    assert '"id" INTEGER PRIMARY KEY' in sql
    assert '"username" VARCHAR NOT NULL' in sql
    assert '"email" VARCHAR NOT NULL' in sql
    assert '"is_active" BOOLEAN NOT NULL' in sql
    assert '"balance" DECIMAL' in sql
    assert '"birthday" DATE' in sql
    assert '"created_at" DATETIME NOT NULL' in sql
    assert '"bio" TEXT' in sql
    assert '"metadata" JSON' in sql
    assert '"big_counter" BIGINT' in sql
    assert '"avatar" BLOB' in sql
    assert '"wake_up_time" TIME' in sql


def test_snowflake_typed_user_no_per_dialect_string_keys():
    for _field_name, marker in TypedUser.__table_field_sql_types__.items():
        assert not hasattr(marker, "dialect_types")
        assert marker.data_type is not None