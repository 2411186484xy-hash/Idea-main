"""Machine-enforced architecture: import direction, single IO writer, no
hardcoded drive letters, line budgets (values come from canon)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from pipelines import canon

REPO = Path(__file__).resolve().parent.parent
PIPELINES = REPO / "pipelines"
CLI = REPO / "cli.py"

LAYER = {
    "contracts": 0,
    "store": 1,
    "canon": 1,
    "runs": 2,
    "search": 2,
    "papers": 2,
    "claims": 2,
    "idea": 2,
    "feedback": 2,
    "zotero": 2,
    "pdf": 2,
    "report": 3,
    "validate": 3,
}

PROJECT_IMPORT_RE = re.compile(r"^pipelines[..]?(\w*)")


def _project_imports(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level > 0:  # relative: from .[module] import names
                if node.module:  # from .contracts import X
                    found.add(node.module.split(".")[0])
                else:  # from . import x, y
                    found.update(a.name for a in node.names)
            elif node.module == "pipelines":  # from pipelines import x, y
                found.update(a.name for a in node.names)
            elif node.module and (hit := PROJECT_IMPORT_RE.match(node.module)):
                found.add(hit.group(1))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                hit = PROJECT_IMPORT_RE.match(alias.name)
                if hit:
                    found.add(hit.group(1))
    return {m for m in found if m}


def _modules() -> dict[str, Path]:
    return {p.stem: p for p in PIPELINES.glob("*.py") if p.name != "__init__.py"}


def test_no_unknown_modules():
    unknown = set(_modules()) - set(LAYER)
    assert not unknown, f"modules outside the layer map: {sorted(unknown)}"


def test_import_direction():
    for name, path in _modules().items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = _project_imports(tree)
        assert "cli" not in imported, f"{name} imports cli"
        for target in imported:
            if target == name:
                continue
            assert target in LAYER, f"{name} imports unknown module {target}"
            own, other = LAYER[name], LAYER[target]
            if own == 2 and name != "runs" and other == 2:
                assert target == "runs", (
                    f"{name} -> {target}: L2 horizontal imports are only allowed to runs"
                )
            else:
                assert other < own, f"{name} (L{own}) imports upward: {target} (L{other})"


def test_cli_imports_allowed():
    tree = ast.parse(CLI.read_text(encoding="utf-8"))
    imported = _project_imports(tree)
    assert imported and "cli" not in imported


WRITE_PATTERNS = (
    r"(?<!\.)\bopen\(",
    r"\.open\([\"']w",
    r"\.write_text\(",
    r"\.write_bytes\(",
    r"\bos\.replace\b",
    r"\.mkdir\(",
    r"\bos\.makedirs\b",
    r"\bshutil\b",
    r"\bos\.remove\b",
    r"\.unlink\(",
    r"\brmtree\b",
    r"\bos\.fsync\b",
    r"\.touch\(",
)


def test_single_io_writer():
    for name, path in _modules().items():
        if name == "store":
            continue
        src = path.read_text(encoding="utf-8")
        for pattern in WRITE_PATTERNS:
            assert not re.search(pattern, src), (
                f"bare write primitive `{pattern}` outside store.py: {name}"
            )


DRIVE_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")


def test_no_hardcoded_drive_letters():
    for path in list(_modules().values()) + [CLI]:
        src = path.read_text(encoding="utf-8")
        hit = DRIVE_RE.search(src)
        assert hit is None, f"hardcoded drive letter in {path.name}: ...{src[max(0, hit.start()-20):hit.end()+20]}..."


def _count_lines(paths: list[Path]) -> int:
    return sum(len(p.read_text(encoding="utf-8").splitlines()) for p in paths)


def test_line_budgets():
    code_budget = int(canon.value("limits.code_line_budget"))
    test_budget = int(canon.value("limits.test_line_budget"))
    module_max = int(canon.value("limits.module_line_max"))
    code_total = _count_lines(list(_modules().values()) + [CLI])
    test_total = _count_lines(list((REPO / "tests").glob("*.py")))
    assert code_total <= code_budget, f"pipelines+cli = {code_total} > {code_budget}"
    assert test_total <= test_budget, f"tests = {test_total} > {test_budget}"
    for name, path in _modules().items():
        n = len(path.read_text(encoding="utf-8").splitlines())
        assert n <= module_max, f"module {name} = {n} > {module_max}"


@pytest.mark.parametrize("name", sorted(LAYER))
def test_expected_modules_exist_or_scheduled(name):
    """M0 modules must exist; M2 modules may land later (this pins the map)."""
    scheduled_m2 = {"idea", "feedback", "zotero", "pdf"}
    if name in scheduled_m2:
        return
    assert name in _modules(), f"missing M0 module: pipelines/{name}.py"
