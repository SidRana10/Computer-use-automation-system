from __future__ import annotations

import threading
import time
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
import uvicorn

from ui_capabilities.config import Settings
from ui_capabilities.observability.evidence import EvidenceManager
from ui_capabilities.observability.logger import RunLogger
from ui_capabilities.policy.config import default_demo_policy
from ui_capabilities.policy.engine import PolicyEngine
from ui_capabilities.policy.redaction import Redactor
from ui_capabilities.surfaces.playwright_web import PlaywrightWebSurface

DEMO_PORT = 8031
DEMO_BASE = f"http://127.0.0.1:{DEMO_PORT}"


@pytest.fixture(scope="session")
def demo_server():
    from demo_app.app import app

    config = uvicorn.Config(app, host="127.0.0.1", port=DEMO_PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{DEMO_BASE}/", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("demo app did not start")
    yield DEMO_BASE
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def demo_state(demo_server):
    from demo_app.state import STATE

    STATE.reset()
    yield STATE
    STATE.reset()


@dataclass
class Harness:
    settings: Settings
    evidence: EvidenceManager
    redactor: Redactor
    logger: RunLogger
    policy: PolicyEngine
    surface: PlaywrightWebSurface


@pytest.fixture
def harness(tmp_path, demo_server) -> Harness:
    settings = Settings(
        playwright_headless=True,
        evidence_dir=tmp_path / "evidence",
        artifact_dir=tmp_path / "artifacts",
        default_step_timeout_ms=4000,
    )
    run_id = f"test-{uuid.uuid4().hex[:8]}"
    evidence = EvidenceManager(settings.evidence_dir, run_id)
    redactor = Redactor()
    logger = RunLogger(evidence.log_path, redactor, run_id)
    policy = PolicyEngine(default_demo_policy(demo_server))
    surface = PlaywrightWebSurface(settings, evidence, headless=True)
    return Harness(settings, evidence, redactor, logger, policy, surface)


@pytest.fixture
def replay_engine(harness):
    from ui_capabilities.replay.engine import ReplayEngine

    def _make(handoff=None) -> "ReplayEngine":
        return ReplayEngine(
            surface=harness.surface,
            global_policy=harness.policy,
            settings=harness.settings,
            logger=harness.logger,
            evidence=harness.evidence,
            redactor=harness.redactor,
            handoff=handoff,
        )

    yield _make


@pytest.fixture
async def cleanup_surface(harness):
    yield
    try:
        await harness.surface.close()
    except Exception:
        pass
