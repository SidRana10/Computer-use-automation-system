"""The single structured result contract every run returns.

Callers (an AI agent in production, the CLI here) branch on `status`:
success | business_outcome | failure | escalated.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

from .errors import ErrorClassification


class RecoveryRecord(BaseModel):
    step_id: str
    code: str
    attempts: int
    outcome: Literal["recovered", "exhausted"]


class HumanCompletionRecord(BaseModel):
    step_id: str
    intervention_id: str
    event_count: int


class SuccessResult(BaseModel):
    status: Literal["success"] = "success"
    run_id: str
    capability_id: str
    capability_version: str
    outputs: dict[str, Any] = {}
    recoveries: list[RecoveryRecord] = []
    human_completions: list[HumanCompletionRecord] = []
    evidence: list[str] = []


class BusinessOutcomeResult(BaseModel):
    status: Literal["business_outcome"] = "business_outcome"
    run_id: str
    capability_id: str
    capability_version: str
    code: str
    message: str
    step_id: str | None = None
    outputs: dict[str, Any] = {}
    evidence: list[str] = []


class FailureResult(BaseModel):
    status: Literal["failure"] = "failure"
    run_id: str
    capability_id: str | None = None
    capability_version: str | None = None
    code: str
    category: ErrorClassification = ErrorClassification.HARD_FAILURE
    step_id: str | None = None
    expected: str = ""
    observed: str = ""
    recovery_attempts: int = 0
    evidence: list[str] = []


class EscalatedResult(BaseModel):
    status: Literal["escalated"] = "escalated"
    run_id: str
    capability_id: str | None = None
    capability_version: str | None = None
    code: str
    intervention_id: str
    step_id: str | None = None
    message: str
    resolution: Literal["pending", "aborted", "resume_validation_failed"] = "pending"
    evidence: list[str] = []


RunResult = Annotated[
    Union[SuccessResult, BusinessOutcomeResult, FailureResult, EscalatedResult],
    Field(discriminator="status"),
]
