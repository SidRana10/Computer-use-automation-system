"""ArtifactCompiler: normalize a successful recorded run into a reusable,
parameterized, PII-free capability artifact.

Deterministic application code — no LLM involvement. Fails loudly when it
cannot parameterize a sensitive value or build a usable durable locator.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from ..models.actions import ClickAction, ExtractAction, FillAction, NavigateAction, SelectAction
from ..models.artifact import (
    CapabilityArtifact,
    CapabilityContract,
    CapabilityPolicy,
    InputSpec,
    InputValueRef,
    LiteralValue,
    OutputSpec,
    Provenance,
    StepSpec,
    TargetAppSpec,
    ValueType,
)
from ..models.conditions import ConditionKind, ConditionSpec
from ..models.errors import CompileError, RiskLevel, risk_exceeds
from ..models.targets import TargetDescriptor
from ..policy.engine import PolicyEngine
from .recorder import RecordedRun, RecordedStep

_COMPILED_STEP_KINDS = ("navigate", "click", "fill", "select", "extract")


class ArtifactCompiler:
    def __init__(self, policy: PolicyEngine, error_rules_factory=None):
        self.policy = policy
        self._error_rules_factory = error_rules_factory

    def compile(
        self,
        run: RecordedRun,
        *,
        capability_version: str = "1.0.0",
        app_id: str = "northstar_member_servicing_demo",
        vendor_family: str | None = "northstar_servicing",
    ) -> CapabilityArtifact:
        if not run.success:
            raise CompileError("refusing to compile: the discovery run did not succeed")

        kept = self._select_steps(run)
        if not kept:
            raise CompileError("no executable steps survived normalization")

        bindings = run.input_bindings
        # Every invocation-specific runtime value — sensitive bindings and all
        # extracted values (sensitive by default in this domain) — must be
        # parameterized or excluded wherever it would otherwise be persisted:
        # step values, locator strategies, descriptions, checkpoints, success
        # conditions, and metadata. The final serialized scan is the backstop.
        runtime_values = self._collect_runtime_values(run)

        steps: list[StepSpec] = []
        outputs: list[OutputSpec] = []
        used_actions: set[str] = set()
        route_patterns: set[str] = set()

        entry = urlparse(run.entry_point)
        route_patterns.add(self._parameterize_path(entry.path or "/", bindings))

        for ordinal, recorded in enumerate(kept, start=1):
            step = self._compile_step(ordinal, recorded, run, bindings, runtime_values)
            steps.append(step)
            used_actions.add(step.action)
            if recorded.after is not None:
                route_patterns.add(self._parameterize_path(recorded.after.path, bindings))
            if isinstance(recorded.action, ExtractAction):
                output_type: ValueType = recorded.action.output_type
                outputs.append(
                    OutputSpec(
                        name=recorded.action.output_name,
                        type=output_type,
                        description=f"Extracted from step {step.id}",
                        sensitive=True,  # financial-style values: sensitive by default
                        source_step_id=step.id,
                    )
                )

        success_conditions = self._success_conditions(run, bindings, runtime_values)
        max_risk = RiskLevel.SAFE
        for step in steps:
            if risk_exceeds(step.risk, max_risk):
                max_risk = step.risk

        error_rules = self._error_rules_factory() if self._error_rules_factory else []
        # recovery routes (e.g. interstitial continue) must stay replayable
        route_patterns.add("/session/**")

        artifact = CapabilityArtifact(
            capability_id=run.capability_id,
            capability_version=capability_version,
            name=run.capability_id.replace(".", " ").replace("_", " ").title(),
            description=self._parameterize_text(run.goal, bindings),
            risk_level=max_risk,
            target=TargetAppSpec(
                app_id=app_id,
                vendor_family=vendor_family,
                surface_kind="web",
                entry_point=run.entry_point,
                app_fingerprint=run.app_fingerprint,
            ),
            contract=CapabilityContract(inputs=list(run.input_specs), outputs=outputs),
            steps=steps,
            success_conditions=success_conditions,
            error_rules=error_rules,
            policy=CapabilityPolicy(
                allowed_domains=[entry.hostname or "127.0.0.1"],
                allowed_route_patterns=sorted(route_patterns),
                allowed_actions=sorted(used_actions | {"wait_for", "assert"}),
                max_unattended_risk=RiskLevel.REVERSIBLE,
                require_human_for=[RiskLevel.RISKY, RiskLevel.IRREVERSIBLE],
            ),
            provenance=Provenance(
                discovery_run_id=run.run_id,
                discovered_at=run.finished_at or datetime.now(timezone.utc),
                discovery_model=run.model_name,
                source_app_fingerprint=run.app_fingerprint,
            ),
        )

        self._assert_no_sensitive_values(artifact, runtime_values)
        return artifact

    @staticmethod
    def _collect_runtime_values(run: RecordedRun) -> list[str]:
        """All concrete invocation-specific runtime values from this run:
        sensitive input bindings plus every extracted value (raw and with
        common money formatting stripped, so `$2540.75` also covers `2540.75`)."""
        values: list[str] = []

        def add(value: str) -> None:
            for variant in (value, value.lstrip("$"), value.replace("$", "").replace(",", "")):
                variant = variant.strip()
                if variant and len(variant) >= 3 and variant not in values:
                    values.append(variant)

        for spec in run.input_specs:
            if spec.sensitive and run.input_bindings.get(spec.name):
                add(run.input_bindings[spec.name])
        for recorded in run.steps:
            if recorded.result is not None and recorded.result.extracted_text:
                add(recorded.result.extracted_text)
        return values

    @staticmethod
    def _contains_runtime_value(text: str | None, runtime_values: list[str]) -> bool:
        if not text:
            return False
        normalized = text.replace("$", "").replace(",", "")
        return any(v in text or v in normalized for v in runtime_values)

    # ------------------------------------------------------------- selection

    def _select_steps(self, run: RecordedRun) -> list[RecordedStep]:
        kept: list[RecordedStep] = []
        last_sig: str | None = None
        for step in run.steps:
            if step.action.action not in _COMPILED_STEP_KINDS:
                continue
            if not step.human_completed and (step.result is None or not step.result.ok):
                continue
            if not step.policy.allowed and not step.human_completed:
                continue
            sig = json.dumps(step.action.model_dump(), sort_keys=True, default=str)
            if sig == last_sig:
                continue  # drop consecutive duplicate exploratory actions
            last_sig = sig
            kept.append(step)
        return kept

    # ------------------------------------------------------------ steps

    def _compile_step(
        self,
        ordinal: int,
        recorded: RecordedStep,
        run: RecordedRun,
        bindings: dict[str, str],
        runtime_values: list[str],
    ) -> StepSpec:
        action = recorded.action
        step_id = f"s{ordinal}_{action.action}"
        checkpoints = self._checkpoints_for(recorded, bindings, runtime_values)

        if isinstance(action, NavigateAction):
            return StepSpec(
                id=step_id,
                name=f"Navigate to {self._parameterize_path(urlparse(action.url).path or '/', bindings)}",
                action="navigate",
                url_template=self._url_template(action.url, bindings),
                checkpoint_after=checkpoints,
            )

        element = recorded.element
        if element is None or not element.candidate_strategies:
            raise CompileError(
                f"cannot compile step {step_id}: no durable locator strategies for the interacted element "
                f"(action={action.action}); coordinate-only interactions must be resolved to semantic targets"
            )
        # A locator whose identity embeds an invocation-specific runtime value
        # (a bound sensitive input or an extracted value) is not a reusable
        # target: keep only invocation-independent strategies, and fail loudly
        # if none survive rather than persisting a single-invocation locator.
        durable_strategies = [
            s
            for s in element.candidate_strategies
            if not self._contains_runtime_value(s.name, runtime_values)
            and not self._contains_runtime_value(s.value, runtime_values)
        ]
        if not durable_strategies:
            raise CompileError(
                f"cannot compile step {step_id}: every candidate locator strategy embeds an "
                "invocation-specific runtime value; no reusable target identity exists for this element"
            )
        if isinstance(action, ExtractAction):
            # the element's text IS the (sensitive) extracted value; identify
            # the target by stable identity, never by content
            ident = element.id_attr or element.name_attr or action.output_name
            description = f"{element.kind} '{ident}'"
        else:
            description = self._scrub_text(
                self._parameterize_text(
                    f"{element.kind} '{element.accessible_name or element.text or element.id_attr}'", bindings
                ),
                runtime_values,
            )
        target = TargetDescriptor(description=description, strategies=durable_strategies)

        if isinstance(action, ClickAction):
            control_risk = self.policy.classify_control_risk(element.accessible_name or element.text)
            return StepSpec(
                id=step_id,
                name=self._parameterize_text(f"Click {element.accessible_name or element.text or element.kind}", bindings),
                action="click",
                target=target,
                risk=control_risk,
                checkpoint_after=checkpoints,
            )

        if isinstance(action, (FillAction, SelectAction)):
            value = self._compile_value(action, run, bindings, step_id)
            return StepSpec(
                id=step_id,
                name=self._parameterize_text(
                    f"{'Fill' if isinstance(action, FillAction) else 'Select'} {element.label or element.accessible_name or element.kind}",
                    bindings,
                ),
                action="fill" if isinstance(action, FillAction) else "select",
                target=target,
                value=value,
                risk=RiskLevel.REVERSIBLE,
                checkpoint_after=checkpoints,
            )

        if isinstance(action, ExtractAction):
            return StepSpec(
                id=step_id,
                name=f"Extract {action.output_name}",
                action="extract",
                target=target,
                output_name=action.output_name,
                output_type=action.output_type,
                checkpoint_after=[],
            )

        raise CompileError(f"unsupported recorded action {action.action}")

    def _compile_value(self, action: FillAction | SelectAction, run: RecordedRun, bindings: dict[str, str], step_id: str):
        source = action.value_source
        declared = {s.name: s for s in run.input_specs}
        if source.input_name:
            if source.input_name not in declared:
                raise CompileError(f"step {step_id} references undeclared input {source.input_name!r}")
            return InputValueRef(name=source.input_name)
        literal = source.literal or ""
        # primary deterministic mapping: literal equal to a binding -> input ref
        for name, bound in bindings.items():
            if literal == bound:
                return InputValueRef(name=name)
        for spec in run.input_specs:
            if spec.sensitive and bindings.get(spec.name) and bindings[spec.name] in literal:
                raise CompileError(
                    f"step {step_id}: literal value embeds sensitive input {spec.name!r} and cannot be parameterized"
                )
        return LiteralValue(value=literal)

    # ------------------------------------------------------------ conditions

    def _checkpoints_for(
        self, recorded: RecordedStep, bindings: dict[str, str], runtime_values: list[str]
    ) -> list[ConditionSpec]:
        if recorded.after is None or recorded.before.path == recorded.after.path:
            return []
        checkpoints = [
            ConditionSpec(kind=ConditionKind.URL_MATCHES, value=self._parameterize_path(recorded.after.path, bindings))
        ]
        heading = recorded.after.heading
        if (
            heading
            and not self._contains_binding(heading, bindings)
            and not self._contains_runtime_value(heading, runtime_values)
        ):
            checkpoints.append(ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value=heading))
        return checkpoints

    def _success_conditions(
        self, run: RecordedRun, bindings: dict[str, str], runtime_values: list[str]
    ) -> list[ConditionSpec]:
        conditions: list[ConditionSpec] = []
        if run.final_state is not None:
            conditions.append(
                ConditionSpec(kind=ConditionKind.URL_MATCHES, value=self._parameterize_path(run.final_state.path, bindings))
            )
        # The model's suggested condition is only reusable if it references
        # stable UI, not this invocation's concrete values (e.g. a success
        # condition of "text_present: <the extracted balance>" verifies one
        # member's balance, not the flow — drop it and rely on structural
        # conditions instead).
        suggested = run.suggested_success_condition
        if (
            suggested is not None
            and not self._contains_binding(suggested.value, bindings)
            and not self._contains_runtime_value(suggested.value, runtime_values)
        ):
            kind = ConditionKind.URL_MATCHES if suggested.kind == "url_matches" else ConditionKind.TEXT_PRESENT
            value = self._parameterize_path(suggested.value, bindings) if kind == ConditionKind.URL_MATCHES else suggested.value
            if not any(c.kind == kind and c.value == value for c in conditions):
                conditions.append(ConditionSpec(kind=kind, value=value))
        if not conditions:
            raise CompileError("could not derive any success condition for the artifact")
        return conditions

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _contains_binding(text: str, bindings: dict[str, str]) -> bool:
        return any(v and v in text for v in bindings.values())

    @staticmethod
    def _scrub_text(text: str, runtime_values: list[str]) -> str:
        """Replace any remaining concrete runtime value in free text (e.g. a
        target description) with a neutral marker."""
        for value in runtime_values:
            if value in text:
                text = text.replace(value, "[dynamic-value]")
        return text

    @staticmethod
    def _parameterize_path(path: str, bindings: dict[str, str]) -> str:
        out = path
        for value in bindings.values():
            if value:
                out = out.replace(value, "*")
        return out

    @staticmethod
    def _parameterize_text(text: str, bindings: dict[str, str]) -> str:
        out = text
        for name, value in bindings.items():
            if value:
                out = out.replace(value, "{" + name + "}")
        return out

    def _url_template(self, url: str, bindings: dict[str, str]) -> str:
        parsed = urlparse(url)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        for name, value in bindings.items():
            if value:
                path = path.replace(value, "{" + name + "}")
        return path

    @staticmethod
    def _assert_no_sensitive_values(artifact: CapabilityArtifact, sensitive_values: list[str]) -> None:
        serialized = artifact.model_dump_json()
        for value in sensitive_values:
            if value in serialized:
                raise CompileError(
                    "compiled artifact embeds a sensitive invocation value; refusing to save. "
                    "This indicates a parameterization gap."
                )


def save_artifact(artifact: CapabilityArtifact, path) -> None:
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(json.loads(artifact.model_dump_json()), indent=2, ensure_ascii=False) + "\n")


def load_artifact(path) -> CapabilityArtifact:
    from pathlib import Path

    return CapabilityArtifact.model_validate_json(Path(path).read_text())
