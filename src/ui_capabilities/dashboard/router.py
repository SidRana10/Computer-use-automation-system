"""Read-only dashboard: capability catalog, run history, run detail
(inputs/outputs/steps/evidence). No invoke form, no browser-control endpoint,
no way to bypass policy — invocation happens through the capability API or
the chatbot; this only ever reads what `CapabilityService` already exposes.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..api.catalog import CapabilityNotFoundError
from ..api.run_store import RunNotFoundError
from ..api.service import CapabilityService

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def build_dashboard_router(service: CapabilityService) -> APIRouter:
    router = APIRouter(prefix="/dashboard", tags=["dashboard"])

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return _TEMPLATES.TemplateResponse(request, "catalog.html", {"capabilities": service.list_capabilities()})

    @router.get("/capabilities/{capability_id}", response_class=HTMLResponse)
    async def capability_detail(request: Request, capability_id: str):
        try:
            detail = service.get_capability(capability_id)
        except CapabilityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _TEMPLATES.TemplateResponse(request, "capability_detail.html", {"capability": detail})

    @router.get("/runs", response_class=HTMLResponse)
    async def run_history(request: Request):
        return _TEMPLATES.TemplateResponse(request, "runs.html", {"runs": service.list_runs()})

    @router.get("/runs/{run_id}", response_class=HTMLResponse)
    async def run_detail(request: Request, run_id: str):
        try:
            detail = service.get_run(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _TEMPLATES.TemplateResponse(request, "run_detail.html", {"run": detail})

    return router
