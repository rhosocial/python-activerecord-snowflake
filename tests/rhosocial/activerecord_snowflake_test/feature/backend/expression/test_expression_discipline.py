# tests/rhosocial/activerecord_snowflake_test/feature/backend/expression/test_expression_discipline.py
"""The expression area's two standing rules, as assertions.

expression-dialect §12:

* **No I/O.** An expression test constructs and renders; it starts no
  connection, creates no database and touches no file. Anything that needs a
  real server belongs to the scenario-driven integration tests, where a
  warehouse is part of the setup.
* **Parallel by default.** Independent cases are what makes a module-wide
  ``xdist_group`` unjustified, so the only serial mark allowed here would be
  one that states its reason.

The first rule is checked by reading this area's own modules -- the modules
where an import of a backend, a driver or the scenario fixture would show up
-- rather than by trusting the review that wrote them. The second is checked
by reading the mark inventory: no case in this area carries ``xdist_group``,
which is what lets ``--dist=loadgroup`` (set in ``plugins/expression_xdist``)
actually spread them.
"""

import ast
import pathlib

AREA = pathlib.Path(__file__).resolve().parent

#: Names that mean "this module reaches a database", plus the module path
#: fragments a live test would import to reach one. The dialect, the
#: expression nodes and the serialisers are absent on purpose: they are pure
#: data, which is the point of the area.
FORBIDDEN_IMPORTS = (
    "snowflake.connector",
    "snowflake_connector",
    "aiosqlite",
    "fakesnow",
)
FORBIDDEN_NAMES = (
    "SnowflakeBackend",
    "AsyncSnowflakeBackend",
    "SnowflakeConnectionConfig",
)

#: Canned SQL a live helper would send. The renderers produce this text
#: themselves, so a literal statement appearing at module level means a module
#: is driving an engine rather than asking a dialect to render.
FORBIDDEN_CALLS = ("connect", "execute", "executemany", "cursor")


def _modules():
    return sorted(
        path
        for path in AREA.glob("*.py")
        if path.name != pathlib.Path(__file__).name and path.name != "__init__.py"
    )


def test_no_expression_test_imports_a_connection():
    """The dialect and the nodes need no driver, and importing one would say
    this area had started measuring a server."""
    offenders = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(
                        alias.name == bad or alias.name.startswith(bad + ".")
                        for bad in FORBIDDEN_IMPORTS
                    ):
                        offenders.append((path.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if any(
                    module == bad or module.startswith(bad + ".")
                    for bad in FORBIDDEN_IMPORTS
                ):
                    offenders.append((path.name, module))
                for alias in node.names:
                    if alias.name in FORBIDDEN_NAMES:
                        offenders.append((path.name, alias.name))
    assert not offenders, (
        "these expression-area modules import the live side: "
        f"{sorted(set(offenders))}. A case that needs a warehouse belongs in "
        f"the scenario-driven integration tests (§12)."
    )


def test_no_expression_test_drives_a_connection():
    """``.connect()`` / ``.execute()`` / ``.cursor()`` are the calls a live
    test makes; rendering is ``.to_sql()`` and stops there."""
    offenders = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in FORBIDDEN_CALLS:
                    offenders.append((path.name, node.lineno, node.func.attr))
    assert not offenders, (
        f"these expression-area calls reach a connection: {sorted(offenders)}"
    )


def test_no_case_in_this_area_is_grouped_for_serial_execution():
    """§12.1: parallel is the default, and ``xdist_group`` needs a reason.

    No case here carries one, which is the honest state: every case builds its
    own dialect and asserts on a rendered string or an artifact, so none of
    them can interfere. A future case that genuinely must run alone can add
    the mark -- and this test is where it has to say why.
    """
    grouped = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "xdist_group":
                    grouped.append((path.name, node.lineno))
            if isinstance(node, ast.Constant) and node.value == "xdist_group":
                grouped.append((path.name, node.lineno))
    assert not grouped, (
        f"these cases are pinned to one worker: {grouped}. Per §12.1 that needs "
        f"a stated reason, and no case in this area has one."
    )


def test_the_parallel_default_covers_this_area():
    """The plugin's scoped area is this directory, spelled the same way.

    A path that drifted (a renamed package, a moved directory) would silently
    stop matching and the area would fall back to serial without any test
    noticing, so the two spellings are compared here.
    """
    from plugins.expression_xdist import _expression_area_root

    assert _expression_area_root() == AREA, (
        f"the xdist plugin defaults to parallel for {_expression_area_root()}, "
        f"but the expression area is {AREA}"
    )
