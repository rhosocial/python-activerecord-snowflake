# src/rhosocial/activerecord/backend/impl/snowflake/functions/semi_structured.py
"""Snowflake semi-structured data (VARIANT/ARRAY/OBJECT) function factories."""

from typing import Union, Optional, TYPE_CHECKING

from rhosocial.activerecord.backend.expression import bases, core

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


def _to_expr(dialect: "SQLDialectBase", expr: Union[str, "bases.BaseExpression"]):
    if isinstance(expr, bases.BaseExpression):
        return expr
    return core.Column(dialect, expr)


def _literal(dialect: "SQLDialectBase", value) -> "core.Literal":
    return core.Literal(dialect, value)


# ========== ARRAY Functions ==========


def array_construct(
    dialect: "SQLDialectBase",
    *args: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ARRAY_CONSTRUCT function call.

    Constructs an ARRAY from one or more expressions.
    """
    exprs = [_to_expr(dialect, a) for a in args]
    return core.FunctionCall(dialect, "ARRAY_CONSTRUCT", *exprs)


def array_append(
    dialect: "SQLDialectBase",
    array: Union[str, "bases.BaseExpression"],
    element: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ARRAY_APPEND function call.

    Appends an element to the end of an ARRAY.
    """
    return core.FunctionCall(
        dialect, "ARRAY_APPEND", _to_expr(dialect, array), _to_expr(dialect, element)
    )


def array_insert(
    dialect: "SQLDialectBase",
    array: Union[str, "bases.BaseExpression"],
    index: Union[int, str, "bases.BaseExpression"],
    element: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ARRAY_INSERT function call.

    Inserts an element into an ARRAY at a specified position.
    """
    idx = _literal(dialect, index) if not isinstance(index, bases.BaseExpression) else index
    return core.FunctionCall(
        dialect, "ARRAY_INSERT", _to_expr(dialect, array), idx, _to_expr(dialect, element)
    )


def array_remove(
    dialect: "SQLDialectBase",
    array: Union[str, "bases.BaseExpression"],
    element: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ARRAY_REMOVE function call.

    Removes all occurrences of an element from an ARRAY.
    """
    return core.FunctionCall(
        dialect, "ARRAY_REMOVE", _to_expr(dialect, array), _to_expr(dialect, element)
    )


def array_size(
    dialect: "SQLDialectBase",
    array: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ARRAY_SIZE function call.

    Returns the number of elements in an ARRAY.
    """
    return core.FunctionCall(dialect, "ARRAY_SIZE", _to_expr(dialect, array))


def array_contains(
    dialect: "SQLDialectBase",
    array: Union[str, "bases.BaseExpression"],
    element: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ARRAY_CONTAINS function call.

    Checks whether an ARRAY contains a specified element.
    """
    return core.FunctionCall(
        dialect, "ARRAY_CONTAINS", _to_expr(dialect, element), _to_expr(dialect, array)
    )


def array_agg(
    dialect: "SQLDialectBase",
    expr: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create ARRAY_AGG aggregate function call.

    Returns the input values, pivoted into an ARRAY.
    """
    return core.FunctionCall(dialect, "ARRAY_AGG", _to_expr(dialect, expr))


# ========== OBJECT Functions ==========


def object_construct(
    dialect: "SQLDialectBase",
    **kwargs: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create OBJECT_CONSTRUCT function call from key-value pairs.

    Constructs an OBJECT from key-value pairs. Each key is a string
    and each value is an expression.
    """
    args = []
    for key, value in kwargs.items():
        args.append(_literal(dialect, key))
        args.append(_to_expr(dialect, value))
    return core.FunctionCall(dialect, "OBJECT_CONSTRUCT", *args)


def object_keys(
    dialect: "SQLDialectBase",
    obj: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create OBJECT_KEYS function call.

    Returns a list of keys in an OBJECT.
    """
    return core.FunctionCall(dialect, "OBJECT_KEYS", _to_expr(dialect, obj))


def object_delete(
    dialect: "SQLDialectBase",
    obj: Union[str, "bases.BaseExpression"],
    *keys: str,
) -> "core.FunctionCall":
    """Create OBJECT_DELETE function call.

    Removes one or more keys from an OBJECT.
    """
    exprs = [_to_expr(dialect, obj)]
    for key in keys:
        exprs.append(_literal(dialect, key))
    return core.FunctionCall(dialect, "OBJECT_DELETE", *exprs)


# ========== VARIANT / JSON Functions ==========


def parse_json(
    dialect: "SQLDialectBase",
    expr: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create PARSE_JSON function call.

    Parses a JSON string and returns a VARIANT value.
    """
    return core.FunctionCall(dialect, "PARSE_JSON", _to_expr(dialect, expr))


def try_parse_json(
    dialect: "SQLDialectBase",
    expr: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create TRY_PARSE_JSON function call.

    Parses a JSON string and returns NULL if parsing fails.
    """
    return core.FunctionCall(dialect, "TRY_PARSE_JSON", _to_expr(dialect, expr))


def to_variant(
    dialect: "SQLDialectBase",
    expr: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create TO_VARIANT function call.

    Converts any Snowflake data type to VARIANT.
    """
    return core.FunctionCall(dialect, "TO_VARIANT", _to_expr(dialect, expr))


def to_array(
    dialect: "SQLDialectBase",
    expr: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create TO_ARRAY function call.

    Converts any Snowflake data type to ARRAY.
    """
    return core.FunctionCall(dialect, "TO_ARRAY", _to_expr(dialect, expr))


def to_object(
    dialect: "SQLDialectBase",
    expr: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create TO_OBJECT function call.

    Converts any Snowflake data type to OBJECT.
    """
    return core.FunctionCall(dialect, "TO_OBJECT", _to_expr(dialect, expr))


def get_path(
    dialect: "SQLDialectBase",
    variant: Union[str, "bases.BaseExpression"],
    path: Union[str, "bases.BaseExpression"],
) -> "core.FunctionCall":
    """Create GET_PATH function call.

    Extracts a value from a VARIANT/OBJECT using a path string.
    """
    return core.FunctionCall(
        dialect, "GET_PATH", _to_expr(dialect, variant), _to_expr(dialect, path)
    )


def flatten(
    dialect: "SQLDialectBase",
    input_expr: Union[str, "bases.BaseExpression"],
    path: Optional[str] = None,
    outer: bool = False,
    recursive: bool = False,
    mode: str = "BOTH",
) -> "bases.BaseExpression":
    """Create a FLATTEN table function.

    FLATTEN is a table function that produces a lateral view of a
    VARIANT, OBJECT, or ARRAY column, expanding nested collection
    elements into multiple rows.

    This returns a ``FunctionCall`` but should be used in a
    ``LATERAL FLATTEN(...)`` context.

    Args:
        dialect: SQL dialect instance.
        input_expr: The INPUT expression (column or subquery).
        path: Optional path to the element within the VARIANT.
        outer: If True, includes rows for NULL or missing paths.
        recursive: If True, recursively flattens all sub-elements.
        mode: Either 'OBJECT', 'ARRAY', or 'BOTH' (default).
    """
    from rhosocial.activerecord.backend.expression.core import FunctionCall

    exprs = [_to_expr(dialect, input_expr)]
    kwargs_list = []
    if path is not None:
        kwargs_list.append((_literal(dialect, "PATH"), _literal(dialect, path)))
    if outer:
        kwargs_list.append((_literal(dialect, "OUTER"), _literal(dialect, True)))
    if recursive:
        kwargs_list.append((_literal(dialect, "RECURSIVE"), _literal(dialect, True)))
    if mode != "BOTH":
        kwargs_list.append((_literal(dialect, "MODE"), _literal(dialect, mode)))
    if kwargs_list:
        for k, v in kwargs_list:
            exprs.append(k)
            exprs.append(v)
    return FunctionCall(dialect, "FLATTEN", *exprs)