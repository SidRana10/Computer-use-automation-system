"""The capability API: list capabilities, inspect one, invoke one, look up a
run. `build_api_router` takes a `CapabilityService` and closes over it —
the same factory shape `handoff.operator_app.create_operator_app` already
uses for its manager — so nothing here constructs its own catalog/runner.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .catalog import CapabilityNotFoundError
from .run_store import RunNotFoundError
from .schemas import CapabilityDetail, CapabilitySummary, InvokeRequest, RunDetail, RunSummary
from .service import CapabilityService, InvalidArgumentsError
from ..models.results import RunResult


def build_api_router(service: CapabilityService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["capability-api"])

    @router.get("/capabilities", response_model=list[CapabilitySummary])
    async def list_capabilities() -> list[CapabilitySummary]:
        return service.list_capabilities()

    @router.get("/capabilities/{capability_id}", response_model=CapabilityDetail)
    async def get_capability(capability_id: str) -> CapabilityDetail:
        try:
            return service.get_capability(capability_id)
        except CapabilityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/capabilities/{capability_id}/invoke", response_model=RunResult)
    async def invoke_capability(capability_id: str, request: InvokeRequest) -> RunResult:
        try:
            return await service.invoke(capability_id, request.inputs)
        except CapabilityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidArgumentsError as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc

    @router.get("/runs", response_model=list[RunSummary])
    async def list_runs() -> list[RunSummary]:
        return service.list_runs()

    @router.get("/runs/{run_id}", response_model=RunDetail)
    async def get_run(run_id: str) -> RunDetail:
        try:
            return service.get_run(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/runs/{run_id}/evidence/{relative_path:path}")
    async def get_run_evidence(run_id: str, relative_path: str) -> FileResponse:
        try:
            service.get_run(run_id)  # 404s cleanly if the run itself is unknown
            path = service.run_store.evidence_file_path(run_id, relative_path)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        # DOM snapshots are redacted HTML captures for evidence review, not
        # pages to render/execute in the dashboard's own browser context;
        # serve them as text so the viewer never re-runs their scripts/styles.
        media_type = "text/plain" if path.suffix == ".html" else None
        return FileResponse(path, media_type=media_type)

    return router
