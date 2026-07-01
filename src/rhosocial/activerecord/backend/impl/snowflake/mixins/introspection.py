# src/rhosocial/activerecord/backend/impl/snowflake/mixins/introspection.py
"""SnowflakeIntrospectionMixin — schema introspection via INFORMATION_SCHEMA."""
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.introspection.types import IntrospectionScope
    from rhosocial.activerecord.backend.expression.introspection import (
        DatabaseInfoExpression,
        TableListExpression,
        ColumnInfoExpression,
        IndexInfoExpression,
        ForeignKeyExpression,
        ViewListExpression,
        ViewInfoExpression,
        TriggerListExpression,
    )


class SnowflakeIntrospectionMixin:
    """Snowflake introspection capability declaration and query formatting.

    This mixin implements the IntrospectionSupport protocol by:
    1. Declaring which introspection features Snowflake supports (supports_* methods)
    2. Formatting SQL queries for introspection (format_*_query methods)

    The format_*_query methods are called by Expression.to_sql() to generate
    database-specific SQL using INFORMATION_SCHEMA.

    Architecture flow:
        Introspector._build_*_sql() [base class]
            -> Expression(Dialect).to_sql()
                -> Dialect.format_*_query() [this mixin]
                    -> Returns SQL and parameters

    Snowflake supports introspection via INFORMATION_SCHEMA views.
    Snowflake does not support traditional indexes or triggers.
    """

    # ========== Capability Detection ==========

    def supports_introspection(self) -> bool:
        """Snowflake supports introspection via INFORMATION_SCHEMA."""
        return True

    def supports_database_info(self) -> bool:
        """Snowflake supports database info via context functions."""
        return True

    def supports_table_introspection(self) -> bool:
        """Snowflake supports table introspection via INFORMATION_SCHEMA.TABLES."""
        return True

    def supports_column_introspection(self) -> bool:
        """Snowflake supports column introspection via INFORMATION_SCHEMA.COLUMNS."""
        return True

    def supports_index_introspection(self) -> bool:
        """Snowflake does not have traditional indexes; uses constraints instead."""
        return True

    def supports_foreign_key_introspection(self) -> bool:
        """Snowflake supports foreign key introspection via INFORMATION_SCHEMA."""
        return True

    def supports_view_introspection(self) -> bool:
        """Snowflake supports view introspection via INFORMATION_SCHEMA.VIEWS."""
        return True

    def supports_trigger_introspection(self) -> bool:
        """Snowflake does not support triggers."""
        return False

    def get_supported_introspection_scopes(self) -> List["IntrospectionScope"]:
        """Get list of supported introspection scopes."""
        from rhosocial.activerecord.backend.introspection.types import IntrospectionScope
        return [
            IntrospectionScope.DATABASE,
            IntrospectionScope.TABLE,
            IntrospectionScope.COLUMN,
            IntrospectionScope.INDEX,
            IntrospectionScope.FOREIGN_KEY,
            IntrospectionScope.VIEW,
        ]

    # ========== Query Formatting ==========

    def format_database_info_query(
        self, expr: "DatabaseInfoExpression"
    ) -> Tuple[str, tuple]:
        """Format database information query using context functions."""
        sql = (
            "SELECT CURRENT_DATABASE() AS CATALOG_NAME, "
            "CURRENT_VERSION() AS SERVER_VERSION"
        )
        return (sql, ())

    def format_table_list_query(
        self, expr: "TableListExpression"
    ) -> Tuple[str, tuple]:
        """Format table list query using INFORMATION_SCHEMA.TABLES."""
        params = expr.get_params()
        schema = params.get("schema", "")
        include_views = params.get("include_views", True)
        include_system = params.get("include_system", False)
        table_type = params.get("table_type")

        conditions = ["TABLE_SCHEMA = %s"]
        sql_params: list = [schema]

        if not include_system:
            conditions.append(
                "TABLE_SCHEMA NOT IN ('information_schema', 'PUBLIC')"
            )
        if not include_views:
            conditions.append("TABLE_TYPE = 'BASE TABLE'")
        if table_type:
            conditions.append("TABLE_TYPE = %s")
            sql_params.append(table_type)

        where = " AND ".join(conditions)
        sql = (
            "SELECT TABLE_NAME, TABLE_TYPE, COMMENT "
            f"FROM INFORMATION_SCHEMA.TABLES WHERE {where} "
            "ORDER BY TABLE_NAME"
        )
        return (sql, tuple(sql_params))

    def format_column_info_query(
        self, expr: "ColumnInfoExpression"
    ) -> Tuple[str, tuple]:
        """Format column information query using INFORMATION_SCHEMA.COLUMNS."""
        params = expr.get_params()
        table_name = params.get("table_name", "")
        schema = params.get("schema", "")

        sql = (
            "SELECT COLUMN_NAME, ORDINAL_POSITION, COLUMN_DEFAULT, IS_NULLABLE, "
            "DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE, "
            "COLLATION_NAME, COMMENT "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION"
        )
        return (sql, (schema, table_name))

    def format_index_info_query(
        self, expr: "IndexInfoExpression"
    ) -> Tuple[str, tuple]:
        """Format index information query using constraints.

        Snowflake does not have traditional indexes. This queries
        TABLE_CONSTRAINTS + KEY_COLUMN_USAGE for PRIMARY KEY and UNIQUE
        constraints, which serve as the closest analog.
        """
        params = expr.get_params()
        table_name = params.get("table_name", "")
        schema = params.get("schema", "")

        sql = (
            "SELECT tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE, "
            "kcu.COLUMN_NAME, kcu.ORDINAL_POSITION "
            "FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
            "  ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
            "  AND tc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA "
            "WHERE tc.TABLE_SCHEMA = %s AND tc.TABLE_NAME = %s "
            "  AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE') "
            "ORDER BY tc.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
        )
        return (sql, (schema, table_name))

    def format_foreign_key_query(
        self, expr: "ForeignKeyExpression"
    ) -> Tuple[str, tuple]:
        """Format foreign key information query.

        Joins REFERENTIAL_CONSTRAINTS, KEY_COLUMN_USAGE, and
        TABLE_CONSTRAINTS to resolve referenced table and columns.
        """
        params = expr.get_params()
        table_name = params.get("table_name", "")
        schema = params.get("schema", "")

        sql = (
            "SELECT rc.CONSTRAINT_NAME, rc.UPDATE_RULE, rc.DELETE_RULE, "
            "kcu.COLUMN_NAME, kcu.ORDINAL_POSITION, "
            "utc.TABLE_NAME AS REFERENCED_TABLE_NAME, "
            "ukcu.COLUMN_NAME AS REFERENCED_COLUMN_NAME "
            "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
            "  ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
            "  AND rc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA "
            "JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS utc "
            "  ON rc.UNIQUE_CONSTRAINT_NAME = utc.CONSTRAINT_NAME "
            "  AND rc.UNIQUE_CONSTRAINT_SCHEMA = utc.CONSTRAINT_SCHEMA "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ukcu "
            "  ON rc.UNIQUE_CONSTRAINT_NAME = ukcu.CONSTRAINT_NAME "
            "  AND rc.UNIQUE_CONSTRAINT_SCHEMA = ukcu.CONSTRAINT_SCHEMA "
            "  AND kcu.POSITION_IN_UNIQUE_CONSTRAINT = ukcu.ORDINAL_POSITION "
            "WHERE rc.CONSTRAINT_SCHEMA = %s "
            "  AND kcu.TABLE_NAME = %s "
            "ORDER BY rc.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
        )
        return (sql, (schema, table_name))

    def format_view_list_query(
        self, expr: "ViewListExpression"
    ) -> Tuple[str, tuple]:
        """Format view list query using INFORMATION_SCHEMA.VIEWS."""
        params = expr.get_params()
        schema = params.get("schema", "")
        include_system = params.get("include_system", False)

        conditions = ["TABLE_SCHEMA = %s"]
        sql_params: list = [schema]

        if not include_system:
            conditions.append(
                "TABLE_SCHEMA NOT IN ('information_schema', 'PUBLIC')"
            )

        where = " AND ".join(conditions)
        sql = (
            "SELECT TABLE_NAME, VIEW_DEFINITION, CHECK_OPTION, IS_UPDATABLE "
            f"FROM INFORMATION_SCHEMA.VIEWS WHERE {where} "
            "ORDER BY TABLE_NAME"
        )
        return (sql, tuple(sql_params))

    def format_view_info_query(
        self, expr: "ViewInfoExpression"
    ) -> Tuple[str, tuple]:
        """Format single view information query."""
        params = expr.get_params()
        view_name = params.get("view_name", "")
        schema = params.get("schema", "")

        sql = (
            "SELECT TABLE_NAME, VIEW_DEFINITION, CHECK_OPTION, IS_UPDATABLE "
            "FROM INFORMATION_SCHEMA.VIEWS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s"
        )
        return (sql, (schema, view_name))

    def format_trigger_list_query(
        self, expr: "TriggerListExpression"
    ) -> Tuple[str, tuple]:
        """Snowflake does not support triggers; return empty result."""
        return ("SELECT 1 WHERE 1 = 0", ())

    def format_trigger_info_query(
        self, expr
    ) -> Tuple[str, tuple]:
        """Snowflake does not support triggers; return empty result."""
        return ("SELECT 1 WHERE 1 = 0", ())