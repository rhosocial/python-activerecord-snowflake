# tests/rhosocial/activerecord_snowflake_test/feature/backend/core/test_support_switches_take_no_arguments.py
"""``supports_*`` is a support switch: no arguments, one bool.

A capability flag answers "does this dialect configuration have capability k",
so its only input is the dialect instance. Anything that needs a name or a kind
is either a separate switch (closed vocabulary) or a format-time validation
(open vocabulary) -- never an argument to ``supports_*``. This is core's rule,
and this backend is subject to it too: a probe that grows a parameter is a
capability model that has drifted from the one the protocol declares.
"""

import ast
from pathlib import Path

import pytest


def _source_files():
    """Every Python file in this repository's ``src`` tree."""
    root = Path(__file__).resolve().parents[6] / "src"
    files = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return files


def _required_arguments(func: ast.FunctionDef):
    """Parameters that must be passed, excluding ``self``."""
    args = func.args
    positional = list(args.posonlyargs) + list(args.args)
    required = positional[1 : len(positional) - len(args.defaults)]
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        if default is None:
            required.append(arg)
    return [a.arg for a in required]


def _annotates_bool(func: ast.FunctionDef) -> bool:
    """A switch declares ``-> bool`` (or no annotation, which cannot be judged here)."""
    annotation = func.returns
    if annotation is None:
        return True
    if isinstance(annotation, ast.Name) and annotation.id == "bool":
        return True
    if isinstance(annotation, ast.Constant) and annotation.value == "bool":
        return True
    return False


def _offenders(tree, label):
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not item.name.startswith("supports_"):
                continue
            missing = _required_arguments(item)
            if missing:
                found.append(f"{label}:{item.lineno} {item.name}({', '.join(missing)})")
            elif not _annotates_bool(item):
                found.append(
                    f"{label}:{item.lineno} {item.name} does not return bool"
                )
    return found


@pytest.mark.parametrize("path", _source_files(), ids=lambda p: str(p.name))
def test_support_switch_takes_no_required_argument(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = _offenders(tree, path.name)
    assert not offenders, "\n".join(offenders)


def test_the_scan_reaches_the_source_tree():
    files = _source_files()
    assert len(files) > 50, f"only {len(files)} source files were scanned"


def test_the_scan_flags_a_planted_violation(tmp_path):
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n" "    def supports_thing(self, name):\n" "        return False\n",
        encoding="utf-8",
    )
    tree = ast.parse(probe.read_text(encoding="utf-8"))
    assert _offenders(tree, "probe")


def test_the_scan_flags_a_planted_keyword_only_violation(tmp_path):
    """A required keyword-only parameter is still an argument."""
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n" "    def supports_thing(self, *, kind):\n" "        return False\n",
        encoding="utf-8",
    )
    tree = ast.parse(probe.read_text(encoding="utf-8"))
    assert _offenders(tree, "probe")


def test_the_scan_flags_a_planted_non_bool_annotation(tmp_path):
    """A switch that answers with a mapping is a catalogue, not a switch."""
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "from typing import Dict\n"
        "class P:\n"
        "    def supports_thing(self) -> Dict[str, bool]:\n"
        "        return {}\n",
        encoding="utf-8",
    )
    tree = ast.parse(probe.read_text(encoding="utf-8"))
    offenders = _offenders(tree, "probe")
    assert offenders and "does not return bool" in offenders[0]


def test_the_scan_accepts_a_quoted_bool_annotation(tmp_path):
    probe = tmp_path / "_probe.py"
    probe.write_text(
        'class P:\n'
        '    def supports_thing(self) -> "bool":\n'
        "        return False\n",
        encoding="utf-8",
    )
    tree = ast.parse(probe.read_text(encoding="utf-8"))
    assert not _offenders(tree, "probe")


def test_the_scan_accepts_a_defaulted_parameter(tmp_path):
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class P:\n" "    def supports_thing(self, name=None):\n" "        return False\n",
        encoding="utf-8",
    )
    tree = ast.parse(probe.read_text(encoding="utf-8"))
    assert not _offenders(tree, "probe")


def _base_name(base):
    """The simple name a base class expression spells, if it spells one."""
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _protocol_bases(tree, label):
    """A ``*Dialect`` class must not inherit a ``*Support`` protocol.

    A ``runtime_checkable`` protocol is satisfied structurally: if the dialect
    really answers the protocol's members, ``isinstance`` is already True
    without inheriting anything. Inheriting the protocol declares no
    behaviour -- it copies the protocol's ellipsis stubs onto the class, so
    ``isinstance`` answers True for members the dialect never implemented.
    That is the lie the protocol conformance suite exists to catch, and this
    scan keeps it out of the source tree.
    """
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not node.name.endswith("Dialect"):
            continue
        for base in node.bases:
            name = _base_name(base)
            if name and name.endswith("Support"):
                found.append(f"{label}:{node.lineno} {node.name}({name})")
    return found


def _dialect_class_count():
    """How many ``*Dialect`` classes the scan actually reached."""
    count = 0
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        count += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name.endswith("Dialect")
        )
    return count


@pytest.mark.parametrize("path", _source_files(), ids=lambda p: str(p.name))
def test_dialect_class_inherits_no_support_protocol(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders = _protocol_bases(tree, path.name)
    assert not offenders, "\n".join(offenders)


def test_the_protocol_base_scan_reaches_the_dialects():
    files = _source_files()
    assert files, "the source scan reached no files"
    count = _dialect_class_count()
    assert count > 0, f"the scan found no *Dialect class in {len(files)} source files"


def test_the_scan_flags_a_planted_support_base(tmp_path):
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class ProbeDialect(NamespaceSupport):\n" "    pass\n",
        encoding="utf-8",
    )
    tree = ast.parse(probe.read_text(encoding="utf-8"))
    offenders = _protocol_bases(tree, "probe")
    assert offenders and "ProbeDialect(NamespaceSupport)" in offenders[0]


def test_the_scan_flags_a_qualified_support_base(tmp_path):
    """A protocol reached through its module is the same base."""
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "import protocols\n"
        "class ProbeDialect(protocols.NamespaceSupport):\n" "    pass\n",
        encoding="utf-8",
    )
    tree = ast.parse(probe.read_text(encoding="utf-8"))
    assert _protocol_bases(tree, "probe")


def test_the_scan_accepts_a_clean_dialect(tmp_path):
    """The control: a real mixin base and a non-protocol base are fine."""
    probe = tmp_path / "_probe.py"
    probe.write_text(
        "class ProbeDialect(MixinBase, object):\n"
        "    pass\n"
        "class Support:\n" "    pass\n",
        encoding="utf-8",
    )
    tree = ast.parse(probe.read_text(encoding="utf-8"))
    assert not _protocol_bases(tree, "probe")
