"""Bounded, explicit recovery execution. Never an open-ended agent loop."""

from __future__ import annotations

import asyncio

from ..models.artifact import ErrorRule
from ..surfaces.base import ExecutableAction, SurfaceAdapter


async def perform_recovery(surface: SurfaceAdapter, rule: ErrorRule) -> list[str]:
    """Execute the rule's recovery actions once; returns human-readable notes."""
    notes: list[str] = []
    for action in rule.recovery:
        if action.kind == "dismiss":
            result = await surface.execute(ExecutableAction(kind="click", target=action.target, timeout_ms=3000))
            notes.append(f"dismiss -> {'ok' if result.ok else result.error_code}")
        elif action.kind == "wait":
            await asyncio.sleep((action.wait_ms or 0) / 1000)
            notes.append(f"waited {action.wait_ms}ms")
        elif action.kind == "reload":
            result = await surface.execute(ExecutableAction(kind="navigate", url=surface.current_url()))
            notes.append(f"reload -> {'ok' if result.ok else result.error_code}")
    return notes
