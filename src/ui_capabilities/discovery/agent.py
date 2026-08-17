"""The LLM discovery loop: observe → decide → policy-check → act → record.

The only place a model makes UI decisions. Bounded by max steps, wall-clock
timeout, repeated-state detection, execution-error and policy-denial budgets.
Escalates to a human instead of looping forever.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from ..config import Settings
from ..models.actions import (
    ClickAction,
    DiscoveryAction,
    DoneAction,
    ExtractAction,
    FillAction,
    NavigateAction,
    RequestHumanAction,
    SelectAction,
    WaitAction,
)
from ..models.artifact import InputSpec
from ..models.conditions import ConditionSpec
from ..models.errors import RiskLevel
from ..models.intervention import RunMode
from ..observability.evidence import EvidenceManager
from ..observability.logger import RunLogger
from ..policy.engine import PolicyDecision, PolicyEngine
from ..policy.redaction import Redactor
from ..surfaces.base import ExecutableAction, Observation, SurfaceAdapter
from .model_adapter import ModelAdapter, TurnContext
from .recorder import RecordedRun, RecordedStep, StateSnapshot

_BUILD_MARKER_RE = re.compile(r"Build ([\w.\-]+)")


@dataclass
class DiscoveryOutcome:
    run: RecordedRun
    status: str  # "success" | "failed" | "escalated" | "aborted"
    reason: str = ""
    intervention_id: str | None = None
    extracted_outputs: dict[str, str] | None = None


def snapshot(observation: Observation) -> StateSnapshot:
    return StateSnapshot(
        url=observation.url,
        path=observation.path,
        title=observation.title,
        heading=observation.heading,
        fingerprint=observation.fingerprint,
    )


class DiscoveryAgent:
    def __init__(
        self,
        *,
        surface: SurfaceAdapter,
        model: ModelAdapter,
        policy: PolicyEngine,
        settings: Settings,
        logger: RunLogger,
        evidence: EvidenceManager,
        redactor: Redactor,
        handoff=None,  # HandoffManager | None; optional to keep tests light
    ):
        self.surface = surface
        self.model = model
        self.policy = policy
        self.settings = settings
        self.logger = logger
        self.evidence = evidence
        self.redactor = redactor
        self.handoff = handoff

    async def run(
        self,
        *,
        goal: str,
        entry_point: str,
        capability_id: str,
        input_specs: list[InputSpec],
        input_bindings: dict[str, str],
        target_app_name: str = "target application",
    ) -> DiscoveryOutcome:
        for spec in input_specs:
            if spec.sensitive and spec.name in input_bindings:
                self.redactor.register_sensitive_value(input_bindings[spec.name])

        run = RecordedRun(
            run_id=self.evidence.run_id,
            goal=goal,
            capability_id=capability_id,
            entry_point=entry_point,
            target_app_name=target_app_name,
            model_name=self.model.name,
            input_specs=input_specs,
            input_bindings=dict(input_bindings),
        )
        self.logger.event(
            "discovery_started",
            goal=goal,
            capability_id=capability_id,
            entry_point=entry_point,
            model=self.model.name,
            inputs=[s.name for s in input_specs],
        )

        started = time.monotonic()
        history: list[str] = []
        feedback: str | None = None
        state_action_counts: dict[str, int] = {}
        execution_errors = 0
        policy_denials = 0
        outputs: dict[str, str] = {}

        step_index = 0
        while True:
            elapsed = time.monotonic() - started
            if step_index >= self.settings.max_discovery_steps:
                return await self._give_up(run, "max_steps", f"reached {self.settings.max_discovery_steps} steps")
            if elapsed > self.settings.discovery_timeout_seconds:
                return await self._give_up(run, "timeout", f"exceeded {self.settings.discovery_timeout_seconds}s")

            observation = await self.surface.observe(label=f"step_{step_index:02d}_before")
            if not run.app_fingerprint:
                run.app_fingerprint = self._fingerprint_app(observation)

            context = TurnContext(
                goal=goal,
                target_app_name=target_app_name,
                entry_point=entry_point,
                step_number=step_index + 1,
                max_steps=self.settings.max_discovery_steps,
                elapsed_seconds=int(elapsed),
                timeout_seconds=self.settings.discovery_timeout_seconds,
                policy=self.policy.config,
                input_specs=input_specs,
                recent_history=history,
                feedback=feedback,
            )
            feedback = None
            try:
                action = await self.model.next_action(observation, context)
            except ValueError as exc:
                return await self._give_up(run, "invalid_model_output", str(exc))

            action_sig = json.dumps(action.model_dump(), sort_keys=True, default=str)
            self.logger.event(
                "model_proposed",
                step=step_index,
                action=action.model_dump(),
                url=observation.path,
                fingerprint=observation.fingerprint,
            )

            # dead-end detection: same state + same action proposed repeatedly
            key = f"{observation.fingerprint}::{action_sig}"
            state_action_counts[key] = state_action_counts.get(key, 0) + 1
            if state_action_counts[key] >= self.settings.max_repeated_states:
                return await self._escalate_or_fail(
                    run, observation, "repeated_state", "the same action keeps being proposed in the same UI state"
                )

            if isinstance(action, DoneAction):
                verified, detail = await self._verify_done(action, input_bindings, outputs)
                if verified:
                    run.success = True
                    run.done_summary = action.success_summary
                    run.suggested_success_condition = action.suggested_success_condition
                    final_obs = await self.surface.observe(label="final")
                    run.final_state = snapshot(final_obs)
                    run.finished_at = datetime.now(timezone.utc)
                    self.logger.event("discovery_succeeded", steps=len(run.steps), detail=detail)
                    return DiscoveryOutcome(run=run, status="success", extracted_outputs=outputs)
                feedback = f"DONE was rejected: {detail}. Continue working toward the goal or request human help."
                history.append(f"step {step_index + 1}: done rejected ({detail})")
                step_index += 1
                continue

            if isinstance(action, RequestHumanAction):
                return await self._escalate_or_fail(run, observation, action.reason_code, action.message)

            element = None
            if getattr(action, "element_ref", None):
                element = next((e for e in observation.elements if e.ref == action.element_ref), None)
                if element is None:
                    feedback = f"element ref {action.element_ref!r} does not exist in the current observation"
                    history.append(f"step {step_index + 1}: rejected unknown ref")
                    step_index += 1
                    continue

            decision = self._check_policy(action, element)
            if decision.requires_human:
                if isinstance(action, ClickAction) and self.handoff is not None:
                    outcome = await self._human_step(run, observation, action, element, decision)
                    if outcome is not None:
                        return outcome
                    history.append(f"step {step_index + 1}: {self._summarize(action, element)} (completed by human)")
                    step_index += 1
                    continue
                return await self._escalate_or_fail(run, observation, "risky_action", decision.reason)
            if not decision.allowed:
                policy_denials += 1
                self.logger.event("policy_blocked", step=step_index, code=decision.code, reason=decision.reason)
                run.steps.append(
                    RecordedStep(
                        index=step_index,
                        before=snapshot(observation),
                        action=action,
                        element=element,
                        policy=decision,
                        started_at=datetime.now(timezone.utc),
                    )
                )
                if policy_denials >= self.settings.max_policy_denials:
                    return await self._escalate_or_fail(run, observation, "policy_denials", "repeated policy violations")
                feedback = f"action blocked by policy: {decision.reason}"
                step_index += 1
                continue

            executable = self._to_executable(action, input_bindings)
            step_started = datetime.now(timezone.utc)
            t0 = time.monotonic()
            result = await self.surface.execute(executable)
            after_obs = await self.surface.observe(label=f"step_{step_index:02d}_after")

            # redirect protection: the landed URL must still be inside policy
            landed = self.policy.check_url(after_obs.url)
            if result.ok and not landed.allowed:
                self.logger.event("post_navigation_policy_violation", step=step_index, reason=landed.reason)
                return await self._escalate_or_fail(
                    run, after_obs, "off_policy_redirect", f"navigation landed outside policy: {landed.reason}"
                )

            if isinstance(action, ExtractAction) and result.ok and result.extracted_text is not None:
                outputs[action.output_name] = result.extracted_text
                # treat every extracted output as sensitive for logging purposes
                self.redactor.register_sensitive_value(result.extracted_text)

            run.steps.append(
                RecordedStep(
                    index=step_index,
                    before=snapshot(observation),
                    action=action,
                    element=element,
                    policy=decision,
                    result=result,
                    after=snapshot(after_obs),
                    started_at=step_started,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                )
            )
            self.logger.event(
                "action_executed",
                step=step_index,
                kind=action.action,
                ok=result.ok,
                error=result.error_code,
                url_after=after_obs.path,
            )

            if result.ok:
                history.append(f"step {step_index + 1}: {self._summarize(action, element)} -> ok, now at {after_obs.path}")
            else:
                execution_errors += 1
                history.append(f"step {step_index + 1}: {self._summarize(action, element)} -> error {result.error_code}")
                feedback = f"the action failed: {result.error_code} {result.message}"
                if execution_errors >= self.settings.max_execution_errors:
                    return await self._escalate_or_fail(run, after_obs, "execution_errors", "repeated action failures")
            step_index += 1

    # ------------------------------------------------------------------ utils

    def _fingerprint_app(self, observation: Observation) -> dict[str, str]:
        fp = {"app_title": observation.title}
        match = _BUILD_MARKER_RE.search(observation.visible_text_summary)
        if match:
            fp["build_marker"] = match.group(1)
        return fp

    def _summarize(self, action: DiscoveryAction, element) -> str:
        ident = ""
        if element is not None:
            ident = f" {element.kind} '{element.accessible_name or element.text or element.ref}'"
        return f"{action.action}{ident}"

    def _check_policy(self, action: DiscoveryAction, element) -> PolicyDecision:
        url = action.url if isinstance(action, NavigateAction) else None
        control_text = None
        if element is not None:
            control_text = element.accessible_name or element.text
        return self.policy.check_action(
            action.action if action.action != "wait" else "wait",
            url=url,
            risk=RiskLevel.SAFE,
            control_text=control_text,
        )

    def _to_executable(self, action: DiscoveryAction, bindings: dict[str, str]) -> ExecutableAction:
        if isinstance(action, NavigateAction):
            return ExecutableAction(kind="navigate", url=action.url)
        if isinstance(action, ClickAction):
            return ExecutableAction(kind="click", element_ref=action.element_ref)
        if isinstance(action, (FillAction, SelectAction)):
            source = action.value_source
            if source.input_name:
                if source.input_name not in bindings:
                    raise ValueError(f"model referenced unknown input {source.input_name!r}")
                value = bindings[source.input_name]
            else:
                value = source.literal or ""
            kind = "fill" if isinstance(action, FillAction) else "select"
            return ExecutableAction(kind=kind, element_ref=action.element_ref, value=value)
        if isinstance(action, ExtractAction):
            return ExecutableAction(kind="extract", element_ref=action.element_ref)
        if isinstance(action, WaitAction):
            return ExecutableAction(kind="wait", wait_ms=min(action.milliseconds, self.settings.max_wait_action_ms))
        raise ValueError(f"unsupported action {action.action}")

    async def _verify_done(
        self, action: DoneAction, bindings: dict[str, str], extracted_outputs: dict[str, str]
    ) -> tuple[bool, str]:
        """Never trust `done` blindly: check the proposed success condition
        against the live UI, and reject conditions that embed concrete runtime
        values — bound inputs or extracted outputs — because those verify one
        invocation, not the reusable flow."""
        suggested = action.suggested_success_condition
        if suggested is None:
            return False, "no success condition was provided"
        if self._embeds_runtime_value(suggested.value, bindings, extracted_outputs):
            return False, (
                "success condition must not embed concrete invocation or extracted values; "
                "reference stable UI text or the URL instead"
            )
        condition = ConditionSpec(kind=suggested.kind, value=suggested.value, timeout_ms=2000)
        result = await self.surface.evaluate_condition(condition)
        return result.satisfied, result.detail or "condition evaluated"

    @staticmethod
    def _embeds_runtime_value(text: str, bindings: dict[str, str], extracted_outputs: dict[str, str]) -> bool:
        normalized_text = text.replace("$", "").replace(",", "")
        for value in list(bindings.values()) + list(extracted_outputs.values()):
            if not value:
                continue
            normalized_value = value.replace("$", "").replace(",", "").strip()
            if len(normalized_value) < 3:
                continue
            if value in text or normalized_value in normalized_text:
                return True
        return False

    async def _give_up(self, run: RecordedRun, reason_code: str, message: str) -> DiscoveryOutcome:
        run.finished_at = datetime.now(timezone.utc)
        self.logger.event("discovery_failed", reason=reason_code, message=message)
        await self.surface.capture_screenshot("discovery_failed")
        return DiscoveryOutcome(run=run, status="failed", reason=f"{reason_code}: {message}")

    async def _escalate_or_fail(self, run: RecordedRun, observation: Observation, reason_code: str, message: str) -> DiscoveryOutcome:
        run.finished_at = datetime.now(timezone.utc)
        if self.handoff is None:
            self.logger.event("discovery_escalation_unavailable", reason=reason_code, message=message)
            return DiscoveryOutcome(run=run, status="escalated", reason=f"{reason_code}: {message}")
        intervention = await self.handoff.request_intervention(
            run_id=run.run_id,
            mode=RunMode.DISCOVERY,
            capability_id=run.capability_id,
            goal_summary=self.redactor.redact_text(run.goal),
            step_id=f"step_{len(run.steps)}",
            reason_code=reason_code,
            reason_message=self.redactor.redact_text(message),
        )
        resolution = await self.handoff.wait(intervention.intervention_id)
        if resolution == "aborted":
            return DiscoveryOutcome(run=run, status="aborted", reason=message, intervention_id=intervention.intervention_id)
        # Human resolved the blockage; hand back a terminal escalated status for
        # discovery (a rerun can then complete) — discovery does not attempt to
        # continue model turns after a mid-goal human fix.
        return DiscoveryOutcome(run=run, status="escalated", reason=message, intervention_id=intervention.intervention_id)

    async def _human_step(self, run, observation, action: ClickAction, element, decision) -> DiscoveryOutcome | None:
        """Risky click during discovery: pause, let a human perform it in the
        same browser, validate, and record it as a human-completed step.
        Returns None when the run may continue."""
        intervention = await self.handoff.request_intervention(
            run_id=run.run_id,
            mode=RunMode.DISCOVERY,
            capability_id=run.capability_id,
            goal_summary=self.redactor.redact_text(run.goal),
            step_id=f"step_{len(run.steps)}",
            reason_code="risky_action",
            reason_message=decision.reason,
        )
        resolution = await self.handoff.wait(intervention.intervention_id)
        if resolution == "aborted":
            run.finished_at = datetime.now(timezone.utc)
            return DiscoveryOutcome(run=run, status="aborted", reason=decision.reason, intervention_id=intervention.intervention_id)
        after_obs = await self.surface.observe(label=f"human_step_{len(run.steps):02d}_after")
        run.steps.append(
            RecordedStep(
                index=len(run.steps),
                before=snapshot(observation),
                action=action,
                element=element,
                policy=decision,
                after=snapshot(after_obs),
                human_completed=True,
                started_at=datetime.now(timezone.utc),
            )
        )
        self.logger.event("human_completed_step", step=len(run.steps) - 1, url_after=after_obs.path)
        return None
