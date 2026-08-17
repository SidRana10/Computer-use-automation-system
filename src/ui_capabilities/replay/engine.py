"""Deterministic replay engine: an interpreter for capability artifacts.

Core invariant: ZERO LLM decision calls. This module (and everything it
imports) has no model-client dependency — that is architectural, not merely a
runtime flag.

For each step: bind values, policy-check, resolve target by ordered
strategies, execute with bounded waits, evaluate checkpoints, classify any
failure against declared error rules (business outcome / recoverable / hard),
apply bounded recovery, and log everything. Returns one structured RunResult.
"""

from __future__ import annotations

from ..config import Settings
from ..models.artifact import CapabilityArtifact, StepSpec
from ..models.conditions import ConditionSpec
from ..models.errors import ErrorClassification, FailureCode
from ..models.intervention import RunMode
from ..models.results import (
    BusinessOutcomeResult,
    EscalatedResult,
    FailureResult,
    HumanCompletionRecord,
    RecoveryRecord,
    RunResult,
    SuccessResult,
)
from ..observability.evidence import EvidenceManager
from ..observability.logger import RunLogger
from ..policy.engine import PolicyEngine
from ..policy.redaction import Redactor
from ..surfaces.base import ActionResult, ExecutableAction, SurfaceAdapter
from . import binder
from .error_classifier import classify_current_state
from .recovery import perform_recovery


class _StepOutcome(Exception):
    """Internal control-flow carrier for terminal step results."""

    def __init__(self, result: RunResult):
        self.result = result


