# src/rhosocial/activerecord/backend/impl/snowflake/reserved_words.py
"""
Snowflake reserved words list.

Source: Snowflake Documentation
"""

SNOWFLAKE_RESERVED_WORDS = frozenset({
    "all", "alter", "and", "any", "array", "as", "between", "by", "case",
    "cast", "check", "column", "connect", "create", "cross", "current_date",
    "current_timestamp", "database", "decimal", "default", "delete", "desc",
    "distinct", "drop", "else", "exists", "false", "fetch", "for", "from",
    "full", "grant", "group", "having", "ilike", "in", "inner", "insert",
    "int", "integer", "intersect", "into", "is", "join", "left", "like",
    "limit", "localtime", "natural", "not", "null", "of", "on", "or",
    "order", "outer", "primary", "qualify", "regexp", "right", "rollup",
    "row", "sample", "schema", "select", "set", "share", "show", "table",
    "then", "time", "timestamp", "to", "trigger", "true", "truncate",
    "union", "unique", "update", "using", "values", "when", "where",
    "with", "year", "zone",
})
