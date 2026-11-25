# tests/core/test_source_regex_free.py
"""Guard: the backend's ``src`` tree carries no regular expressions.

Every text-reading rule in ``src`` is stated as characters -- the type-spelling
parser reads its leading word, its digit runs and its quoted names through
``.../snowflake/_scan.py``.  A pattern would read twice (once as itself, once as
the string shape it accepts) and its anchoring and word-boundary rules are the
part that breaks quietly, so the rule is that ``src`` imports no ``re`` module
at all and reads no ``re.`` attribute.

Tests are exempt: a test may still use a pattern to assert generated SQL.  Only
this repository's own ``src`` is walked, so a sibling checkout cannot make the
guard fail.
"""

import ast
from pathlib import Path
from typing import List

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"


def _source_files() -> List[Path]:
    return sorted(SRC_ROOT.rglob("*.py"))


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _re_imports(tree: ast.AST) -> List[str]:
    """List every ``import re`` / ``from re import ...`` in a parsed module."""
    found: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "re" or alias.name.startswith("re."):
                    found.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "re" or module.startswith("re."):
                found.append(f"line {node.lineno}: from {module} import ...")
    return found


def _re_attribute_sites(text: str) -> List[str]:
    """List lines where ``re`` is read as a module, i.e. a standalone ``re.``.

    The token has to start its own word, so prose that merely ends a word in
    ``re.`` -- "there.", "structure." -- is not a hit, and neither is a name
    such as ``more.`` or ``require.``.
    """
    sites: List[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pos, ch in enumerate(line):
            if ch != "r" or not line.startswith("re.", pos):
                continue
            if pos and _is_word_char(line[pos - 1]):
                continue
            sites.append(f"line {number}: re. attribute use")
            break
    return sites


@pytest.mark.parametrize(
    "path",
    _source_files(),
    ids=lambda path: path.relative_to(REPO_ROOT).as_posix(),
)
def test_module_imports_no_re(path: Path):
    """A ``src`` module never imports the ``re`` module, under any local name."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = _re_imports(tree)
    assert not imports, f"{path.relative_to(REPO_ROOT)} imports re: {imports}"


@pytest.mark.parametrize(
    "path",
    _source_files(),
    ids=lambda path: path.relative_to(REPO_ROOT).as_posix(),
)
def test_module_reads_no_re_attribute(path: Path):
    """A ``src`` module never reads an ``re.`` attribute, however it got the module."""
    sites = _re_attribute_sites(path.read_text(encoding="utf-8"))
    assert not sites, f"{path.relative_to(REPO_ROOT)} reads re: {sites}"
