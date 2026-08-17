# 02 — Architecture Blueprint

## Core concept

Treat the system as a compiler/runtime for UI capabilities:

- **Discovery is compilation:** goal + live UI + LLM decisions -> normalized capability artifact.
- **Replay is runtime:** artifact + invocation inputs -> deterministic UI execution -> structured result.

## Recommended process boundaries

Keep the submission local-first and simple:

1. **Target App** — FastAPI/Jinja synthetic legacy credit-union app.
2. **Automation Core** — Python package containing discovery, compiler, replay, policies, surfaces, logging.
3. **Operator Console** — small FastAPI/Jinja control surface sharing the Automation Core run/intervention store.

They may run in one Python process with multiple routes/services or as two local processes. Prefer whatever makes same-session browser handoff easiest. Do not add distributed infrastructure.

## Component diagram

```text
CLI / optional local API
        |
        v
RunOrchestrator
   |                  \
   | discovery         \ replay
   v                    v
DiscoveryAgent       ReplayEngine
   |                    |
   +---------+----------+
             v
         PolicyEngine
             |
             v
       SurfaceAdapter
             |
             v
   PlaywrightWebSurface
             |
             v
       Target live UI

DiscoveryAgent -> RunRecorder -> ArtifactCompiler -> CapabilityStore(JSON)

Any block/risk/failure -> HandoffManager -> InterventionStore -> Operator Console
                                       \-> same live Playwright session

All components -> RunLogger / EvidenceManager -> JSONL, screenshots, traces
```

## Suggested package structure Claude should create

```text
.
├── README.md
├── REPORT.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── Makefile                     # optional but useful
├── artifacts/
│   └── .gitkeep
├── evidence/
│   └── .gitkeep
├── src/
│   └── ui_capabilities/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── models/
│       │   ├── actions.py
│       │   ├── artifact.py
│       │   ├── conditions.py
│       │   ├── errors.py
│       │   ├── results.py
│       │   └── intervention.py
│       ├── discovery/
│       │   ├── agent.py
│       │   ├── anthropic_client.py
│       │   ├── prompts.py
│       │   ├── recorder.py
│       │   └── compiler.py
│       ├── replay/
│       │   ├── engine.py
│       │   ├── binder.py
│       │   ├── error_classifier.py
│       │   ├── recovery.py
│       │   └── conditions.py
│       ├── surfaces/
│       │   ├── base.py
│       │   ├── playwright_web.py
│       │   ├── locator_resolver.py
│       │   └── observation.py
│       ├── policy/
│       │   ├── engine.py
│       │   ├── config.py
│       │   └── redaction.py
│       ├── handoff/
│       │   ├── manager.py
│       │   ├── store.py
│       │   └── operator_app.py
│       └── observability/
│           ├── logger.py
│           └── evidence.py
├── demo_app/
│   ├── app.py
│   ├── data.py
│   ├── state.py
│   ├── templates/
│   └── static/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── scripts/
    ├── run_demo.sh
    └── clean_evidence.sh
```

Exact filenames may vary, but preserve these responsibilities and boundaries.

## Key interfaces

### SurfaceAdapter

Surface-independent contract, approximately:

```python
class SurfaceAdapter(Protocol):
    async def start(self, entry_point: str) -> None: ...
    async def observe(self) -> Observation: ...
    async def execute(self, action: ExecutableAction) -> ActionResult: ...
    async def resolve_target(self, target: TargetDescriptor) -> ResolvedTarget: ...
    async def evaluate_condition(self, condition: ConditionSpec) -> ConditionResult: ...
    async def capture_screenshot(self, label: str) -> Path: ...
    async def start_trace(self, run_id: str) -> None: ...
    async def stop_trace(self, path: Path) -> None: ...
    async def close(self) -> None: ...
```

The rest of the system should not depend directly on `playwright.async_api.Page` except inside the web adapter/handoff plumbing.

### PolicyEngine

```python
check(action, current_surface_state, capability_policy) -> PolicyDecision
```

Every action passes through it in discovery and replay.

### ArtifactCompiler

```python
compile(successful_run: RecordedRun) -> CapabilityArtifact
```

It normalizes concrete discovery values to declared inputs, retains stable target descriptors, removes raw reasoning/PII, and validates the artifact.

### ReplayEngine

```python
replay(artifact: CapabilityArtifact, inputs: dict) -> RunResult
```

Must not receive an LLM client dependency.

### HandoffManager

```python
request_intervention(...)
pause(run_id)
take_control(intervention_id, operator_id)
resume(intervention_id)
abort(intervention_id)
```

## State models

### Run mode
- DISCOVERY
- REPLAY

### Control owner
- AUTOMATION
- PAUSED
- HUMAN

### Run state
- CREATED
- RUNNING
- WAITING_FOR_HUMAN
- COMPLETED
- FAILED
- ABORTED

State transitions must be explicit and testable.

## Configuration

Environment/config fields should include at least:

```text
ANTHROPIC_API_KEY=
DISCOVERY_MODEL=claude-fable-5
TARGET_BASE_URL=http://127.0.0.1:8001
OPERATOR_BASE_URL=http://127.0.0.1:8002
PLAYWRIGHT_HEADLESS=false
MAX_DISCOVERY_STEPS=20
DISCOVERY_TIMEOUT_SECONDS=180
DEFAULT_STEP_TIMEOUT_MS=5000
MAX_RECOVERY_ATTEMPTS=2
EVIDENCE_DIR=evidence
ARTIFACT_DIR=artifacts
LOG_LEVEL=INFO
```

Never put a real key in tracked files.
