"""Durable, file-backed record of capability-API invocations.

No database: one more JSON file (`result.json`) dropped into the same
per-run evidence directory `EvidenceManager` already creates
(`evidence/runs/<run_id>/`), alongside the redacted `run.jsonl`, screenshots,
and DOM snapshots the replay engine writes. Run history is just a directory
listing; a run's own file IS the source of truth, so it survives a process
restart without any separate index to keep in sync.

Only invocations made through the capability API/chatbot get a `result.json`
— older CLI/script runs in the same `evidence/runs/` tree are not retroactively
indexed. That is a deliberate scope boundary, not a bug: this store exists to
let the dashboard show what the new surface did, not to become a general
evidence-directory crawler.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models.artifact import CapabilityArtifact
from ..models.results import RunResult
from ..policy.redaction import Redactor
from ..targets.registry import profile_for_app_id
from .schemas import RunDetail, RunSummary


class RunNotFoundError(LookupError):
    def __init__(self, run_id: str):
        super().__init__(f"unknown run_id {run_id!r}")
        self.run_id = run_id


class RunStore:
    def __init__(self, evidence_dir: Path):
        self._evidence_dir = Path(evidence_dir)

    def _runs_dir(self) -> Path:
        return self._evidence_dir / "runs"

    def _run_dir(self, run_id: str) -> Path:
        return self._runs_dir() / run_id

    def record(
        self,
        *,
        run_dir: Path,
        result: RunResult,
        artifact: CapabilityArtifact,
        provided_inputs: dict[str, str],
        started_at: datetime,
        finished_at: datetime,
    ) -> None:
        """Write the one durable record of an API/chatbot invocation.

        `provided_inputs` are the caller-supplied business arguments only
        (never the server-injected operator credentials). Values are shown
        only for inputs the artifact's own contract does not mark sensitive
        — the same sensitivity flag the redactor and the replay engine
        already use — so this never becomes a second place sensitive values
        leak into durable storage.
        """
        specs = {s.name: s for s in artifact.contract.inputs}
        display_inputs = {
            name: ("[REDACTED]" if specs.get(name) is None or specs[name].sensitive else value)
            for name, value in provided_inputs.items()
        }
        record: dict[str, Any] = {
            "run_id": result.run_id,
            "capability_id": result.capability_id or artifact.capability_id,
            "capability_version": result.capability_version or artifact.capability_version,
            "capability_name": artifact.name,
            "status": result.status,
            "code": getattr(result, "code", None),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "inputs": display_inputs,
            "result": self._redacted_result(result, artifact),
        }
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "result.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")

    @staticmethod
    def _redacted_result(result: RunResult, artifact: CapabilityArtifact) -> dict[str, Any]:
        """The durable run-history copy, redacted with the same central
        `Redactor` and target-profile patterns already used for logs, DOM
        snapshots, and screenshots (`targets/<profile>.py`
        `redaction_text_patterns`) — not a second, unrelated sanitizer.

        The live API/chatbot response to the caller is unaffected: this only
        governs what gets written to `result.json` for the dashboard/evidence
        trail. A capability's structured outputs (e.g. balances) can carry
        target-rendered sensitive values a caller legitimately asked for but
        that must not accumulate in durable storage, matching the same
        currency/contact-detail patterns already scrubbed from redacted DOM
        snapshots for this target.
        """
        payload = json.loads(result.model_dump_json())
        profile = profile_for_app_id(artifact.target.app_id)
        if profile is None or not profile.redaction_text_patterns:
            return payload
        redactor = Redactor(text_patterns=profile.redaction_text_patterns)
        return redactor.redact(payload)

    def list_runs(self) -> list[RunSummary]:
        runs_dir = self._runs_dir()
        if not runs_dir.is_dir():
            return []
        summaries: list[RunSummary] = []
        for path in runs_dir.glob("*/result.json"):
            data = self._read_json(path)
            if data is None:
                continue
            summaries.append(
                RunSummary(
                    run_id=data["run_id"],
                    capability_id=data["capability_id"],
                    capability_version=data["capability_version"],
                    capability_name=data["capability_name"],
                    status=data["status"],
                    code=data.get("code"),
                    started_at=data["started_at"],
                    finished_at=data["finished_at"],
                    duration_ms=data["duration_ms"],
                )
            )
        return sorted(summaries, key=lambda r: r.started_at, reverse=True)

    def get(self, run_id: str) -> RunDetail:
        run_dir = self._run_dir(run_id)
        data = self._read_json(run_dir / "result.json")
        if data is None:
            raise RunNotFoundError(run_id)
        evidence_files = sorted(
            str(p.relative_to(run_dir)) for p in run_dir.rglob("*") if p.is_file()
        )
        return RunDetail(
            run_id=data["run_id"],
            capability_id=data["capability_id"],
            capability_version=data["capability_version"],
            capability_name=data["capability_name"],
            status=data["status"],
            code=data.get("code"),
            started_at=data["started_at"],
            finished_at=data["finished_at"],
            duration_ms=data["duration_ms"],
            inputs=data["inputs"],
            result=data["result"],
            evidence_files=evidence_files,
            events=self._read_events(run_dir / "run.jsonl"),
        )

    def evidence_file_path(self, run_id: str, relative: str) -> Path:
        """Resolve a relative evidence file path safely inside one run's
        directory. Raises rather than ever serving a path outside it."""
        run_dir = self._run_dir(run_id).resolve()
        candidate = (run_dir / relative).resolve()
        if not candidate.is_relative_to(run_dir):
            raise ValueError(f"path {relative!r} escapes run directory")
        if not candidate.is_file():
            raise FileNotFoundError(relative)
        return candidate

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _read_events(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events
