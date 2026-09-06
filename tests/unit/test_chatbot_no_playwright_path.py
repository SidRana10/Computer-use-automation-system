"""P7/P8 hard requirement: the chatbot and dashboard must not interact with
Playwright directly and must not become a second automation engine. Checked
by parsing actual `import`/`from` statements (via `ast`), not a substring
scan of the whole file — several modules' own docstrings *talk about* not
using Playwright, which a naive text search would misflag."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHATBOT_DIR = REPO_ROOT / "src" / "ui_capabilities" / "chatbot"
DASHBOARD_DIR = REPO_ROOT / "src" / "ui_capabilities" / "dashboard"
API_DIR = REPO_ROOT / "src" / "ui_capabilities" / "api"


def _python_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.rglob("*.py") if p.is_file())


def _imported_module_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(f"{'.' * node.level}{node.module or ''}")
    return names


def _forbidden_imports(path: Path) -> list[str]:
    return [
        name
        for name in _imported_module_names(path)
        if "playwright" in name.lower() or "replay.engine" in name.lower()
    ]


def test_chatbot_never_imports_playwright_or_the_replay_engine():
    offenders = {path: _forbidden_imports(path) for path in _python_files(CHATBOT_DIR)}
    offenders = {p: f for p, f in offenders.items() if f}
    assert offenders == {}


def test_dashboard_never_imports_playwright_or_the_replay_engine():
    offenders = {path: _forbidden_imports(path) for path in _python_files(DASHBOARD_DIR)}
    offenders = {p: f for p, f in offenders.items() if f}
    assert offenders == {}


def test_only_runner_module_imports_the_surface_or_replay_engine():
    offenders = {
        path: _forbidden_imports(path)
        for path in _python_files(API_DIR)
        if path.name != "runner.py"
    }
    offenders = {p: f for p, f in offenders.items() if f}
    assert offenders == {}, f"unexpected second Playwright/replay-engine entry point(s): {offenders}"


def test_runner_module_is_the_one_place_that_imports_them():
    imports = _forbidden_imports(API_DIR / "runner.py")
    assert any("playwright" in i.lower() for i in imports)
    assert any("replay.engine" in i.lower() for i in imports)
