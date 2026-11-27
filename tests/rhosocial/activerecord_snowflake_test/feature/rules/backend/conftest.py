# tests/rhosocial/activerecord_snowflake_test/feature/rules/backend/conftest.py
"""Fixtures for the Snowflake backend's copy of the shared formal rule suite.

The rule modules are star-imported into this package, so the testsuite's
conftest fixtures are re-exported here for pytest to resolve on this backend.
Every override is derived from the installed packages and this project's
package layout; no checkout or worktree path is hardcoded. Only this
backend's ``impl/snowflake`` tree is supplied to the shared source scans.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from rhosocial.activerecord.testsuite.feature.rules.backend.conftest import *  # noqa: F401,F403
from rhosocial.activerecord.testsuite.feature.rules.backend.conftest import python_files_in
from rhosocial.activerecord.testsuite.feature.rules.backend import (
    test_no_reflection_in_expression_layer as reflection_rules,
)
from rhosocial.activerecord.testsuite.pytest_plugin import Declaration

DECLARATION = Declaration(
    uses_database=False,
    parallel=False,
    purpose="Executable assertions of the Snowflake backend's formal constraints",
    passes_means="backend source obeys the mechanical and structural rule",
    fails_means="backend source introduces a forbidden construct or dependency",
)


@pytest.fixture
def backend_expression_package() -> object:
    """The Snowflake backend's expression package."""
    return importlib.import_module("rhosocial.activerecord.backend.impl.snowflake.expression")


@pytest.fixture
def backend_dialect() -> object:
    """An instantiated Snowflake dialect (no connection is opened)."""
    dialect_cls = importlib.import_module(
        "rhosocial.activerecord.backend.impl.snowflake.dialect"
    ).SnowflakeDialect
    return dialect_cls()


@pytest.fixture
def backend_prefix(backend_dialect) -> str:
    """The prefix Snowflake-owned declarations must carry."""
    name = type(backend_dialect).__name__
    return name[: -len("Dialect")] if name.endswith("Dialect") else name


@pytest.fixture
def source_roots(backend_impl_root: Path) -> List[Tuple[str, Path]]:
    """One labelled root: this repository's ``impl/snowflake`` tree only."""
    return [("snowflake", backend_impl_root.resolve())]


@pytest.fixture
def backend_project_root(backend_impl_root: Path) -> Path:
    """Project root inferred from the installed backend package layout."""
    for candidate in [backend_impl_root] + list(backend_impl_root.parents):
        if (candidate / "tests").is_dir() and (candidate / "src").is_dir():
            return candidate
    pytest.skip("backend project root is not discoverable from the installed package")


@pytest.fixture
def backend_test_files(backend_project_root: Path) -> List[Path]:
    """Every Python test file in this backend's project."""
    files = list(python_files_in(backend_project_root / "tests"))
    assert files, f"no test files under {backend_project_root / 'tests'}"
    return files


