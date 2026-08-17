"""Unit-test fakes. FakeSurface simulates just enough of the SurfaceAdapter
contract for classifier/handoff tests without a browser."""

from __future__ import annotations

from pathlib import Path

from urllib.parse import urlparse

from ui_capabilities.models.conditions import ConditionKind, ConditionResult, ConditionSpec
from ui_capabilities.surfaces.base import ActionResult, ExecutableAction, Observation


class FakeSurface:
    def __init__(self, tmp_dir: Path, page_text: str = "", url: str = "http://127.0.0.1:8001/"):
        self.tmp_dir = Path(tmp_dir)
        self.page_text = page_text
        self.url = url
        self.human_capture = False
        self.human_events: list[dict] = []
        self.executed: list[ExecutableAction] = []
        # simulate a server-side redirect: requested URL -> landed URL
        self.redirects: dict[str, str] = {}

    def current_url(self) -> str:
        return self.url

    async def start(self, entry_point: str) -> None:
        self.url = entry_point

    async def observe(self, label: str = "observe") -> Observation:
        parsed = urlparse(self.url)
        return Observation(
            url=self.url,
            path=parsed.path or "/",
            title="Fake Page",
            visible_text_summary=self.page_text,
            elements=[],
            fingerprint="fake",
        )

    async def start_trace(self) -> None:
        pass

    async def stop_trace(self) -> Path | None:
        return None

    async def close(self) -> None:
        pass

    async def execute(self, action: ExecutableAction) -> ActionResult:
        self.executed.append(action)
        if action.kind == "navigate" and action.url:
            self.url = self.redirects.get(action.url, action.url)
        return ActionResult(ok=True)

    async def evaluate_condition(self, condition: ConditionSpec) -> ConditionResult:
        if condition.kind == ConditionKind.TEXT_PRESENT:
            return ConditionResult(satisfied=(condition.value or "") in self.page_text, kind=condition.kind)
        if condition.kind == ConditionKind.TEXT_ABSENT:
            return ConditionResult(satisfied=(condition.value or "") not in self.page_text, kind=condition.kind)
        if condition.kind == ConditionKind.URL_MATCHES:
            return ConditionResult(satisfied=(condition.value or "") in self.url, kind=condition.kind)
        return ConditionResult(satisfied=False, kind=condition.kind, detail="unsupported in fake")

    async def capture_screenshot(self, label: str) -> Path:
        path = self.tmp_dir / f"{label}.png"
        path.write_bytes(b"fake-png")
        return path

    async def set_human_capture(self, enabled: bool) -> None:
        self.human_capture = enabled

    async def collect_human_events(self) -> list[dict]:
        events, self.human_events = self.human_events, []
        return events
