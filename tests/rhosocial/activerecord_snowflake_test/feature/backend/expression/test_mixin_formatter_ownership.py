# tests/rhosocial/activerecord_snowflake_test/feature/backend/expression/test_mixin_formatter_ownership.py
"""One formatter per wildcard kind: the mixin area's structural guard.

The defect this test stands over was a single private renderer
(``_render_snowflake_wildcard``) called by two independent public formatters,
``format_all_columns_wildcard`` and ``format_row_count_wildcard``.  Those two
positions are different grammars in core (spec 4.10), so a shared body lets a
change meant for one position silently move the other.

The rule enforced here: inside ``impl/snowflake/mixins/**`` a private
``_render_*`` / ``_format_*`` helper may not be called by two or more public
``format_*`` methods of the same class, unless the entry is allow-listed with a
written reason.  Two reasons are legitimate:

* a pure primitive utility that renders one token or number both callers already
  own (no clause or node-kind choice happens inside it), or
* a helper that renders a fixed sub-node which genuinely has the same spelling
  in both positions.

Everything else -- a renderer that selects between node kinds on the caller's
behalf -- is the defect, and a new entry cannot appear without someone writing
down why.  The allow-list is checked in both directions, so an entry that stops
being needed fails instead of lingering as permission.

Source is read as text and parsed with ``ast``; the scanned modules themselves
are never imported, so an import cycle or a side effect cannot make this pass by
accident.  Only the package's location is looked up.
"""

import ast
import importlib.util
import pathlib

PREFIXES = ("_render_", "_format_")
PUBLIC_FORMATTER_PREFIX = "format_"

#: ``<module file>:<class>.<helper>`` -> why the helper is allowed to serve more
#: than one public formatter.  Keep the reason specific: "it is shared" is the
#: thing the guard exists to refuse.
ALLOWED_SHARED_HELPERS = {
    "ddl_type.py:SnowflakeTypeDDLMixin._format_type_name": (
        "Pure primitive utility: it renders the quoted schema/name token of one "
        "type node and makes no clause or node-kind choice. CREATE, ALTER and DROP "
        "each place that same token in their own statement skeleton."
    ),
    "types.py:SnowflakeTypeSupportMixin._format_number": (
        "Pure primitive utility: it renders one precision-and-scale pair from the "
        "caller's own node. The two numeric type formatters pass their own numbers "
        "in; no type kind or clause grammar is selected here."
    ),
}


def _mixins_root() -> pathlib.Path:
    spec = importlib.util.find_spec("rhosocial.activerecord.backend.impl.snowflake.mixins")
    assert (
        spec is not None and spec.submodule_search_locations
    ), "the Snowflake mixins package could not be located; the scan would be empty"
    return pathlib.Path(list(spec.submodule_search_locations)[0])


def _is_private_helper(name: str) -> bool:
    return name.startswith(PREFIXES) and not (name.startswith("__") and name.endswith("__"))


def _self_calls(method: ast.AST) -> set:
    """Names of attributes of ``self`` named like a private renderer."""
    found = set()
    for node in ast.walk(method):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and _is_private_helper(node.attr)
        ):
            found.add(node.attr)
    return found


def _shared_helper_callers() -> dict:
    """``(module, class, helper)`` -> set of public ``format_*`` methods calling it."""
    callers = {}
    root = _mixins_root()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for klass in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
            methods = {
                node.name: node
                for node in klass.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            helpers = {name for name in methods if _is_private_helper(name)}
            for formatter_name, formatter in methods.items():
                if not formatter_name.startswith(PUBLIC_FORMATTER_PREFIX):
                    continue
                for helper in _self_calls(formatter) & helpers:
                    callers.setdefault((path.name, klass.name, helper), set()).add(formatter_name)
    return callers


def _violations(callers: dict) -> dict:
    return {key: sorted(formatters) for key, formatters in callers.items() if len(formatters) >= 2}


def _key(key: tuple) -> str:
    module, klass, helper = key
    return f"{module}:{klass}.{helper}"


def test_no_private_renderer_serves_two_formatters_unless_allow_listed():
    violations = _violations(_shared_helper_callers())
    unlisted = {
        _key(key): formatters
        for key, formatters in violations.items()
        if _key(key) not in ALLOWED_SHARED_HELPERS
    }
    assert not unlisted, (
        "these private renderers are called by two or more public formatters of "
        f"the same class: {unlisted}. Give each kind its own formatter, or "
        "allow-list the helper with a written reason in "
        "ALLOWED_SHARED_HELPERS."
    )


def test_the_allow_list_matches_reality():
    """Both directions: no stale permission, and every reason is written."""
    violations = _violations(_shared_helper_callers())
    detected = {_key(key) for key in violations}
    allowed = set(ALLOWED_SHARED_HELPERS)
    assert detected == allowed, (
        "the shared-helper allow-list drifted from the source. "
        f"detected={sorted(detected)} allowed={sorted(allowed)}. "
        "An allow-listed helper that no longer serves two formatters must be "
        "removed; a newly shared helper must be listed with a reason."
    )
    for key, reason in ALLOWED_SHARED_HELPERS.items():
        assert reason.strip(), f"{key} is allow-listed with an empty reason"


def test_the_wildcard_positions_own_their_renderers():
    """The original defect: one body, two formatters.  Now zero shared helpers.

    This is the guard's own regression pin -- if a future edit reintroduces a
    ``_render_snowflake_wildcard``-style body for the two wildcard positions, the
    scan above would catch it, and this assertion names the file outright.
    """
    tree = ast.parse((_mixins_root() / "wildcard.py").read_text(encoding="utf-8"))
    helpers = [
        f"{klass.name}.{name}"
        for klass in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
        for name in (
            node.name
            for node in klass.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        if _is_private_helper(name)
    ]
    assert not helpers, (
        "the wildcard mixin has private renderers again: "
        f"{helpers}. Each wildcard position renders itself; see the module "
        "docstring in mixins/wildcard.py."
    )


def test_each_allow_listed_reason_names_a_kind_of_helper():
    """The reason has to say which of the two legitimate shapes it is."""
    for key, reason in ALLOWED_SHARED_HELPERS.items():
        assert "utility" in reason.lower() or "sub-node" in reason.lower(), (
            f"{key}'s reason must say it is a pure primitive utility or a "
            f"sub-node renderer; got {reason!r}"
        )
