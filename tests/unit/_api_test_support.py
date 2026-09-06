"""Shared test doubles for api/chatbot/dashboard tests.

`FakeRunner` stands in for `CapabilityRunner`: it satisfies the same
`invoke(artifact, bound_inputs) -> (RunResult, evidence)` shape without ever
touching Playwright, so these tests exercise the real `CapabilityService`,
routing, and run-history persistence without a live browser or a live
MERIDIAN target. Recording every call also lets a test assert a runner was
never reached at all — the "fails before browser execution" contract.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from ui_capabilities.api.catalog import CapabilityCatalog
from ui_capabilities.api.run_store import RunStore
from ui_capabilities.api.service import CapabilityService
from ui_capabilities.models.artifact import CapabilityArtifact
from ui_capabilities.models.results import RunResult

MERIDIAN_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "meridian"


class FakeRunner:
    def __init__(self, result_fn: Callable[[CapabilityArtifact, dict[str, str]], RunResult], evidence_root: Path):
        self.calls: list[tuple[str, dict[str, str]]] = []
        self._result_fn = result_fn
        self._evidence_root = evidence_root

    async def invoke(self, artifact: CapabilityArtifact, bound_inputs: dict[str, str]):
        self.calls.append((artifact.capability_id, dict(bound_inputs)))
        result = self._result_fn(artifact, bound_inputs)
        run_dir = self._evidence_root / "runs" / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        evidence = SimpleNamespace(run_dir=run_dir)
        return result, evidence


def make_service(tmp_path: Path, result_fn: Callable[[CapabilityArtifact, dict[str, str]], RunResult]) -> tuple[CapabilityService, FakeRunner]:
    catalog = CapabilityCatalog(MERIDIAN_ARTIFACTS_DIR)
    run_store = RunStore(tmp_path / "evidence")
    runner = FakeRunner(result_fn, tmp_path / "evidence")
    service = CapabilityService(catalog, runner, run_store)
    return service, runner
