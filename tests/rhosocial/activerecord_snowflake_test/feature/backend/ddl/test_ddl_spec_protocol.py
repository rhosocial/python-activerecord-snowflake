# tests/rhosocial/activerecord_snowflake_test/feature/backend/ddl/test_ddl_spec_protocol.py
"""Snowflake DDL feature-spec claiming tests (``build_spec``).

Covers the Snowflake-specific Specs (external-table partition, semi-structured
column types) and the generic Specs on the Snowflake dialect:

- ``SnowflakeExternalPartition`` translates to ``SnowflakePartitionClause``.
- VARIANT / ARRAY / OBJECT column Specs translate to native Snowflake types.
- Generic Specs still translate via the core ``DDLSpecBuildingMixin``.
- Foreign Specs (``PartitionSpec`` marker, unknown objects) return ``None``.
"""

import pytest

from rhosocial.activerecord.base import (
    CheckSpec,
    PartitionSpec,
    PrimaryKeySpec,
    UniqueSpec,
)
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.ddl_spec import (
    SnowflakeArrayColumnSpec,
    SnowflakeExternalPartition,
    SnowflakeObjectColumnSpec,
    SnowflakeVariantColumnSpec,
)


@pytest.fixture
def dialect():
    return SnowflakeDialect()


class TestProtocolConformance:
    def test_build_spec_returns_none_for_unknown(self, dialect):
        assert dialect.build_spec(object()) is None

    def test_build_spec_returns_none_for_base_partition_marker(self, dialect):
        assert dialect.build_spec(PartitionSpec()) is None


class TestGenericSpecTranslation:
    def test_unique_spec(self, dialect):
        result = dialect.build_spec(UniqueSpec(["a", "b"], name="uq_ab"))
        assert result.columns == ["a", "b"]

    def test_check_spec_lazy(self, dialect):
        result = dialect.build_spec(
            CheckSpec(lambda d: Column(d, "age") >= 18, name="ck_age")
        )
        assert result.check_condition is not None

    def test_primary_key_single(self, dialect):
        result = dialect.build_spec(PrimaryKeySpec(["id"]))
        from rhosocial.activerecord.backend.expression.statements import (
            ColumnConstraint,
            ColumnConstraintType,
        )
        assert isinstance(result, ColumnConstraint)
        assert result.constraint_type == ColumnConstraintType.PRIMARY_KEY


class TestSnowflakePartitionSpecs:
    def test_external_partition(self, dialect):
        spec = SnowflakeExternalPartition(["created_date", "region"])
        expr = dialect.build_spec(spec)
        assert type(expr).__name__ == "SnowflakePartitionClause"
        sql, _ = expr.to_sql()
        assert "PARTITION BY" in sql

    def test_external_partition_requires_columns(self):
        with pytest.raises(ValueError):
            SnowflakeExternalPartition([])


class TestSnowflakeTypeSpecs:
    def test_variant_column(self, dialect):
        result = dialect.build_spec(SnowflakeVariantColumnSpec("data"))
        sql, _ = result.patched_data_type.to_sql(dialect)
        assert sql == "VARIANT"

    def test_array_column(self, dialect):
        result = dialect.build_spec(SnowflakeArrayColumnSpec("arr"))
        sql, _ = result.patched_data_type.to_sql(dialect)
        assert sql == "ARRAY"

    def test_object_column(self, dialect):
        result = dialect.build_spec(SnowflakeObjectColumnSpec("obj"))
        sql, _ = result.patched_data_type.to_sql(dialect)
        assert sql == "OBJECT"


class TestModelIntegration:
    def test_model_spec_constraints(self, dialect):
        from rhosocial.activerecord.model import ActiveRecord

        class T(ActiveRecord):
            __table_name__ = "t"
            __table_constraints__ = [
                UniqueSpec(columns=["a", "b"], name="uq_ab"),
            ]
            a: int
            b: int

        expr = T.generate_create_table(dialect)
        assert expr.table_constraints[0].columns == ["a", "b"]

    def test_model_type_specs_render(self, dialect):
        from rhosocial.activerecord.model import ActiveRecord

        class T(ActiveRecord):
            __table_name__ = "t"
            __table_constraints__ = [
                SnowflakeVariantColumnSpec("data"),
                SnowflakeArrayColumnSpec("arr"),
                SnowflakeObjectColumnSpec("obj"),
            ]
            data: object
            arr: object
            obj: object

        expr = T.generate_create_table(dialect)
        sql, _ = expr.to_sql()
        assert "VARIANT" in sql
        assert "ARRAY" in sql
        assert "OBJECT" in sql