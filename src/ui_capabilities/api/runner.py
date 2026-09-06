"""Runs one capability artifact through the existing deterministic replay
path — the exact same construction `uicap replay` and
`scripts/meridian_replay.py` already use: `PlaywrightWebSurface` +
`PolicyEngine` + `Redactor` + `RunLogger` + `EvidenceManager` +
`HandoffManager` + `ReplayEngine`.

This is intentionally the ONLY place in the api/chatbot/dashboard code that
imports a surface. Nothing else in `api/`, `chatbot/`, or `dashboard/` may
import `..surfaces` or `..replay.engine` directly — that is what keeps this a
single Playwright execution path instead of a second one growing next to it.
"""

from __future__ import annotations

import asyncio
import urllib.parse
import uuid

from ..config import Settings
from ..handoff.manager import HandoffManager
from ..handoff.operator_app import OperatorServer, create_operator_app
from ..handoff.store import InterventionStore
from ..models.artifact import CapabilityArtifact
from ..models.results import RunResult
from ..observability.evidence import EvidenceManager
from ..observability.logger import RunLogger
from ..policy.engine import PolicyEngine
from ..policy.redaction import Redactor
from ..replay.engine import ReplayEngine
from ..surfaces.playwright_web import PlaywrightWebSurface
from ..targets.registry import TargetProfile, profile_for_app_id


class NoTargetProfileError(LookupError):
    def __init__(self, app_id: str):
        super().__init__(f"no target profile registered for app_id {app_id!r}")


class CapabilityRunner:
    """One live invocation = one fresh browser, one fresh evidence directory,
    one fresh operator console — then everything is torn down. Concurrency is
    serialized by `_lock`: two overlapping invocations would otherwise both
    try to bind the same operator console port, exactly as two concurrent
    `uicap replay --no-operator=false` processes would. A demo/interview
    system driving one live legacy UI at a time does not need more than
    that; documented as a known limitation, not silently papered over.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.load()
        self._lock = asyncio.Lock()

    async def invoke(self, artifact: CapabilityArtifact, bound_inputs: dict[str, str]) -> tuple[RunResult, EvidenceManager]:
        async with self._lock:
            return await self._invoke(artifact, bound_inputs)

    async def _invoke(
        self, artifact: CapabilityArtifact, bound_inputs: dict[str, str]
    ) -> tuple[RunResult, EvidenceManager]:
        profile: TargetProfile | None = profile_for_app_id(artifact.target.app_id)
        if profile is None:
            raise NoTargetProfileError(artifact.target.app_id)

        run_id = f"api-{uuid.uuid4().hex[:10]}"
        evidence = EvidenceManager(self.settings.evidence_dir, run_id)
        redactor = Redactor(text_patterns=profile.redaction_text_patterns)
        logger = RunLogger(evidence.log_path, redactor, run_id)
        policy = PolicyEngine(profile.policy(artifact.target.entry_point))

        surface = PlaywrightWebSurface(
            self.settings,
            evidence,
            headless=None,  # settings.playwright_headless decides
            heading_selector=profile.heading_selector,
            mask_selectors=profile.screenshot_mask_selectors,
            redactor=redactor,
            enable_tracing=profile.durable_traces,
        )
        store = InterventionStore(dump_path=evidence.run_dir / "interventions.json")
        handoff = HandoffManager(
            store=store,
            surface=surface,
            logger=logger,
            redactor=redactor,
            operator_base_url=self.settings.operator_base_url,
        )
        parsed = urllib.parse.urlparse(self.settings.operator_base_url)
        operator_server = OperatorServer(
            create_operator_app(handoff), parsed.hostname or "127.0.0.1", parsed.port or 8002
        )
        await operator_server.start()
        try:
            engine = ReplayEngine(
                surface=surface,
                global_policy=policy,
                settings=self.settings,
                logger=logger,
                evidence=evidence,
                redactor=redactor,
                handoff=handoff,
            )
            result = await engine.replay(artifact, bound_inputs)
            return result, evidence
        finally:
            await operator_server.stop()
            await surface.close()
