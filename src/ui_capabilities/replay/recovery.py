"""Bounded, explicit recovery execution. Never an open-ended agent loop.

Recovery touches the live surface, so it crosses the same authorization
boundary as every other action: each surface-executing recovery step is
checked by the PolicyEngine before execution, using the same
`check_action` seam the discovery agent and replay engine use. A denial stops
recovery immediately and is reported to the caller — recovery never has a
weaker path to the surface than an ordinary step.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from ..models.artifact import ErrorRule
from ..policy.engine import PolicyDecision, PolicyEngine
from ..surfaces.base import ExecutableAction, SurfaceAdapter


@dataclass
class RecoveryOutcome:
    """Result of one bounded recovery attempt."""

    notes: list[str] = field(default_factory=list)
    denial: PolicyDecision | None = None
    denied_action: str | None = None

    @property
    def denied(self) -> bool:
        return self.denial is not None


async def perform_recovery(surface: SurfaceAdapter, rule: ErrorRule, policy: PolicyEngine) -> RecoveryOutcome:
    """Execute the rule's recovery actions once, policy-checking each surface
    action first. Stops at the first denial without touching the surface."""
    outcome = RecoveryOutcome()
    for action in rule.recovery:
        if action.kind == "dismiss":
            control_text = action.target.description if action.target else None
            decision = policy.check_action("click", control_text=control_text)
            if not decision.allowed:
                outcome.denial = decision
                outcome.denied_action = "dismiss"
                return outcome
            result = await surface.execute(ExecutableAction(kind="click", target=action.target, timeout_ms=3000))
            outcome.notes.append(f"dismiss -> {'ok' if result.ok else result.error_code}")
        elif action.kind == "wait":
            # pure delay: never reaches the surface, so there is nothing to authorize
            await asyncio.sleep((action.wait_ms or 0) / 1000)
            outcome.notes.append(f"waited {action.wait_ms}ms")
        elif action.kind == "reload":
            url = surface.current_url()
            decision = policy.check_action("navigate", url=url)
            if not decision.allowed:
                outcome.denial = decision
                outcome.denied_action = "reload"
                return outcome
            result = await surface.execute(ExecutableAction(kind="navigate", url=url))
            outcome.notes.append(f"reload -> {'ok' if result.ok else result.error_code}")
    return outcome
