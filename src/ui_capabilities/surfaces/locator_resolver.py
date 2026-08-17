"""Ordered locator-strategy resolution — the single place selector resolution
happens for durable targets.

Strategies are tried in artifact order; ambiguity is rejected, never silently
resolved to the first match. The matched strategy is reported so replay
telemetry can observe fallback usage (a drift signal).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Literal

from playwright.async_api import Locator, Page

from ..models.targets import LocatorKind, LocatorStrategy, TargetDescriptor


@dataclass
class ResolutionOutcome:
    status: Literal["resolved", "not_found", "ambiguous"]
    locator: Locator | None = None
    matched_strategy: LocatorStrategy | None = None
    detail: str = ""


def _css_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_locator(page: Page, strategy: LocatorStrategy) -> Locator | None:
    if strategy.kind == LocatorKind.ROLE_NAME:
        if not strategy.role:
            return None
        return page.get_by_role(strategy.role, name=strategy.name, exact=strategy.exact)  # type: ignore[arg-type]
    if strategy.kind == LocatorKind.LABEL:
        return page.get_by_label(strategy.value or "", exact=strategy.exact)
    if strategy.kind == LocatorKind.PLACEHOLDER:
        return page.get_by_placeholder(strategy.value or "", exact=strategy.exact)
    if strategy.kind == LocatorKind.TEXT:
        return page.get_by_text(strategy.value or "", exact=strategy.exact)
    if strategy.kind == LocatorKind.STABLE_ATTRIBUTE:
        if not strategy.attribute or strategy.value is None:
            return None
        return page.locator(f'[{strategy.attribute}="{_css_escape(strategy.value)}"]')
    if strategy.kind == LocatorKind.CSS:
        return page.locator(strategy.value or "")
    # frame_path is a schema extension point; the demo app has no frames.
    return None


async def resolve_target(
    page: Page,
    target: TargetDescriptor,
    timeout_ms: int,
    poll_interval_ms: int = 200,
) -> ResolutionOutcome:
    """Try each strategy in order until exactly one element matches; poll
    within the timeout to absorb harmless async rendering delay."""
    deadline = time.monotonic() + timeout_ms / 1000
    saw_ambiguous: str | None = None
    while True:
        for strategy in target.strategies:
            locator = build_locator(page, strategy)
            if locator is None:
                continue
            try:
                count = await locator.count()
            except Exception as exc:  # invalid selector etc. — try next strategy
                saw_ambiguous = saw_ambiguous or f"strategy {strategy.kind} errored: {exc}"
                continue
            if count == 1:
                return ResolutionOutcome(status="resolved", locator=locator, matched_strategy=strategy)
            if count > 1:
                saw_ambiguous = f"strategy {strategy.kind} matched {count} elements"
                continue
        if time.monotonic() >= deadline:
            break
        await asyncio.sleep(poll_interval_ms / 1000)
    if saw_ambiguous:
        return ResolutionOutcome(status="ambiguous", detail=saw_ambiguous)
    return ResolutionOutcome(
        status="not_found",
        detail=f"no strategy of {[s.kind.value for s in target.strategies]} matched within {timeout_ms}ms",
    )
