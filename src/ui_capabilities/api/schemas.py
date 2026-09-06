"""Wire schemas for the capability API. Deliberately thin: everything here
either mirrors a field already on `CapabilityArtifact`/`RunResult` or is a
small derived view over the evidence directory. No new business logic lives
here.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ..models.artifact import CapabilityArtifact, ValueType
from ..models.results import RunResult

# Inputs every MERIDIAN artifact declares that the operating environment
# supplies, never a caller: the operator sign-on identity and branch context.
# See targets/meridian.py MERIDIAN_INPUT_SPECS and D017 (each capability
# carries its own sign-on prefix). Centralized here so the API, the chatbot,
# and their tests agree on exactly one list.
SERVER_SUPPLIED_INPUTS: frozenset[str] = frozenset({"operator_id", "password", "branch"})


class InputField(BaseModel):
    name: str
    type: ValueType
    required: bool
    sensitive: bool
    description: str
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None


class OutputField(BaseModel):
    name: str
    type: ValueType
    description: str


class CapabilitySummary(BaseModel):
    capability_id: str
    capability_version: str
    name: str
    description: str
    risk_level: str
    target_app_id: str
    target_display_name: str
    input_count: int
    output_count: int


class CapabilityDetail(CapabilitySummary):
    inputs: list[InputField]
    outputs: list[OutputField]
    escalate_on_codes: list[str]


def _public_inputs(artifact: CapabilityArtifact) -> list[InputField]:
    return [
        InputField(
            name=spec.name,
            type=spec.type,
            required=spec.required,
            sensitive=spec.sensitive,
            description=spec.description,
            pattern=spec.pattern,
            minimum=spec.minimum,
            maximum=spec.maximum,
        )
        for spec in artifact.contract.inputs
        if spec.name not in SERVER_SUPPLIED_INPUTS
    ]


def to_summary(artifact: CapabilityArtifact, target_display_name: str) -> CapabilitySummary:
    return CapabilitySummary(
        capability_id=artifact.capability_id,
        capability_version=artifact.capability_version,
        name=artifact.name,
        description=artifact.description,
        risk_level=artifact.risk_level.value,
        target_app_id=artifact.target.app_id,
        target_display_name=target_display_name,
        input_count=len(_public_inputs(artifact)),
        output_count=len(artifact.contract.outputs),
    )


def to_detail(artifact: CapabilityArtifact, target_display_name: str) -> CapabilityDetail:
    summary = to_summary(artifact, target_display_name)
    return CapabilityDetail(
        **summary.model_dump(),
        inputs=_public_inputs(artifact),
        outputs=[
            OutputField(name=o.name, type=o.type, description=o.description) for o in artifact.contract.outputs
        ],
        escalate_on_codes=list(artifact.policy.escalate_on_codes),
    )


class InvokeRequest(BaseModel):
    inputs: dict[str, Any] = {}


class RunSummary(BaseModel):
    run_id: str
    capability_id: str
    capability_version: str
    capability_name: str
    status: str
    code: str | None = None
    started_at: str
    finished_at: str
    duration_ms: int


class RunDetail(RunSummary):
    inputs: dict[str, Any]
    result: RunResult
    evidence_files: list[str]
    events: list[dict[str, Any]]
