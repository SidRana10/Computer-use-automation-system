"""Playwright implementation of the SurfaceAdapter.

Owns the browser lifecycle, observation, execution, condition evaluation,
tracing, and the same-session handoff plumbing (the browser/context/page stay
alive while a human takes over).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    ElementHandle,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ..config import Settings
from ..models.conditions import ConditionKind, ConditionResult, ConditionSpec
from ..observability.evidence import EvidenceManager
from . import observation as obs
from .base import ActionResult, ExecutableAction, Observation
from .locator_resolver import resolve_target

# Static, trusted human-interaction capture script. Injected at context level
# so it survives same-origin navigation; records safe metadata only, and only
# while human mode is on. Typed values are never captured.
_HUMAN_CAPTURE_JS = """
(() => {
  const MODE_KEY = 'uicap_human_mode';
  const BUF_KEY = 'uicap_human_events';
  const active = () => { try { return sessionStorage.getItem(MODE_KEY) === '1'; } catch (e) { return false; } };
  const push = (ev) => {
    try {
      const buf = JSON.parse(sessionStorage.getItem(BUF_KEY) || '[]');
      if (buf.length < 200) { buf.push(ev); sessionStorage.setItem(BUF_KEY, JSON.stringify(buf)); }
    } catch (e) {}
  };
  if (active()) {
    push({event: 'navigation', url: location.pathname, timestamp: new Date().toISOString()});
  }
  document.addEventListener('click', (e) => {
    if (!active()) return;
    const t = (e.target.closest && e.target.closest('a,button,input,select')) || e.target;
    push({
      event: 'click',
      tag: (t.tagName || '').toLowerCase(),
      text: ((t.innerText || t.value || '') + '').trim().slice(0, 40) || null,
      aria_label: t.getAttribute ? t.getAttribute('aria-label') : null,
      timestamp: new Date().toISOString()
    });
  }, true);
  document.addEventListener('change', (e) => {
    if (!active()) return;
    const t = e.target;
    push({
      event: 'change',
      tag: (t.tagName || '').toLowerCase(),
      name: t.getAttribute ? t.getAttribute('name') : null,
      value_changed: true,
      value: '[REDACTED]',
      timestamp: new Date().toISOString()
    });
  }, true);
})();
"""


class PlaywrightWebSurface:
    def __init__(self, settings: Settings, evidence: EvidenceManager, headless: bool | None = None):
        self.settings = settings
        self.evidence = evidence
        self.headless = settings.playwright_headless if headless is None else headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._ref_handles: dict[str, ElementHandle] = {}
        self._tracing = False

    # ------------------------------------------------------------ lifecycle

    async def start(self, entry_point: str) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(viewport={"width": 1180, "height": 900})
        await self._context.add_init_script(_HUMAN_CAPTURE_JS)
        self._page = await self._context.new_page()
        await self._page.goto(entry_point, wait_until="load")

    async def close(self) -> None:
        if self._tracing:
            try:
                await self.stop_trace()
            except PlaywrightError:
                pass
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("surface not started")
        return self._page

    def current_url(self) -> str:
        return self.page.url

    # ------------------------------------------------------------ observation

    async def observe(self, label: str = "observe") -> Observation:
        page = self.page
        try:
            await page.wait_for_load_state("load", timeout=self.settings.default_step_timeout_ms)
        except PlaywrightTimeoutError:
            pass
        elements, self._ref_handles = await obs.build_inventory(page)
        text_summary = await obs.visible_text_summary(page)
        title = await page.title()
        heading = None
        try:
            h2 = page.locator("h2").first
            if await h2.count() > 0:
                heading = (await h2.inner_text(timeout=1000)).strip() or None
        except PlaywrightError:
            heading = None
        parsed = urlparse(page.url)
        screenshot = await self.capture_screenshot(label)
        return Observation(
            url=page.url,
            path=parsed.path or "/",
            title=title,
            heading=heading,
            visible_text_summary=text_summary,
            elements=elements,
            screenshot_path=str(screenshot),
            fingerprint=obs.observation_fingerprint(parsed.path or "/", title, elements, text_summary),
        )

    async def capture_screenshot(self, label: str) -> Path:
        path = self.evidence.screenshot_path(label)
        await self.page.screenshot(path=str(path))
        return path

    # ------------------------------------------------------------- execution

    async def execute(self, action: ExecutableAction) -> ActionResult:
        started = time.monotonic()
        timeout = action.timeout_ms or self.settings.default_step_timeout_ms

        def _done(**kwargs) -> ActionResult:
            return ActionResult(duration_ms=int((time.monotonic() - started) * 1000), **kwargs)

        try:
            if action.kind == "navigate":
                if not action.url:
                    return _done(ok=False, error_code="EXECUTION_ERROR", message="navigate requires url")
                await self.page.goto(action.url, wait_until="load", timeout=max(timeout, 10_000))
                return _done(ok=True)

            if action.kind == "wait":
                await asyncio.sleep(min(action.wait_ms or 0, self.settings.max_wait_action_ms) / 1000)
                return _done(ok=True)

            matched = None
            if action.element_ref is not None:
                handle = self._ref_handles.get(action.element_ref)
                if handle is None:
                    return _done(ok=False, error_code="TARGET_NOT_FOUND", message=f"unknown element ref {action.element_ref!r} (stale observation?)")
                subject: ElementHandle = handle
            elif action.target is not None:
                outcome = await resolve_target(self.page, action.target, timeout, self.settings.condition_poll_interval_ms)
                if outcome.status == "not_found":
                    return _done(ok=False, error_code="TARGET_NOT_FOUND", message=outcome.detail)
                if outcome.status == "ambiguous":
                    return _done(ok=False, error_code="AMBIGUOUS_TARGET", message=outcome.detail)
                subject = outcome.locator  # type: ignore[assignment]
                matched = outcome.matched_strategy
            else:
                return _done(ok=False, error_code="EXECUTION_ERROR", message=f"{action.kind} requires element_ref or target")

            if action.kind == "click":
                await subject.click(timeout=timeout)
                try:
                    await self.page.wait_for_load_state("load", timeout=timeout)
                except PlaywrightTimeoutError:
                    pass
                return _done(ok=True, matched_strategy=matched)
            if action.kind == "fill":
                await subject.fill(action.value or "", timeout=timeout)
                return _done(ok=True, matched_strategy=matched)
            if action.kind == "select":
                await subject.select_option(label=action.value, timeout=timeout)
                return _done(ok=True, matched_strategy=matched)
            if action.kind == "extract":
                if isinstance(subject, ElementHandle):
                    text = (await subject.inner_text()).strip()
                else:
                    text = (await subject.inner_text(timeout=timeout)).strip()
                return _done(ok=True, extracted_text=text, matched_strategy=matched)
            return _done(ok=False, error_code="EXECUTION_ERROR", message=f"unsupported action kind {action.kind!r}")
        except PlaywrightTimeoutError as exc:
            return _done(ok=False, error_code="TIMEOUT", message=str(exc).splitlines()[0] if str(exc) else "timeout")
        except PlaywrightError as exc:
            return _done(ok=False, error_code="EXECUTION_ERROR", message=str(exc).splitlines()[0] if str(exc) else "error")

    # ------------------------------------------------------------ conditions

    async def evaluate_condition(self, condition: ConditionSpec) -> ConditionResult:
        timeout = condition.timeout_ms or self.settings.default_step_timeout_ms
        deadline = time.monotonic() + timeout / 1000
        detail = ""
        while True:
            satisfied, detail = await self._evaluate_once(condition)
            if satisfied:
                return ConditionResult(satisfied=True, kind=condition.kind, detail=detail)
            if time.monotonic() >= deadline:
                return ConditionResult(satisfied=False, kind=condition.kind, detail=detail)
            await asyncio.sleep(self.settings.condition_poll_interval_ms / 1000)

    async def _evaluate_once(self, condition: ConditionSpec) -> tuple[bool, str]:
        page = self.page
        if condition.kind == ConditionKind.URL_MATCHES:
            pattern = condition.value or ""
            path = urlparse(page.url).path or "/"
            ok = _glob_match(pattern, path) or _glob_match(pattern, page.url)
            return ok, f"url={path}"
        if condition.kind in (ConditionKind.TEXT_PRESENT, ConditionKind.TEXT_ABSENT):
            try:
                body = await page.inner_text("body", timeout=1000)
            except PlaywrightError:
                body = ""
            present = (condition.value or "") in " ".join(body.split())
            if condition.kind == ConditionKind.TEXT_PRESENT:
                return present, "text found" if present else f"text {condition.value!r} not present"
            return not present, "text absent" if not present else f"text {condition.value!r} unexpectedly present"
        # element conditions
        assert condition.target is not None
        outcome = await resolve_target(page, condition.target, timeout_ms=250, poll_interval_ms=100)
        if condition.kind == ConditionKind.ELEMENT_PRESENT:
            return outcome.status == "resolved", outcome.detail or outcome.status
        if condition.kind == ConditionKind.ELEMENT_ABSENT:
            return outcome.status == "not_found", outcome.detail or outcome.status
        if condition.kind == ConditionKind.ELEMENT_VALUE_MATCHES:
            if outcome.status != "resolved" or outcome.locator is None:
                return False, outcome.detail or "target not resolved"
            try:
                value = await outcome.locator.input_value(timeout=500)
            except PlaywrightError:
                try:
                    value = (await outcome.locator.inner_text(timeout=500)).strip()
                except PlaywrightError:
                    return False, "could not read element value"
            ok = re.search(condition.value or "", value) is not None
            return ok, "value matched" if ok else "value did not match"
        return False, f"unknown condition kind {condition.kind}"

    # --------------------------------------------------------------- tracing

    async def start_trace(self) -> None:
        if self._context and not self._tracing:
            await self._context.tracing.start(screenshots=True, snapshots=True)
            self._tracing = True

    async def stop_trace(self) -> Path | None:
        if self._context and self._tracing:
            path = self.evidence.trace_path
            await self._context.tracing.stop(path=str(path))
            self._tracing = False
            return path
        return None

    # ------------------------------------------------- human handoff support

    async def set_human_capture(self, enabled: bool) -> None:
        """Toggle the human-mode flag read by the static init script."""
        value = "1" if enabled else "0"
        await self.page.evaluate(f"sessionStorage.setItem('uicap_human_mode', '{value}')")

    async def collect_human_events(self) -> list[dict]:
        raw = await self.page.evaluate(
            "() => { const v = sessionStorage.getItem('uicap_human_events') || '[]';"
            " sessionStorage.removeItem('uicap_human_events'); return v; }"
        )
        try:
            events = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return []
        return events if isinstance(events, list) else []


def _glob_match(pattern: str, value: str) -> bool:
    """Glob-ish match for url conditions: `*` spans one path segment, `**`
    spans anything; a pattern without a scheme matches on the path."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.match("^" + "".join(out) + r"/?$", value) is not None
