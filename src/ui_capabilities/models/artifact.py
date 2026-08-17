"""The capability artifact: a typed, versioned, parameterized, reviewable
description of a UI flow that an AI agent can invoke by contract.

This is deliberately NOT a raw model transcript. The compiler normalizes a
successful discovery run into this schema; replay interprets it with no LLM.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

from .conditions import ConditionSpec
from .errors import ErrorClassification, RiskLevel
from .targets import TargetDescriptor

SCHEMA_VERSION = "1.0"

ValueType = Literal["string", "integer", "decimal", "boolean"]

# Artifact step actions. `done`/`request_human` are discovery control signals
# and never become artifact steps.
StepAction = Literal["navigate", "click", "fill", "select", "extract", "wait_for", "assert"]

_TARGETED_ACTIONS = {"click", "fill", "select", "extract"}
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_CAPABILITY_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


class ApprovalState(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class InputValueRef(BaseModel):
    """A reference to a declared invocation input; the concrete value is bound
    at replay time and never stored in the artifact."""

    kind: Literal["input"] = "input"
    name: str


class LiteralValue(BaseModel):
    kind: Literal["literal"] = "literal"
    value: str | int | float | bool
    sensitive: bool = False


ValueRef = Annotated[Union[InputValueRef, LiteralValue], Field(discriminator="kind")]


class InputSpec(BaseModel):
    name: str
    type: ValueType
    required: bool = True
    description: str
    sensitive: bool = False
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None


class OutputSpec(BaseModel):
    name: str
    type: ValueType
    description: str
    sensitive: bool = False
    source_step_id: str


class CapabilityContract(BaseModel):
    inputs: list[InputSpec] = []
    outputs: list[OutputSpec] = []


class TargetAppSpec(BaseModel):
    app_id: str
    vendor_family: str | None = None
    surface_kind: Literal["web"] = "web"
    entry_point: str
    compatible_variants: list[str] = []
    app_fingerprint: dict[str, str] = {}


class RecoveryActionSpec(BaseModel):
    """One bounded, explicit recovery move. Never an open-ended agent loop."""

    kind: Literal["dismiss", "wait", "reload"]
    target: TargetDescriptor | None = None  # control to click for "dismiss"
    wait_ms: int | None = None

    @model_validator(mode="after")
    def _shape(self) -> "RecoveryActionSpec":
        if self.kind == "dismiss" and self.target is None:
            raise ValueError("dismiss recovery requires a target")
        if self.kind == "wait" and not self.wait_ms:
            raise ValueError("wait recovery requires wait_ms")
        return self


class ErrorRule(BaseModel):
    code: str
    classification: ErrorClassification
    when: list[ConditionSpec] = Field(min_length=1)
    recovery: list[RecoveryActionSpec] = []
    max_attempts: int = 0
    caller_message: str

    @model_validator(mode="after")
    def _recovery_only_for_recoverable(self) -> "ErrorRule":
        if self.recovery and self.classification != ErrorClassification.RECOVERABLE:
            raise ValueError("recovery actions are only valid for recoverable rules")
        return self


class StepErrorPolicy(BaseModel):
    """Per-step override of retry budget for recoverable conditions."""

    max_attempts: int = 1


class StepSpec(BaseModel):
    id: str
    name: str
    action: StepAction
    target: TargetDescriptor | None = None
    value: ValueRef | None = None
    url_template: str | None = None  # navigate only; {name} placeholders bind inputs
    output_name: str | None = None
    output_type: ValueType | None = None
    timeout_ms: int | None = None
    risk: RiskLevel = RiskLevel.SAFE
    checkpoint_after: list[ConditionSpec] = []
    on_error: StepErrorPolicy | None = None

    @model_validator(mode="after")
    def _shape(self) -> "StepSpec":
        if self.action in _TARGETED_ACTIONS and self.target is None:
            raise ValueError(f"step {self.id!r}: action {self.action!r} requires a target")
        if self.action == "navigate" and not self.url_template:
            raise ValueError(f"step {self.id!r}: navigate requires url_template")
        if self.action == "extract" and not self.output_name:
            raise ValueError(f"step {self.id!r}: extract requires output_name")
        if self.action in {"fill", "select"} and self.value is None:
            raise ValueError(f"step {self.id!r}: {self.action} requires a value")
        return self


class CapabilityPolicy(BaseModel):
    """Artifact-scoped policy. Composed with the global policy at replay by
    intersection: an artifact can narrow global privileges, never broaden."""

    allowed_domains: list[str]
    allowed_route_patterns: list[str]
    allowed_actions: list[str]
    max_unattended_risk: RiskLevel = RiskLevel.REVERSIBLE
    require_human_for: list[RiskLevel] = [RiskLevel.RISKY, RiskLevel.IRREVERSIBLE]


class Provenance(BaseModel):
    discovery_run_id: str
    discovered_at: datetime
    discovery_model: str
    source_app_fingerprint: dict[str, str] = {}


class CapabilityArtifact(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    capability_id: str
    capability_version: str
    name: str
    description: str
    approval_state: ApprovalState = ApprovalState.DRAFT
    risk_level: RiskLevel = RiskLevel.SAFE
    target: TargetAppSpec
    contract: CapabilityContract
    preconditions: list[ConditionSpec] = []
    steps: list[StepSpec] = Field(min_length=1)
    success_conditions: list[ConditionSpec] = Field(min_length=1)
    error_rules: list[ErrorRule] = []
    policy: CapabilityPolicy
    provenance: Provenance

    @model_validator(mode="after")
    def _cross_validate(self) -> "CapabilityArtifact":
        if not _CAPABILITY_ID_RE.match(self.capability_id):
            raise ValueError(f"capability_id {self.capability_id!r} must look like 'domain.verb_noun'")
        if not _SEMVER_RE.match(self.capability_version):
            raise ValueError(f"capability_version {self.capability_version!r} must be semver MAJOR.MINOR.PATCH")

        step_ids = [s.id for s in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("step ids must be unique")
        step_id_set = set(step_ids)

        input_names = {i.name for i in self.contract.inputs}
        for out in self.contract.outputs:
            if out.source_step_id not in step_id_set:
                raise ValueError(f"output {out.name!r} references unknown step {out.source_step_id!r}")
            src = next(s for s in self.steps if s.id == out.source_step_id)
            if src.action != "extract":
                raise ValueError(f"output {out.name!r} source step {src.id!r} is not an extract step")

        declared_outputs = {o.name for o in self.contract.outputs}
        for step in self.steps:
            if isinstance(step.value, InputValueRef) and step.value.name not in input_names:
                raise ValueError(f"step {step.id!r} references undeclared input {step.value.name!r}")
            if step.url_template:
                for ph in re.findall(r"\{([a-z_][a-z0-9_]*)\}", step.url_template):
                    if ph not in input_names:
                        raise ValueError(f"step {step.id!r} url_template references undeclared input {ph!r}")
            if step.action == "extract" and step.output_name not in declared_outputs:
                raise ValueError(f"extract step {step.id!r} output {step.output_name!r} not declared in contract")

        # highest step risk must not be understated at artifact level
        risks = [s.risk for s in self.steps]
        if RiskLevel.IRREVERSIBLE in risks and self.risk_level not in (RiskLevel.IRREVERSIBLE,):
            raise ValueError("artifact containing an irreversible step must declare risk_level=irreversible")
        return self
