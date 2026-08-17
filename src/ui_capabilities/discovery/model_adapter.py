"""Model adapter seam: discovery asks *some* adapter for one structured next
action. The Anthropic adapter is the genuine path; the scripted fake exists
only for tests/offline smoke runs and can never produce real evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..models.actions import DiscoveryAction
from ..models.artifact import InputSpec
from ..policy.config import PolicyConfig
from ..surfaces.base import Observation


@dataclass
class TurnContext:
    goal: str
    target_app_name: str
    entry_point: str
    step_number: int
    max_steps: int
    elapsed_seconds: int
    timeout_seconds: int
    policy: PolicyConfig
    input_specs: list[InputSpec] = field(default_factory=list)
    recent_history: list[str] = field(default_factory=list)
    feedback: str | None = None


class ModelAdapter(Protocol):
    name: str

    async def next_action(self, observation: Observation, context: TurnContext) -> DiscoveryAction: ...
