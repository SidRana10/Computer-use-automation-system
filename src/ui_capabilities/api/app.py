"""In-process FastAPI app assembling the capability API, the thin chatbot,
and the dashboard over the existing deterministic replay path.

One process, one event loop, one Playwright execution path (`api/runner.py`).
No queues, brokers, containers, or additional services — consistent with
CLAUDE.md's "no unnecessary microservices," which explicitly names these
three routers as in-process FastAPI routers sharing the automation's event
loop.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from ..config import Settings
from .catalog import CapabilityCatalog
from .routes import build_api_router
from .run_store import RunStore
from .runner import CapabilityRunner
from .service import CapabilityService


def build_app(service: CapabilityService) -> FastAPI:
    """Wire the three routers over an already-constructed `CapabilityService`.

    Split from `create_app` so tests can pass a service backed by a fake
    runner (no Playwright, no live MERIDIAN traffic) while exercising the
    exact same route wiring, request validation, and response shapes a real
    deployment uses.
    """
    # Imported here (not at module top) so importing `api.app` never drags in
    # the chatbot/dashboard packages as a side effect of importing the API
    # alone — each stays independently importable and testable.
    from ..chatbot.router import build_chatbot_router
    from ..dashboard.router import build_dashboard_router

    app = FastAPI(
        title="MERIDIAN Capability API",
        description="Typed capability catalog and deterministic replay invocation over MERIDIAN CORE.",
    )
    app.state.service = service

    app.include_router(build_api_router(service))
    app.include_router(build_chatbot_router(service))
    app.include_router(build_dashboard_router(service))

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard")

    return app


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    catalog = CapabilityCatalog(settings.artifact_dir / "meridian")
    runner = CapabilityRunner(settings)
    run_store = RunStore(settings.evidence_dir)
    service = CapabilityService(catalog, runner, run_store)
    return build_app(service)


app = create_app()
