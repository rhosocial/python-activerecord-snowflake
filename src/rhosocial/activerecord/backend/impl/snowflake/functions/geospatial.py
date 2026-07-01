# src/rhosocial/activerecord/backend/impl/snowflake/functions/geospatial.py
"""Snowflake geospatial (GEOGRAPHY/GEOMETRY) function factories."""

from typing import Union, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases, core

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


def _to_expr(dialect: "SQLDialectBase", expr: Union[str, "bases.BaseExpression"]):
    if isinstance(expr, bases.BaseExpression):
        return expr
    return core.Column(dialect, expr)


def st_make_point(
    dialect: "SQLDialectBase",
    longitude: Union[float, str, "bases.BaseExpression"],
    latitude: Union[float, str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ST_MAKEPOINT function call.

    Creates a GEOGRAPHY point from longitude and latitude.
    """
    lon = (_to_expr(dialect, longitude) if isinstance(longitude, bases.BaseExpression)
           else core.Literal(dialect, longitude))
    lat = (_to_expr(dialect, latitude) if isinstance(latitude, bases.BaseExpression)
           else core.Literal(dialect, latitude))
    return core.FunctionCall(dialect, "ST_MAKEPOINT", lon, lat)


def st_distance(
    dialect: "SQLDialectBase",
    geo1: Union[str, "bases.BaseExpression"],
    geo2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ST_DISTANCE function call.

    Returns the distance between two GEOGRAPHY or GEOMETRY objects in meters.
    """
    return core.FunctionCall(
        dialect, "ST_DISTANCE", _to_expr(dialect, geo1), _to_expr(dialect, geo2)
    )


def st_within(
    dialect: "SQLDialectBase",
    geo1: Union[str, "bases.BaseExpression"],
    geo2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ST_WITHIN function call.

    Returns True if geo1 is completely within geo2.
    """
    return core.FunctionCall(
        dialect, "ST_WITHIN", _to_expr(dialect, geo1), _to_expr(dialect, geo2)
    )


def st_contains(
    dialect: "SQLDialectBase",
    geo1: Union[str, "bases.BaseExpression"],
    geo2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ST_CONTAINS function call.

    Returns True if geo1 completely contains geo2.
    """
    return core.FunctionCall(
        dialect, "ST_CONTAINS", _to_expr(dialect, geo1), _to_expr(dialect, geo2)
    )


def st_intersects(
    dialect: "SQLDialectBase",
    geo1: Union[str, "bases.BaseExpression"],
    geo2: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ST_INTERSECTS function call.

    Returns True if geo1 and geo2 intersect.
    """
    return core.FunctionCall(
        dialect, "ST_INTERSECTS", _to_expr(dialect, geo1), _to_expr(dialect, geo2)
    )


def st_as_text(
    dialect: "SQLDialectBase",
    geo: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ST_ASTEXT function call.

    Returns the WKT (Well-Known Text) representation of a geometry.
    """
    return core.FunctionCall(dialect, "ST_ASTEXT", _to_expr(dialect, geo))


def st_as_geojson(
    dialect: "SQLDialectBase",
    geo: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ST_ASGEOJSON function call.

    Returns the GeoJSON representation of a geometry.
    """
    return core.FunctionCall(dialect, "ST_ASGEOJSON", _to_expr(dialect, geo))