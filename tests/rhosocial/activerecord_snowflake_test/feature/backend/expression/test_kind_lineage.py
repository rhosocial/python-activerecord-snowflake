# tests/rhosocial/activerecord_snowflake_test/feature/backend/expression/test_kind_lineage.py
"""The kind audit, as an assertion rather than a paragraph.

``expression-kinds.md`` decides a backend node's relation to core by one
question: *does core already ship this kind?* Two rules follow, and both are
mechanical enough to pin here:

* **Core's kind may be re-rendered, never re-classed.** A backend may override
  ``format_<kind>``; it may not put a second class behind the same kind, because
  an artifact names a kind and nothing else, so two classes under one kind leave
  the reader no way to choose (rules §7, §10).
* **An override must be reachable.** A mixin placed after the class it
  overrides never wins (§11.1), and a ``format_method`` naming a method the
  dialect does not have is a formatter that can never run.

The measured inventory this file pins, read off the running code rather than
maintained by hand:

=========================  =====
core kinds                 357
snowflake override           0
snowflake custom            33
=========================  =====

The 33 are the nodes that declare a ``format_method``; the rest of
``impl.snowflake.expression`` renders through its own ``to_sql()`` and so has no
kind to register yet. That split is recorded here rather than changed: it is
the same shape MariaDB's audit recorded for its SHOW family, and converting
those nodes is a rename of their dialect entries, not an audit finding.

Generated with the core script on a temporary copy whose ``BACKENDS`` names this
package and ``SnowflakeDialect`` -- registering a backend in
``scripts/expression_lineage.py`` is a change to the core repository, so it is
reported rather than committed here.
"""

import importlib
import inspect
import pkgutil

import pytest

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.core import Literal
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect

CORE_EXPR_PKG = "rhosocial.activerecord.backend.expression"
SNOWFLAKE_EXPR_PKG = "rhosocial.activerecord.backend.impl.snowflake.expression"


def _classes(package_path):
    """Every concrete expression class a package defines, by object identity."""
    pkg = importlib.import_module(package_path)
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


def _declares_format_method(cls):
    """Whether *cls* itself (not a base) declares the formatter name."""
    return any("format_method" in vars(klass) for klass in cls.__mro__[:-1])


def _format_method_name(cls):
    """The string ``format_method`` answers, or ``None`` when it answers none.

    ``format_method`` is a ``property``, so reading it off the *class* hands
    back the descriptor. ``__new__`` without ``__init__`` is enough: every
    implementation returns a literal or reads ``self.name``, which is a class
    attribute on the type nodes.
    """
    try:
        return cls.format_method.fget(cls.__new__(cls))
    except NotImplementedError:
        return None


@pytest.fixture(scope="module")
def dialect():
    return SnowflakeDialect()


@pytest.fixture(scope="module")
def core_kinds():
    """kind -> class name for everything core ships, minus the one value node."""
    kinds = {}
    for cls, fqn in _classes(CORE_EXPR_PKG).items():
        if issubclass(cls, Literal):
            continue  # one class carries every value kind
        kinds[cls.kind()] = fqn
    return kinds


@pytest.fixture(scope="module")
def backend_classes():
    return _classes(SNOWFLAKE_EXPR_PKG)


def test_core_ships_the_357_kinds_the_audit_counted(core_kinds):
    """The denominator, so a core change that moves it is visible here.

    Not an equality on 357 -- core keeps growing, and a new node must not fail
    this file. The floor says the walk still reaches core's package; the audit's
    number is the one measured on this branch.
    """
    assert len(core_kinds) >= 350, (
        f"only {len(core_kinds)} core kinds collected; the package walk may have "
        f"stopped early"
    )


def test_no_backend_class_replaces_a_core_kind(backend_classes, core_kinds):
    """Core's kind may be re-rendered, never re-classed (rules §7, §10).

    The audit's headline number: **zero** overrides. That is the only shape
    that keeps an artifact readable -- a kind resolves to one class, always.
    A class that genuinely specialises a core node inherits it and carries its
    own kind (``SnowflakeCreateMaterializedViewExpression`` over
    ``CreateMaterializedViewStatement``), which is what makes this zero rather
    than a rule the backend happens to dodge.
    """
    replaced = {
        cls.kind(): (fqn, core_kinds[cls.kind()])
        for cls, fqn in backend_classes.items()
        if cls.kind() in core_kinds
    }
    assert not replaced, (
        "these classes claim a kind core already ships, which would leave one "
        f"kind resolving to two classes: {replaced}"
    )


def test_every_declared_formatter_exists_on_the_dialect(dialect, backend_classes):
    """A ``format_method`` naming a method the dialect lacks can never run.

    ``to_sql()`` reports such a gap as ``UnsupportedFeatureError`` at call time;
    this asks the same question once, over the whole package, so a rename that
    orphans a formatter fails here instead of in whichever test happened to
    render that node.
    """
    missing = []
    for cls, fqn in backend_classes.items():
        method = _format_method_name(cls)
        if method is None:
            continue
        if not isinstance(method, str) or not method:
            missing.append((fqn, method))
        elif not callable(getattr(dialect, method, None)):
            missing.append((fqn, method))
    assert not missing, (
        "these classes declare a formatting entry the dialect does not have: "
        f"{sorted(missing)}"
    )


def test_a_backends_kind_carries_the_backend_name_first(backend_classes):
    """§3: the backend name goes first -- never last, never in the middle.

    Every custom kind here is spelled ``snowflake_<concept>``, and the check is
    on the prefix rather than on a list of the 33, so a node added later is
    covered without a second edit.
    """
    misfiled = sorted(
        fqn
        for cls, fqn in backend_classes.items()
        if _declares_format_method(cls) and not cls.kind().startswith("snowflake_")
    )
    assert not misfiled, (
        f"these kinds do not name their backend first: {misfiled}"
    )


def test_the_literal_mixin_precedes_the_class_it_overrides():
    """§11.1, for the one mixin this release added.

    ``SnowflakeLiteralValueMixin`` replaces ``SQLDialectBase.format_literal``.
    A base list is the MRO, so the overriding mixin must sit ahead of -- a lower
    index than -- ``SQLDialectBase``; placed after it, the override is never
    asked and every inline literal renders with the base's spellings.
    """
    from rhosocial.activerecord.backend.impl.snowflake.mixins.literal import (
        SnowflakeLiteralValueMixin,
    )

    mro = SnowflakeDialect.__mro__
    assert mro.index(SnowflakeLiteralValueMixin) < mro.index(SQLDialectBase), (
        "SnowflakeLiteralValueMixin must precede SQLDialectBase in the base list"
    )
