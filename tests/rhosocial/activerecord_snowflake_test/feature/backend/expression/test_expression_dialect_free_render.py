# tests/rhosocial/activerecord_snowflake_test/feature/backend/expression/test_expression_dialect_free_render.py
"""A Snowflake node renders through the dialect, never around it.

An expression collects parameters only. The one route from a node to SQL is
``BaseExpression._render``: it reads the node's declared ``format_method``,
looks the formatter up on the dialect and calls it. A node that overrides
``to_sql`` / ``_render`` reaches the dialect itself and bypasses that lookup,
so a probe or a refusal the formatter performs cannot govern it.

The statements, clauses and DDL nodes in ``impl.snowflake.expression`` used to
render themselves. This file pins the shape they were converted to: a
declaration on the class, and a node built without a dialect -- which is what a
declaration-time tree is -- rendering through ``to_sql(dialect)``.
"""

import importlib
import inspect
import pkgutil

from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.expression.show import (
    SnowflakeShowObjectType,
    SnowflakeShowScope,
    SnowflakeShowStatement,
)

SNOWFLAKE_EXPR_PKG = "rhosocial.activerecord.backend.impl.snowflake.expression"


def _expression_classes():
    """Every concrete expression class this package defines, by object identity."""
    pkg = importlib.import_module(SNOWFLAKE_EXPR_PKG)
    found = {}
    for _, modname, _ in pkgutil.walk_packages(
        pkg.__path__, pkg.__name__ + ".", onerror=lambda x: None
    ):
        try:
            module = importlib.import_module(modname)
        except Exception:  # noqa: BLE001 -- an unimportable module defines nothing
            continue
        for name in dir(module):
            obj = getattr(module, name, None)
            if (
                isinstance(obj, type)
                and obj.__module__ == modname
                and issubclass(obj, BaseExpression)
                and obj is not BaseExpression
                and not inspect.isabstract(obj)
            ):
                found.setdefault(obj, f"{modname}.{name}")
    return found


def _declares_a_formatter(cls):
    """Whether *cls* resolves a formatter that is not the base's sentinel."""
    for klass in cls.__mro__:
        if "format_method" in vars(klass):
            return klass is not BaseExpression
    return False


def _show(**overrides):
    """A SHOW statement with every clause populated, dialect bound or not."""
    kwargs = {
        "object_type": SnowflakeShowObjectType.TABLES,
        "in_scope": SnowflakeShowScope.SCHEMA,
        "in_name": "PUBLIC",
        "like": "raw%",
        "limit": 5,
    }
    kwargs.update(overrides)
    return kwargs


EXPECTED_SHOW = "SHOW TABLES LIKE 'raw%' IN SCHEMA \"PUBLIC\" LIMIT 5"


def test_a_dialect_free_show_statement_renders_through_to_sql():
    """A node built without a backend renders when ``to_sql`` supplies one."""
    statement = SnowflakeShowStatement(None, **_show())

    assert statement.to_sql(SnowflakeDialect()) == (EXPECTED_SHOW, ())


def test_the_supplied_dialect_and_a_construction_time_binding_agree():
    """``to_sql(dialect)`` does not change what a bound node renders."""
    dialect = SnowflakeDialect()
    unbound = SnowflakeShowStatement(None, **_show())
    bound = SnowflakeShowStatement(dialect, **_show())

    assert unbound.to_sql(dialect) == bound.to_sql()


def test_the_show_statement_declares_a_formatter_and_owns_no_to_sql():
    """The class names its formatter; it does not route SQL itself."""
    statement = SnowflakeShowStatement(None, **_show())

    assert statement.format_method == "format_show_statement"
    assert "to_sql" not in vars(SnowflakeShowStatement)
    assert "_render" not in vars(SnowflakeShowStatement)


def test_no_snowflake_expression_renders_itself():
    """The rule over the whole package: declarations replace overrides.

    A node with a ``to_sql`` / ``_render`` of its own is a node the dialect
    cannot refuse or probe, because the dispatch never runs. Zero offenders is
    the state the conversion left; this is what keeps it that way.
    """
    offenders = sorted(
        fqn
        for cls, fqn in _expression_classes().items()
        if ("to_sql" in vars(cls) or "_render" in vars(cls))
        and not _declares_a_formatter(cls)
    )
    assert not offenders, (
        "these Snowflake expression classes render themselves instead of "
        f"declaring a format_method: {offenders}"
    )