def pinned_entries(path: Path) -> Optional[int]:
    """Number of pins in a matrix's UNCONSTRUCTIBLE literal, if it declares one."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else ([node.target] if isinstance(node, ast.AnnAssign) else [])
        )
        if not any(
            isinstance(target, ast.Name) and target.id == "UNCONSTRUCTIBLE" for target in targets
        ):
            continue
        value = node.value
        if isinstance(value, (ast.Tuple, ast.List, ast.Set, ast.Dict)):
            return len(value.elts) if not isinstance(value, ast.Dict) else len(value.keys)
        return None
    return None


@pytest.fixture
def backend_matrix_files(backend_test_files: List[Path]) -> List[Path]:
    """Round-trip matrices whose pin list actually exposes the pinned facts.

    The local rule bridges are not matrices (this conftest mentions the marker
    itself). Snowflake's round-trip matrix declares an empty pin list -- every
    collected class builds -- so it exposes no pinned entries or reasons for
    the shared rule to check; it is excluded explicitly rather than skipped
    silently.
    """
    rules_dir = Path(__file__).resolve().parent
    return [
        path
        for path in backend_test_files
        if rules_dir not in path.parents
        and "UNCONSTRUCTIBLE" in path.read_text(encoding="utf-8")
        and (pinned_entries(path) or 0) > 0
    ]


# Measured legacy sites in this backend, keyed by (source label, relative path,
# AST scope, reflection builtin) -> (count, reason). The reasons state what is
# probed, why that object is not an expression, and why a declared attribute
# cannot replace the probe. Counts are exact; line shifts do not change them.
SNOWFLAKE_REFLECTION_ENTRIES = {
    ("snowflake", "cli/introspect.py", "_refuse_unused_arguments", "getattr"): (
        2,
        "CLI reads dynamically named argparse switches; a namespace declares no attribute for them",
    ),
    ("snowflake", "cli/introspect.py", "_require_capability", "getattr"): (
        2,
        "CLI probes capability flags named by argparse switches; no declared flag on the CLI object",
    ),
    ("snowflake", "cli/introspect.py", "_serialize_for_output", "hasattr"): (
        1,
        "CLI serializer probes optional model_dump on result objects; no shared declared hook",
    ),
    ("snowflake", "cli/introspect.py", "_value_sample_arguments", "getattr"): (
        1,
        "CLI reads an argparse field by dynamic name; namespace declares no such attribute",
    ),
    ("snowflake", "cli/named_migration.py", "disconnect", "getattr"): (
        1,
        "CLI closes an optional backend connection; the protocol declares no _connection",
    ),
    ("snowflake", "cli/named_migration.py", "disconnect_async", "getattr"): (
        1,
        "async CLI cleanup reads the same driver-owned connection; no declared async attribute exists",
    ),
    ("snowflake", "cli/named_migration.py", "handle", "getattr"): (
        1,
        "CLI dispatch reads an optional argparse flag; argparse namespaces declare no attribute for it",
    ),
    ("snowflake", "examples/introspection_account_objects.py", "main", "getattr"): (
        1,
        "example closes an optional driver connection; the example object declares none",
    ),
    ("snowflake", "field.py", "SnowflakePKMixin", "getattr"): (
        1,
        "mixin chains to an optional parent hook through super(); model bases do not all declare it",
    ),
    ("snowflake", "field.py", "SnowflakePKMixin", "setattr"): (
        1,
        "mixin writes the PK under a runtime name from primary_key(); not a declared attribute",
    ),
    ("snowflake", "introspection/introspector.py", "SnowflakeIntrospectorMixin", "getattr"): (
        4,
        "introspection reads optional config, parser-result and backend attributes (schema, "
        "schema_name, name, dialect); those client objects share no declared interface",
    ),
    ("snowflake", "introspection/introspector.py", "SnowflakeIntrospectorMixin", "hasattr"): (
        1,
        "introspection guards an optional config attribute on the backend; protocol omits config",
    ),
    (
        "snowflake",
        "introspection/introspector.py",
        "_SnowflakeAsyncIntrospectorExecutor",
        "getattr",
    ): (
        1,
        "executor caches an optional driver-owned _executor from the backend; no declared executor attribute",
    ),
    ("snowflake", "mixins/backend.py", "SnowflakeBackendMixin", "getattr"): (
        13,
        "driver compatibility reads optional connector error classes, exception errno/sqlstate "
        "and alternate config schema names; no expression and no uniform declared driver attribute",
    ),
    ("snowflake", "mixins/backend.py", "SnowflakeBackendMixin", "hasattr"): (
        2,
        "backend guards a lazily injected dialect cache and optional config; neither is declared",
    ),
    ("snowflake", "mixins/collation.py", "SnowflakeCollationMixin", "getattr"): (
        2,
        "dialect reads its own optional version, composed at runtime; not declared on the mixin",
    ),
    ("snowflake", "mixins/ddl.py", "SnowflakeAlterColumnModifierMixin", "getattr"): (
        5,
        "legacy DDL formatter reads optional if_not_exists/if_exists/cascade flags on ALTER "
        "actions; other action subclasses omit them, so a declared read would raise",
    ),
    ("snowflake", "mixins/ddl_table_modifier.py", "SnowflakeTableModifierMixin", "getattr"): (
        3,
        "legacy CREATE TABLE formatter reads optional table_options/or_replace; no declared shape",
    ),
    ("snowflake", "mixins/ddl_type.py", "SnowflakeTypeDDLMixin", "getattr"): (
        3,
        "version is composed at runtime; legacy DROP TYPE formatter reads optional cascade/restrict",
    ),
    (
        "snowflake",
        "mixins/table_constraint_change_suggestion.py",
        "_freeze",
        "getattr",
    ): (
        1,
        "schema-snapshot comparison probes optional get_params on arbitrary values; no declared "
        "interface and no SQL is rendered",
    ),
    ("snowflake", "mixins/types.py", "SnowflakeTypeSupportMixin", "getattr"): (
        2,
        "type-support mixin reads its own optional version, injected at runtime and not declared",
    ),
}


@pytest.fixture
def reflection_allowlist():
    """Core's baseline entries plus this backend's measured legacy sites.

    The baseline is retained because the shared rule module's own regression
    tests exercise core scopes through this same fixture; only the snowflake
    entries are new and each carries its own reason.
    """
    return {**reflection_rules.REFLECTION_ALLOWLIST, **SNOWFLAKE_REFLECTION_ENTRIES}
