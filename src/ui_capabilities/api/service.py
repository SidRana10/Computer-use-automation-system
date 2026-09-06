"""CapabilityService: the one place that turns "invoke capability X with
these arguments" into a deterministic replay run.

Both the HTTP routes (`api/routes.py`) and the chatbot (`chatbot/router.py`)
call this same class — there is exactly one invocation path in the process,
not an HTTP route plus a separate chatbot-internal automation shortcut. The
routes are a thin FastAPI adapter over it; the chatbot is a thin NLU adapter
over it. Neither imports `CapabilityRunner`, a surface, or the replay engine
directly.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from ..models.artifact import CapabilityArtifact
from ..models.errors import FailureCode
from ..models.results import FailureResult, RunResult
from ..replay import binder
from .catalog import CapabilityCatalog, CapabilityNotFoundError
from .run_store import RunNotFoundError, RunStore
from .runner import CapabilityRunner
from .schemas import SERVER_SUPPLIED_INPUTS, CapabilityDetail, CapabilitySummary, RunDetail, RunSummary, to_detail, to_summary

__all__ = [
    "CapabilityService",
    "CapabilityNotFoundError",
    "RunNotFoundError",
    "InvalidArgumentsError",
]

# Never accepted from a caller under any name, even if a request body happens
# to include them: they either bypass policy (`human_approved`) or would let
# a caller impersonate the operating environment's own MERIDIAN sign-on.
_FORBIDDEN_INPUT_NAMES = SERVER_SUPPLIED_INPUTS | {"human_approved"}


class InvalidArgumentsError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _operator_credentials() -> dict[str, str]:
    """Server-side MERIDIAN sign-on context. Never accepted from a caller,
    never returned to one — the same environment variables the live
    integration tests already read (`MERIDIAN_TELLER_ID`,
    `MERIDIAN_TELLER_PASSWORD`, `MERIDIAN_BRANCH`)."""
    return {
        "operator_id": os.environ.get("MERIDIAN_TELLER_ID", ""),
        "password": os.environ.get("MERIDIAN_TELLER_PASSWORD", ""),
        "branch": os.environ.get("MERIDIAN_BRANCH", "MAIN-001"),
    }


class CapabilityService:
    def __init__(self, catalog: CapabilityCatalog, runner: CapabilityRunner, run_store: RunStore):
        self.catalog = catalog
        self.runner = runner
        self.run_store = run_store

    # -- catalog --------------------------------------------------------

    def list_capabilities(self) -> list[CapabilitySummary]:
        return [self._summary(a) for a in self.catalog.list()]

    def get_capability(self, capability_id: str) -> CapabilityDetail:
        artifact = self.catalog.get(capability_id)  # raises CapabilityNotFoundError
        return to_detail(artifact, self._target_name(artifact))

    def _summary(self, artifact: CapabilityArtifact) -> CapabilitySummary:
        return to_summary(artifact, self._target_name(artifact))

    @staticmethod
    def _target_name(artifact: CapabilityArtifact) -> str:
        from ..targets.registry import profile_for_app_id

        profile = profile_for_app_id(artifact.target.app_id)
        return profile.display_name if profile is not None else artifact.target.app_id

    # -- invocation -------------------------------------------------------

    async def invoke(self, capability_id: str, inputs: dict[str, object]) -> RunResult:
        artifact = self.catalog.get(capability_id)  # raises CapabilityNotFoundError, before any browser work

        forbidden = set(inputs) & _FORBIDDEN_INPUT_NAMES
        if forbidden:
            raise InvalidArgumentsError(
                f"input(s) {sorted(forbidden)} are supplied by the operating environment, not the caller"
            )

        business_inputs = {name: str(value) for name, value in inputs.items()}
        merged = {**business_inputs, **_operator_credentials()}

        # Cheap, pure contract check before any evidence directory, browser,
        # or operator-console port is touched. `ReplayEngine.replay` performs
        # this exact same check again as its own first step (defense in
        # depth, not duplicated policy) — doing it here too means a bad
        # request has zero side effects instead of merely no browser launch.
        try:
            binder.validate_and_bind(artifact.contract, merged)
        except binder.InvocationError as exc:
            return FailureResult(
                run_id=f"rejected-{uuid.uuid4().hex[:10]}",
                capability_id=artifact.capability_id,
                capability_version=artifact.capability_version,
                code=FailureCode.INVOCATION_INVALID,
                expected="invocation matching the capability contract",
                observed=str(exc),
            )

        started_at = datetime.now(timezone.utc)
        result, evidence = await self.runner.invoke(artifact, merged)
        finished_at = datetime.now(timezone.utc)

        self.run_store.record(
            run_dir=evidence.run_dir,
            result=result,
            artifact=artifact,
            provided_inputs=business_inputs,
            started_at=started_at,
            finished_at=finished_at,
        )
        return result

    # -- run history --------------------------------------------------------

    def list_runs(self) -> list[RunSummary]:
        return self.run_store.list_runs()

    def get_run(self, run_id: str) -> RunDetail:
        return self.run_store.get(run_id)  # raises RunNotFoundError
