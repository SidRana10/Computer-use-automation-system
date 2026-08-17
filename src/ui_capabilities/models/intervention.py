"""Human-in-the-loop control transfer models.

Control ownership is explicit and typed; automation and a human can never both
hold the session.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ControlOwner(StrEnum):
    AUTOMATION = "AUTOMATION"
    PAUSED = "PAUSED"
    HUMAN = "HUMAN"


class RunMode(StrEnum):
    DISCOVERY = "discovery"
    REPLAY = "replay"


class RunState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


InterventionStatus = Literal["open", "claimed", "resumed", "aborted", "resolved"]


class HumanActionEvent(BaseModel):
    """Redacted record of one human interaction during takeover.
    Typed values are never captured — only element identity and the fact a
    value changed."""

    event: str  # click | change | submit | navigation
    tag: str | None = None
    text: str | None = None
    aria_label: str | None = None
    name: str | None = None
    value_changed: bool | None = None
    value: Literal["[REDACTED]"] | None = None
    url: str | None = None
    timestamp: str | None = None


class InterventionRequest(BaseModel):
    intervention_id: str
    run_id: str
    mode: RunMode
    capability_id: str | None = None
    goal_summary: str
    step_id: str | None = None
    reason_code: str
    reason_message: str
    control_owner: ControlOwner = ControlOwner.PAUSED
    screenshot_path: str = ""
    current_url: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: InterventionStatus = "open"
    operator_id: str | None = None
    operator_note: str | None = None
    human_events: list[HumanActionEvent] = []
    before_screenshot: str = ""
    after_screenshot: str = ""
