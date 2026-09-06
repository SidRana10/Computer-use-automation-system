"""RunStore: file-backed run history and its evidence-file path safety.

The HTTP-level path-traversal test in test_api_routes.py is best-effort (URL
normalization can rewrite `..` segments before they reach the route); this
tests `evidence_file_path` directly so the guarantee does not depend on that.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ui_capabilities.api.run_store import RunNotFoundError, RunStore
from ui_capabilities.discovery.compiler import load_artifact
from ui_capabilities.models.results import SuccessResult

MERIDIAN_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "meridian"


def test_persisted_result_redacts_sensitive_output_values_but_keeps_structure(tmp_path):
    """The live API/chatbot response may carry real balances (the caller
    asked for exactly that), but the durable `result.json` copy backing the
    dashboard/evidence trail must not accumulate them in clear text — the
    same currency/contact-detail patterns already scrubbed from this
    target's redacted DOM snapshots and screenshots must also apply here."""
    artifact = load_artifact(MERIDIAN_ARTIFACTS_DIR / "meridian.get_member_balances.v1.json")
    result = SuccessResult(
        run_id="run-redact-1",
        capability_id=artifact.capability_id,
        capability_version=artifact.capability_version,
        outputs={
            "shares": [
                {"Share ID": "100234-S0001", "Type": "Regular Shares", "Balance": "$2,499.00", "Status": "OPEN"},
            ]
        },
    )

    evidence_root = tmp_path / "evidence"
    run_dir = evidence_root / "runs" / result.run_id
    store = RunStore(evidence_root)
    now = datetime.now(timezone.utc)
    store.record(
        run_dir=run_dir,
        result=result,
        artifact=artifact,
        provided_inputs={"member_number": "100234"},
        started_at=now,
        finished_at=now,
    )

    on_disk = json.loads((run_dir / "result.json").read_text())
    share_row = on_disk["result"]["outputs"]["shares"][0]
    assert share_row["Balance"] == "[REDACTED]"
    assert "2,499.00" not in json.dumps(on_disk)
    # structure survives: the dashboard can still show which share/status was reached
    assert share_row["Share ID"] == "100234-S0001"
    assert share_row["Status"] == "OPEN"

    # the RunStore read path returns the same redacted copy — dashboard and
    # persisted evidence are always consistent with each other
    detail = store.get(result.run_id)
    assert detail.result.outputs["shares"][0]["Balance"] == "[REDACTED]"


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
