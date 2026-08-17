"""Discovery run recording: redacted structured facts per step, kept strictly
separate from the compiled capability artifact.

Raw sensitive values (invocation bindings, extracted sensitive text) live only
in process memory; they are excluded from serialization and scrubbed by the
Redactor on any logging path.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ..models.actions import DiscoveryAction, SuggestedCondition
from ..models.artifact import InputSpec
from ..policy.engine import PolicyDecision
from ..surfaces.base import ActionResult, ObservedElement


class StateSnapshot(BaseModel):
    url: str
    path: str
    title: str
    heading: str | None = None
    fingerprint: str


class RecordedStep(BaseModel):
    index: int
    before: StateSnapshot
    action: DiscoveryAction
    element: ObservedElement | None = None
    policy: PolicyDecision
    result: ActionResult | None = None
    after: StateSnapshot | None = None
    human_completed: bool = False
    started_at: datetime
    duration_ms: int = 0


class RecordedRun(BaseModel):
    run_id: str = Field(default_factory=lambda: f"disc-{uuid.uuid4().hex[:10]}")
    goal: str
    capability_id: str
    entry_point: str
    target_app_name: str = ""
    model_name: str = ""
    input_specs: list[InputSpec] = []
    # concrete invocation values: process memory only, never serialized
    input_bindings: dict[str, str] = Field(default_factory=dict, exclude=True)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    steps: list[RecordedStep] = []
    success: bool = False
    done_summary: str | None = None
    suggested_success_condition: SuggestedCondition | None = None
    final_state: StateSnapshot | None = None
    app_fingerprint: dict[str, str] = {}
