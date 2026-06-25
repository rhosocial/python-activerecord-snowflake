# src/rhosocial/activerecord/backend/impl/snowflake/functions/__init__.py
"""Snowflake-specific SQL function factories."""

from .semi_structured import (
    array_construct,
    array_append,
    array_insert,
    array_remove,
    array_size,
    array_contains,
    array_agg,
    flatten,
    get_path,
    object_construct,
    object_keys,
    object_delete,
    parse_json,
    to_array,
    to_object,
    to_variant,
    try_parse_json,
)
from .geospatial import (
    st_make_point,
    st_distance,
    st_within,
    st_contains,
    st_intersects,
    st_as_text,
    st_as_geojson,
)

__all__ = [
    # ARRAY functions
    "array_construct",
    "array_append",
    "array_insert",
    "array_remove",
    "array_size",
    "array_contains",
    "array_agg",
    # Semi-structured functions
    "flatten",
    "get_path",
    "object_construct",
    "object_keys",
    "object_delete",
    "parse_json",
    "to_array",
    "to_object",
    "to_variant",
    "try_parse_json",
    # Geospatial functions
    "st_make_point",
    "st_distance",
    "st_within",
    "st_contains",
    "st_intersects",
    "st_as_text",
    "st_as_geojson",
]