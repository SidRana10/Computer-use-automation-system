"""Minimal operator console: list interventions, show context/screenshot,
Take Control / Resume / Abort. Deliberately unpolished — the control-transfer
model is the point, not the UI."""

from __future__ import annotations

import asyncio
import html
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from .manager import HandoffError, HandoffManager

_PAGE = """<!DOCTYPE html>
<html><head><title>Operator Console</title>
<style>
 body {{ font-family: monospace; margin: 20px; background: #f5f5f0; }}
 .card {{ border: 1px solid #888; background: #fff; padding: 12px; margin-bottom: 12px; max-width: 900px; }}
 .owner {{ font-weight: bold; }}
 img {{ max-width: 640px; border: 1px solid #aaa; }}
 form {{ display: inline; }}
 button {{ margin-right: 8px; }}
</style></head><body>
<h1>Operator Console</h1>
<p>Control owner: <span class="owner">{owner}</span></p>
{body}
</body></html>"""


def create_operator_app(manager: HandoffManager) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        cards = []
        for item in manager.store.all():
            cards.append(
                f"""<div class="card">
                <b>{item.intervention_id}</b> — status: {item.status} — mode: {item.mode.value}<br>
                run: {item.run_id} / capability: {html.escape(str(item.capability_id))}<br>
                step: {html.escape(str(item.step_id))}<br>
                reason: [{html.escape(item.reason_code)}] {html.escape(item.reason_message)}<br>
                goal: {html.escape(item.goal_summary)}<br>
                url: {html.escape(item.current_url)}<br>
                <a href="/interventions/{item.intervention_id}">details</a>
                </div>"""
            )
        body = "\n".join(cards) or "<p>No interventions.</p>"
        return _PAGE.format(owner=manager.control_owner.value, body=body)

    @app.get("/interventions/{intervention_id}", response_class=HTMLResponse)
    async def detail(intervention_id: str):
        item = manager.store.get(intervention_id)
        buttons = []
        if item.status == "open":
            buttons.append(
                f'<form method="post" action="/interventions/{item.intervention_id}/take">'
                '<button type="submit">Take Control</button></form>'
            )
        if item.status == "claimed":
            buttons.append(
                f'<form method="post" action="/interventions/{item.intervention_id}/resume">'
                '<input name="note" placeholder="operator note (optional)">'
                '<button type="submit">Resume Automation</button></form>'
            )
        if item.status in ("open", "claimed"):
            buttons.append(
                f'<form method="post" action="/interventions/{item.intervention_id}/abort">'
                '<button type="submit">Abort</button></form>'
            )
        events = "".join(
            f"<li>{html.escape(e.event)} {html.escape(e.tag or '')} {html.escape(e.text or e.name or '')}"
            f"{' (value_changed)' if e.value_changed else ''}</li>"
            for e in item.human_events
        )
        body = f"""<div class="card">
        <b>{item.intervention_id}</b> — status: {item.status}<br>
        step: {html.escape(str(item.step_id))}<br>
        reason: [{html.escape(item.reason_code)}] {html.escape(item.reason_message)}<br>
        goal: {html.escape(item.goal_summary)}<br>
        url: {html.escape(item.current_url)}<br>
        <p>{''.join(buttons)}</p>
        <p>The live browser window stays open — operate it directly after taking control.</p>
        <p><img src="/interventions/{item.intervention_id}/screenshot" alt="current screenshot"></p>
        <p>Recorded human actions (redacted):</p><ul>{events or '<li>(none yet)</li>'}</ul>
        <p><a href="/">back</a></p>
        </div>"""
        return _PAGE.format(owner=manager.control_owner.value, body=body)

    @app.get("/interventions/{intervention_id}/screenshot")
    async def screenshot(intervention_id: str):
        item = manager.store.get(intervention_id)
        path = item.after_screenshot or item.screenshot_path
        if path and Path(path).exists():
            return FileResponse(path)
        return HTMLResponse("no screenshot", status_code=404)

    @app.post("/interventions/{intervention_id}/take")
    async def take(intervention_id: str):
        try:
            await manager.take_control(intervention_id, operator_id="local-operator")
        except HandoffError as exc:
            return HTMLResponse(f"invalid transition: {html.escape(str(exc))}", status_code=409)
        return RedirectResponse(url=f"/interventions/{intervention_id}", status_code=303)

    @app.post("/interventions/{intervention_id}/resume")
    async def resume(intervention_id: str, note: str = Form("")):
        try:
            await manager.resume(intervention_id, note=note or None)
        except HandoffError as exc:
            return HTMLResponse(f"invalid transition: {html.escape(str(exc))}", status_code=409)
        return RedirectResponse(url=f"/interventions/{intervention_id}", status_code=303)

    @app.post("/interventions/{intervention_id}/abort")
    async def abort(intervention_id: str):
        try:
            await manager.abort(intervention_id)
        except HandoffError as exc:
            return HTMLResponse(f"invalid transition: {html.escape(str(exc))}", status_code=409)
        return RedirectResponse(url=f"/interventions/{intervention_id}", status_code=303)

    return app


class OperatorServer:
    """Runs the operator console on the same event loop as the automation so
    they share the HandoffManager and the live Playwright session."""

    def __init__(self, app: FastAPI, host: str, port: int):
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(config)
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self.server.serve())
        while not self.server.started and not self._task.done():
            await asyncio.sleep(0.05)

    async def stop(self) -> None:
        self.server.should_exit = True
        if self._task:
            await self._task
