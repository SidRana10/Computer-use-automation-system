"""HandoffManager: explicit control-owner state machine over the *same* live
browser session.

AUTOMATION -> PAUSED (intervention raised)
PAUSED -> HUMAN (operator takes control; human-event capture on)
HUMAN -> PAUSED (operator resumes; events collected, capture off)
PAUSED -> AUTOMATION (resume checkpoint validated by the engine)
PAUSED/HUMAN -> aborted (terminal)

Automation and the human can never both hold the session: automation only
issues surface actions while owner == AUTOMATION, and every transition is
guarded here.
"""

from __future__ import annotations

import uuid
from typing import Literal

from ..models.errors import CapabilityError
from ..models.intervention import ControlOwner, HumanActionEvent, InterventionRequest, RunMode
from ..observability.logger import RunLogger
from ..policy.redaction import Redactor
from .store import InterventionStore


class HandoffError(CapabilityError):
    pass


class HandoffManager:
    def __init__(
        self,
        *,
        store: InterventionStore,
        surface,  # PlaywrightWebSurface (human capture uses the live page)
        logger: RunLogger,
        redactor: Redactor,
        operator_base_url: str = "",
    ):
        self.store = store
        self.surface = surface
        self.logger = logger
        self.redactor = redactor
        self.operator_base_url = operator_base_url
        self.control_owner: ControlOwner = ControlOwner.AUTOMATION

    # ------------------------------------------------------------ automation side

    async def request_intervention(
        self,
        *,
        run_id: str,
        mode: RunMode,
        capability_id: str | None,
        goal_summary: str,
        step_id: str | None,
        reason_code: str,
        reason_message: str,
    ) -> InterventionRequest:
        if self.control_owner != ControlOwner.AUTOMATION:
            raise HandoffError(f"cannot raise intervention while control owner is {self.control_owner}")
        screenshot = ""
        current_url = ""
        try:
            screenshot = str(await self.surface.capture_screenshot(f"intervention_{step_id or 'run'}"))
            current_url = self.surface.current_url()
        except Exception:
            pass  # a dead page must not prevent escalation
        intervention = InterventionRequest(
            intervention_id=f"int-{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            mode=mode,
            capability_id=capability_id,
            goal_summary=self.redactor.redact_text(goal_summary),
            step_id=step_id,
            reason_code=reason_code,
            reason_message=self.redactor.redact_text(reason_message),
            control_owner=ControlOwner.PAUSED,
            screenshot_path=screenshot,
            before_screenshot=screenshot,
            current_url=self.redactor.redact_text(current_url),
        )
        self.control_owner = ControlOwner.PAUSED
        self.store.add(intervention)
        self.logger.event(
            "intervention_created",
            intervention_id=intervention.intervention_id,
            step_id=step_id,
            reason_code=reason_code,
            reason=intervention.reason_message,
            control_owner=self.control_owner.value,
            operator_url=self.operator_base_url,
        )
        return intervention

    async def wait(self, intervention_id: str) -> Literal["resumed", "aborted"]:
        """Block automation until the operator resumes or aborts."""
        await self.store.wait(intervention_id)
        return "aborted" if self.store.get(intervention_id).status == "aborted" else "resumed"

    def confirm_automation_resumed(self, intervention_id: str) -> None:
        if self.control_owner != ControlOwner.PAUSED:
            raise HandoffError(f"cannot resume automation from {self.control_owner}")
        intervention = self.store.get(intervention_id)
        intervention.status = "resolved"
        intervention.control_owner = ControlOwner.AUTOMATION
        self.store.update(intervention)
        self.control_owner = ControlOwner.AUTOMATION
        self.logger.event("control_owner_changed", to="AUTOMATION", intervention_id=intervention_id)

    def mark_validation_failed(self, intervention_id: str) -> None:
        intervention = self.store.get(intervention_id)
        intervention.status = "resolved"
        intervention.operator_note = (intervention.operator_note or "") + " [resume validation failed]"
        self.store.update(intervention)
        self.logger.event("resume_validation_failed", intervention_id=intervention_id)

    def human_event_count(self, intervention_id: str) -> int:
        return len(self.store.get(intervention_id).human_events)

    # ------------------------------------------------------------ operator side

    async def take_control(self, intervention_id: str, operator_id: str) -> None:
        intervention = self.store.get(intervention_id)
        if self.control_owner != ControlOwner.PAUSED or intervention.status != "open":
            raise HandoffError(
                f"take control requires PAUSED/open, got {self.control_owner}/{intervention.status}"
            )
        self.control_owner = ControlOwner.HUMAN
        intervention.status = "claimed"
        intervention.control_owner = ControlOwner.HUMAN
        intervention.operator_id = operator_id
        self.store.update(intervention)
        await self.surface.set_human_capture(True)
        self.logger.event("control_owner_changed", to="HUMAN", intervention_id=intervention_id, operator_id=operator_id)

    async def resume(self, intervention_id: str, note: str | None = None) -> None:
        intervention = self.store.get(intervention_id)
        if self.control_owner != ControlOwner.HUMAN or intervention.status != "claimed":
            raise HandoffError(f"resume requires HUMAN/claimed, got {self.control_owner}/{intervention.status}")
        raw_events = await self.surface.collect_human_events()
        await self.surface.set_human_capture(False)
        events = []
        for raw in raw_events:
            if not isinstance(raw, dict):
                continue
            cleaned = self.redactor.redact(raw)
            # belt and braces: a typed value must never survive, even if the
            # in-page script was tampered with
            if "value" in cleaned and cleaned["value"] is not None:
                cleaned["value"] = "[REDACTED]"
                cleaned.setdefault("value_changed", True)
            try:
                events.append(HumanActionEvent.model_validate(cleaned))
            except ValueError:
                continue  # never let a malformed browser event break the resume path
        try:
            after = str(await self.surface.capture_screenshot(f"resume_{intervention_id}"))
        except Exception:
            after = ""
        intervention.human_events = events
        intervention.after_screenshot = after
        intervention.status = "resumed"
        intervention.control_owner = ControlOwner.PAUSED
        if note:
            intervention.operator_note = self.redactor.redact_text(note)
        self.store.update(intervention)
        self.control_owner = ControlOwner.PAUSED
        self.logger.event(
            "control_owner_changed",
            to="PAUSED",
            intervention_id=intervention_id,
            human_events=len(events),
        )
        self.store.signal(intervention_id)

    async def abort(self, intervention_id: str, note: str | None = None) -> None:
        intervention = self.store.get(intervention_id)
        if intervention.status not in ("open", "claimed"):
            raise HandoffError(f"cannot abort intervention in status {intervention.status}")
        if self.control_owner == ControlOwner.HUMAN:
            try:
                await self.surface.set_human_capture(False)
            except Exception:
                pass
        intervention.status = "aborted"
        intervention.control_owner = ControlOwner.PAUSED
        if note:
            intervention.operator_note = self.redactor.redact_text(note)
        self.store.update(intervention)
        self.control_owner = ControlOwner.PAUSED
        self.logger.event("run_aborted_by_operator", intervention_id=intervention_id)
        self.store.signal(intervention_id)