class ReplayEngine:
    def __init__(
        self,
        *,
        surface: SurfaceAdapter,
        global_policy: PolicyEngine,
        settings: Settings,
        logger: RunLogger,
        evidence: EvidenceManager,
        redactor: Redactor,
        handoff=None,  # HandoffManager | None
    ):
        self.surface = surface
        self.settings = settings
        self.logger = logger
        self.evidence = evidence
        self.redactor = redactor
        self.handoff = handoff
        self._global_policy = global_policy

    async def replay(self, artifact: CapabilityArtifact, inputs: dict[str, str]) -> RunResult:
        run_id = self.evidence.run_id

        # 1-2. validate invocation against contract, before any browser action
        try:
            bound = binder.validate_and_bind(artifact.contract, inputs)
        except binder.InvocationError as exc:
            self.logger.event("invocation_rejected", error=str(exc))
            return FailureResult(
                run_id=run_id,
                capability_id=artifact.capability_id,
                capability_version=artifact.capability_version,
                code=FailureCode.INVOCATION_INVALID,
                expected="invocation matching the capability contract",
                observed=str(exc),
            )
        for spec in artifact.contract.inputs:
            if spec.sensitive and spec.name in bound:
                self.redactor.register_sensitive_value(bound[spec.name])

        # 3. strictest-composition policy
        policy = PolicyEngine(self._global_policy.config.narrowed_by(artifact.policy))

        self.logger.event(
            "replay_started",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            inputs=sorted(bound.keys()),
        )

        # 4. open target
        await self.surface.start(artifact.target.entry_point)
        await self.surface.start_trace()

        recoveries: list[RecoveryRecord] = []
        human_completions: list[HumanCompletionRecord] = []
        extracted: dict[str, str] = {}

        try:
            # 5. fingerprint / preconditions
            await self._verify_fingerprint(artifact, run_id)
            for condition in artifact.preconditions:
                await self._require_condition(artifact, None, condition, "precondition")

            # 6. steps
            for step in artifact.steps:
                await self._run_step(artifact, step, bound, policy, recoveries, human_completions, extracted)

            # 8. final success conditions
            for condition in artifact.success_conditions:
                await self._require_condition(artifact, None, condition, "success condition")

            # 7. outputs
            outputs = {}
            for spec in artifact.contract.outputs:
                if spec.name not in extracted:
                    raise _StepOutcome(
                        await self._hard_failure(
                            artifact,
                            step_id=spec.source_step_id,
                            code=FailureCode.OUTPUT_EXTRACTION_FAILED,
                            expected=f"extracted value for output {spec.name!r}",
                            observed="no value was extracted",
                        )
                    )
                try:
                    outputs[spec.name] = binder.coerce_output(spec.name, extracted[spec.name], spec.type)
                except binder.OutputCoercionError as exc:
                    raise _StepOutcome(
                        await self._hard_failure(
                            artifact,
                            step_id=spec.source_step_id,
                            code=FailureCode.OUTPUT_EXTRACTION_FAILED,
                            expected=f"text coercible to {spec.type}",
                            observed=str(exc),
                        )
                    ) from None

            self.logger.event("replay_succeeded", outputs=list(outputs.keys()), recoveries=len(recoveries))
            return SuccessResult(
                run_id=run_id,
                capability_id=artifact.capability_id,
                capability_version=artifact.capability_version,
                outputs=outputs,
                recoveries=recoveries,
                human_completions=human_completions,
                evidence=self.evidence.files(),
            )
        except _StepOutcome as outcome:
            return outcome.result
        finally:
            await self.surface.stop_trace()

    # ------------------------------------------------------------------ steps

    async def _run_step(
        self,
        artifact: CapabilityArtifact,
        step: StepSpec,
        bound: dict[str, str],
        policy: PolicyEngine,
        recoveries: list[RecoveryRecord],
        human_completions: list[HumanCompletionRecord],
        extracted: dict[str, str],
    ) -> None:
        executable = self._to_executable(step, bound, artifact)

        decision = policy.check_action(
            step.action,
            url=executable.url,
            risk=step.risk,
            control_text=step.target.description if step.target else None,
        )
        self.logger.event("policy_checked", step_id=step.id, allowed=decision.allowed, requires_human=decision.requires_human, code=decision.code)

        if decision.requires_human:
            await self._escalate_step(artifact, step, human_completions)
            return  # human performed the step; checkpoints validated on resume
        if not decision.allowed:
            raise _StepOutcome(
                await self._hard_failure(
                    artifact,
                    step_id=step.id,
                    code=FailureCode.POLICY_BLOCKED,
                    expected="step permitted by effective policy",
                    observed=decision.reason,
                )
            )

        max_attempts = self.settings.max_recovery_attempts
        if step.on_error is not None:
            max_attempts = min(max_attempts, step.on_error.max_attempts)

        attempts = 0
        while True:
            result = await self.surface.execute(executable)
            # a navigation/click may have been redirected: the landed URL must
            # still be inside policy (docs/06 — no silent off-policy redirects)
            if result.ok and step.action in ("navigate", "click"):
                landed = policy.check_url(self.surface.current_url())
                if not landed.allowed:
                    raise _StepOutcome(
                        await self._hard_failure(
                            artifact,
                            step_id=step.id,
                            code=FailureCode.POLICY_BLOCKED,
                            expected="post-action URL inside the policy allowlist",
                            observed=f"landed outside policy: {landed.reason}",
                            recovery_attempts=attempts,
                        )
                    )
            checkpoint_failure: ConditionSpec | None = None
            if result.ok:
                if step.action == "extract" and result.extracted_text is not None:
                    extracted[step.output_name or step.id] = result.extracted_text
                    self.redactor.register_sensitive_value(result.extracted_text)
                if result.matched_strategy is not None:
                    self.logger.event("target_resolved", step_id=step.id, strategy=result.matched_strategy.kind.value)
                checkpoint_failure = await self._first_failing_checkpoint(step)
                if checkpoint_failure is None:
                    self.logger.event("step_completed", step_id=step.id, attempts=attempts)
                    return

            # something is wrong: classify against declared rules
            rule = await classify_current_state(self.surface, artifact)
            if rule is not None and rule.classification == ErrorClassification.BUSINESS_OUTCOME:
                self.logger.event("business_outcome", step_id=step.id, code=rule.code)
                await self.surface.capture_screenshot(f"{step.id}_business_outcome")
                raise _StepOutcome(
                    BusinessOutcomeResult(
                        run_id=self.evidence.run_id,
                        capability_id=artifact.capability_id,
                        capability_version=artifact.capability_version,
                        code=rule.code,
                        message=rule.caller_message,
                        step_id=step.id,
                        evidence=self.evidence.files(),
                    )
                )
            if rule is not None and rule.classification == ErrorClassification.HARD_FAILURE:
                raise _StepOutcome(
                    await self._hard_failure(
                        artifact,
                        step_id=step.id,
                        code=rule.code,
                        expected="step to complete without a declared fatal condition",
                        observed=rule.caller_message,
                        recovery_attempts=attempts,
                    )
                )
            if rule is not None and rule.classification == ErrorClassification.RECOVERABLE:
                budget = min(rule.max_attempts or self.settings.max_recovery_attempts, max_attempts) or max_attempts
                if attempts < budget:
                    attempts += 1
                    recovery = await perform_recovery(self.surface, rule, policy)
                    self.logger.event(
                        "recovery_attempted",
                        step_id=step.id,
                        code=rule.code,
                        attempt=attempts,
                        notes=recovery.notes,
                        denied=recovery.denied_action,
                    )
                    if recovery.denied:
                        raise _StepOutcome(
                            await self._hard_failure(
                                artifact,
                                step_id=step.id,
                                code=FailureCode.POLICY_BLOCKED,
                                expected=f"recovery {rule.code} ({recovery.denied_action}) permitted by effective policy",
                                observed=recovery.denial.reason,
                                recovery_attempts=attempts,
                            )
                        )
                    notes = recovery.notes
                    # recovery may already have restored the expected state
                    if await self._first_failing_checkpoint(step) is None and (result.ok or step.action in ("navigate", "click")):
                        recoveries.append(RecoveryRecord(step_id=step.id, code=rule.code, attempts=attempts, outcome="recovered"))
                        self.logger.event("step_completed", step_id=step.id, attempts=attempts, recovered=True)
                        return
                    continue  # retry the step action itself
                recoveries.append(RecoveryRecord(step_id=step.id, code=rule.code, attempts=attempts, outcome="exhausted"))
                raise _StepOutcome(
                    await self._hard_failure(
                        artifact,
                        step_id=step.id,
                        code=FailureCode.RETRY_EXHAUSTED,
                        expected=f"recovery {rule.code} to restore the expected state within {budget} attempts",
                        observed=f"still failing after {attempts} attempts",
                        recovery_attempts=attempts,
                    )
                )

            # no declared rule matched -> unclassified hard failure
            if not result.ok:
                code = {
                    "TARGET_NOT_FOUND": FailureCode.TARGET_NOT_FOUND,
                    "AMBIGUOUS_TARGET": FailureCode.AMBIGUOUS_TARGET,
                    "TIMEOUT": FailureCode.UNEXPECTED_STATE,
                }.get(result.error_code or "", FailureCode.EXECUTION_ERROR)
                expected = self._expected_for(step)
                observed = result.message or (result.error_code or "unknown execution error")
            else:
                code = FailureCode.CHECKPOINT_FAILED
                expected = f"checkpoint {checkpoint_failure.kind.value}={checkpoint_failure.value!r} after step"
                observed = f"checkpoint not satisfied at {self.surface.current_url()}"
            raise _StepOutcome(
                await self._hard_failure(
                    artifact,
                    step_id=step.id,
                    code=code,
                    expected=expected,
                    observed=observed,
                    recovery_attempts=attempts,
                )
            )

    def _expected_for(self, step: StepSpec) -> str:
        if step.target is not None:
            kinds = [s.kind.value for s in step.target.strategies]
            return f"{step.target.description} resolvable by strategies {kinds}"
        return f"{step.action} to execute"

    async def _first_failing_checkpoint(self, step: StepSpec) -> ConditionSpec | None:
        for condition in step.checkpoint_after:
            result = await self.surface.evaluate_condition(condition)
            if not result.satisfied:
                return condition
        return None

    def _to_executable(self, step: StepSpec, bound: dict[str, str], artifact: CapabilityArtifact) -> ExecutableAction:
        timeout = step.timeout_ms or self.settings.default_step_timeout_ms
        if step.action == "navigate":
            url = binder.render_url(step.url_template or "/", bound, artifact.target.entry_point)
            return ExecutableAction(kind="navigate", url=url, timeout_ms=timeout)
        value = binder.resolve_value(step.value, bound) if step.value is not None else None
        kind = step.action if step.action in ("click", "fill", "select", "extract") else "wait"
        return ExecutableAction(kind=kind, target=step.target, value=value, timeout_ms=timeout)

    # ------------------------------------------------------------- conditions

    async def _require_condition(self, artifact: CapabilityArtifact, step_id: str | None, condition: ConditionSpec, label: str) -> None:
        result = await self.surface.evaluate_condition(condition)
        if result.satisfied:
            return
        rule = await classify_current_state(self.surface, artifact)
        if rule is not None and rule.classification == ErrorClassification.BUSINESS_OUTCOME:
            await self.surface.capture_screenshot(f"{label.replace(' ', '_')}_business_outcome")
            raise _StepOutcome(
                BusinessOutcomeResult(
                    run_id=self.evidence.run_id,
                    capability_id=artifact.capability_id,
                    capability_version=artifact.capability_version,
                    code=rule.code,
                    message=rule.caller_message,
                    step_id=step_id,
                    evidence=self.evidence.files(),
                )
            )
        raise _StepOutcome(
            await self._hard_failure(
                artifact,
                step_id=step_id,
                code=FailureCode.CHECKPOINT_FAILED,
                expected=f"{label}: {condition.kind.value}={condition.value!r}",
                observed=result.detail or f"not satisfied at {self.surface.current_url()}",
            )
        )

    async def _verify_fingerprint(self, artifact: CapabilityArtifact, run_id: str) -> None:
        expected_title = artifact.target.app_fingerprint.get("app_title")
        if not expected_title:
            return
        observation = await self.surface.observe(label="fingerprint")
        if expected_title not in observation.title:
            raise _StepOutcome(
                await self._hard_failure(
                    artifact,
                    step_id=None,
                    code=FailureCode.TARGET_APP_MISMATCH,
                    expected=f"app title containing {expected_title!r}",
                    observed=f"title {observation.title!r}",
                )
            )

    # ------------------------------------------------------------- failures

    async def _hard_failure(
        self,
        artifact: CapabilityArtifact,
        *,
        step_id: str | None,
        code: str,
        expected: str,
        observed: str,
        recovery_attempts: int = 0,
    ) -> FailureResult:
        try:
            screenshot = await self.surface.capture_screenshot(f"failure_{step_id or 'run'}")
            evidence = [str(screenshot)]
        except Exception:  # browser may already be gone; failure result still returned
            evidence = []
        self.logger.event(
            "hard_failure",
            step_id=step_id,
            code=str(code),
            expected=expected,
            observed=observed,
            recovery_attempts=recovery_attempts,
        )
        return FailureResult(
            run_id=self.evidence.run_id,
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            code=str(code),
            step_id=step_id,
            expected=expected,
            observed=self.redactor.redact_text(observed),
            recovery_attempts=recovery_attempts,
            evidence=evidence + self.evidence.files(),
        )

    # ------------------------------------------------------------- escalation

    async def _escalate_step(self, artifact: CapabilityArtifact, step: StepSpec, human_completions: list[HumanCompletionRecord]) -> None:
        if self.handoff is None:
            raise _StepOutcome(
                EscalatedResult(
                    run_id=self.evidence.run_id,
                    capability_id=artifact.capability_id,
                    capability_version=artifact.capability_version,
                    code="HUMAN_APPROVAL_REQUIRED",
                    intervention_id="",
                    step_id=step.id,
                    message=f"step {step.id} ({step.risk.value}) requires a human operator, and no handoff channel is available",
                )
            )
        intervention = await self.handoff.request_intervention(
            run_id=self.evidence.run_id,
            mode=RunMode.REPLAY,
            capability_id=artifact.capability_id,
            goal_summary=artifact.description,
            step_id=step.id,
            reason_code="HUMAN_APPROVAL_REQUIRED",
            reason_message=f"Step {step.id!r} is {step.risk.value}; policy requires a human operator to perform it.",
        )
        resolution = await self.handoff.wait(intervention.intervention_id)
        if resolution == "aborted":
            raise _StepOutcome(
                EscalatedResult(
                    run_id=self.evidence.run_id,
                    capability_id=artifact.capability_id,
                    capability_version=artifact.capability_version,
                    code="HUMAN_APPROVAL_REQUIRED",
                    intervention_id=intervention.intervention_id,
                    step_id=step.id,
                    message="operator aborted the run",
                    resolution="aborted",
                    evidence=self.evidence.files(),
                )
            )
        # human says done: re-observe and validate this step's checkpoints
        failing = await self._first_failing_checkpoint(step)
        if failing is not None:
            self.handoff.mark_validation_failed(intervention.intervention_id)
            raise _StepOutcome(
                EscalatedResult(
                    run_id=self.evidence.run_id,
                    capability_id=artifact.capability_id,
                    capability_version=artifact.capability_version,
                    code="RESUME_VALIDATION_FAILED",
                    intervention_id=intervention.intervention_id,
                    step_id=step.id,
                    message=f"after human control, checkpoint {failing.kind.value}={failing.value!r} still fails",
                    resolution="resume_validation_failed",
                    evidence=self.evidence.files(),
                )
            )
        self.handoff.confirm_automation_resumed(intervention.intervention_id)
        events = self.handoff.human_event_count(intervention.intervention_id)
        human_completions.append(
            HumanCompletionRecord(step_id=step.id, intervention_id=intervention.intervention_id, event_count=events)
        )
        self.logger.event("human_completed_step", step_id=step.id, intervention_id=intervention.intervention_id, events=events)
