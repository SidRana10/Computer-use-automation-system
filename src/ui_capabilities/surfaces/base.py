"""Surface-independent contract: how the system perceives and acts on a UI.

This seam is what would let the recorded-flow layer extend to legacy web,
desktop/accessibility, or vision surfaces without touching discovery, the
artifact schema, or the replay engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from ..models.conditions import ConditionResult, ConditionSpec
from ..models.targets import LocatorStrategy, TargetDescriptor


class ObservedElement(BaseModel):
    ref: str  # ephemeral, valid only for the observation that produced it
    kind: str  # link | button | textbox | combobox | cell | checkbox | ...
    tag: str
    accessible_name: str | None = None
    label: str | None = None
    placeholder: str | None = None
    text: str | None = None
    name_attr: str | None = None
    id_attr: str | None = None
    options: list[str] = []
    candidate_strategies: list[LocatorStrategy] = []


class Observation(BaseModel):
    url: str
    path: str
    title: str
    heading: str | None = None  # first content heading; a stable page marker
    visible_text_summary: str
    elements: list[ObservedElement]
    screenshot_path: str | None = None
    fingerprint: str


class ExecutableAction(BaseModel):
    """The uniform action the surface executes. Discovery addresses elements
    by ephemeral observation ref; replay addresses them by durable
    TargetDescriptor. Target resolution logic lives once, in the resolver."""

    kind: Literal["navigate", "click", "fill", "select", "extract", "wait"]
    url: str | None = None
    element_ref: str | None = None
    target: TargetDescriptor | None = None
    value: str | None = None
    wait_ms: int | None = None
    timeout_ms: int | None = None


class ActionResult(BaseModel):
    ok: bool
    error_code: str | None = None  # TARGET_NOT_FOUND | AMBIGUOUS_TARGET | TIMEOUT | EXECUTION_ERROR
    message: str = ""
    extracted_text: str | None = None
    matched_strategy: LocatorStrategy | None = None
    duration_ms: int = 0


class SurfaceAdapter(Protocol):
    async def start(self, entry_point: str) -> None: ...

    async def observe(self, label: str = "observe") -> Observation: ...

    async def execute(self, action: ExecutableAction) -> ActionResult: ...

    async def evaluate_condition(self, condition: ConditionSpec) -> ConditionResult: ...

    async def capture_screenshot(self, label: str) -> Path: ...

    async def start_trace(self) -> None: ...

    async def stop_trace(self) -> Path | None: ...

    async def close(self) -> None: ...

    def current_url(self) -> str: ...


# Narrow escape hatch used only by handoff plumbing (human-mode capture works
# on the live page object); typed as Any to keep Playwright out of the seam.
SurfaceHandle = Any
