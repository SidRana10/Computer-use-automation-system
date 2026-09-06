"""RunStore: file-backed run history and its evidence-file path safety.

The HTTP-level path-traversal test in test_api_routes.py is best-effort (URL
normalization can rewrite `..` segments before they reach the route); this
tests `evidence_file_path` directly so the guarantee does not depend on that.
"""

from __future__ import annotations

import pytest

from ui_capabilities.api.run_store import RunNotFoundError, RunStore


def test_evidence_file_path_rejects_traversal_outside_run_dir(tmp_path):
    evidence_root = tmp_path / "evidence"
    run_dir = evidence_root / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "screenshots").mkdir()
    (run_dir / "screenshots" / "ok.png").write_bytes(b"fake-png")
    secret = tmp_path / "outside_secret.txt"
    secret.write_text("do not serve me")

    store = RunStore(evidence_root)

    # legitimate file resolves fine
    resolved = store.evidence_file_path("run-1", "screenshots/ok.png")
    assert resolved.is_file()

    with pytest.raises(ValueError):
        store.evidence_file_path("run-1", "../../outside_secret.txt")

    with pytest.raises(FileNotFoundError):
        store.evidence_file_path("run-1", "screenshots/does_not_exist.png")


def test_get_unknown_run_raises(tmp_path):
    store = RunStore(tmp_path / "evidence")
    with pytest.raises(RunNotFoundError):
        store.get("no-such-run")


def test_list_runs_on_empty_store_is_empty(tmp_path):
    store = RunStore(tmp_path / "evidence")
    assert store.list_runs() == []
