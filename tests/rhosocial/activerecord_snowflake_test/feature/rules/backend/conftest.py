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
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        if not any(isinstance(target, ast.Name) and target.id == "UNCONSTRUCTIBLE" for target in targets):
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
        path for path in backend_test_files
        if rules_dir not in path.parents
        and "UNCONSTRUCTIBLE" in path.read_text(encoding="utf-8")
        and (pinned_entries(path) or 0) > 0
    ]
