# Project Instructions for Claude Code

You are building the interface.ai engineering take-home described in `reference/ORIGINAL_ASSIGNMENT.txt`.

## Mission

Build a small, real, end-to-end system where:

1. an LLM discovers how to complete a natural-language goal on a live UI,
2. the successful run is compiled into a typed/versioned reusable capability artifact,
3. that artifact replays deterministically without an LLM in the decision loop,
4. replay deliberately handles business outcomes, recoverable runtime conditions, and hard failures,
5. all actions pass through configurable safety/policy guardrails,
6. the system can pause and transfer control of the same live browser session to a human, then resume,
7. runs produce structured, redacted evidence.

The core mental model is: **model discovers; artifact is the capability; deterministic replay is production execution.**

## Priority order

When trade-offs are required, optimize in this order:

1. Artifact schema and capability contract quality.
2. Deterministic replay correctness and runtime-error handling.
3. Human handoff/control-transfer model.
4. Safety/privacy and evidence.
5. Genuine LLM discovery loop.
6. Surface abstraction and credible multi-tenant/heterogeneity design.
7. Tests, readability, reproducibility.
8. UI polish only after everything above is complete.

Do not add infrastructure for appearance. No Kafka, Kubernetes, Redis, Celery, distributed queues, or unnecessary microservices.

## Required architecture decisions

Use the detailed specifications in `docs/`. Treat them as the implementation contract unless a concrete technical impossibility is discovered. If you need to deviate, document the reason in `DECISIONS.md` and keep the assignment requirements satisfied.

Mandatory stack:

- Python 3.12
- async Playwright
- Anthropic Python SDK / Messages API
- default runtime discovery model from env: `DISCOVERY_MODEL=claude-fable-5`
- Pydantic v2
- FastAPI + Jinja2 for local target app and minimal operator console
- pytest + pytest-asyncio
- JSON for capability artifacts
- JSONL for structured logs

## Non-negotiable behaviors

### Discovery
- Must perform at least one genuine API-backed LLM-driven run against the live local target UI.
- The LLM must receive a real observation of current UI state. Use a screenshot plus a compact semantic element inventory/current URL/title/visible text summary.
- The LLM chooses from a strict structured action schema. Never execute arbitrary model-generated code or JavaScript.
- Every proposed action passes through the PolicyEngine before SurfaceAdapter execution.
- Bound the loop by max steps, wall-clock timeout, repeated-state/action detection, and policy failures.
- Keep the raw transcript/evidence separate from the reusable artifact.

### Artifact
- Never save a raw discovery transcript as the capability.
- Compile/normalize the successful run into the schema in `docs/03_ARTIFACT_SCHEMA.md`.
- Inputs must be parameterized; use explicit discovery invocation bindings when provided so the compiler can replace concrete values deterministically; do not persist invocation secrets or PII.
- Targeting must store an ordered strategy chain, not only x/y coordinates.
- Artifact must include contract, steps, outputs, success/checkpoint conditions, risk/policy metadata, provenance, versioning, and target-app compatibility metadata.

### Replay
- Zero LLM decision calls during ordinary replay.
- Replay interprets the saved artifact through the SurfaceAdapter.
- It verifies preconditions/checkpoints/postconditions.
- It returns one structured result contract: success, business_outcome, failure, or escalated.
- It handles known runtime conditions explicitly and records retries/recoveries.

### Safety/privacy
- Policy checks occur before execution in both discovery and replay.
- Enforce allowed domains/routes, action kinds, and risk limits.
- Risky/irreversible actions require human approval in the demo design.
- Never store API keys, credentials, tokens, full synthetic-member sensitive values, or typed field contents in logs/artifacts.
- Redact sensitive inputs and human typing from logs.
- `.env` must be gitignored. Provide `.env.example` only.

### Handoff
- Pause automation without closing the Playwright browser/context/page.
- Track control owner explicitly: AUTOMATION, PAUSED, HUMAN.
- Create an intervention record with run/capability/step/reason/screenshot/context.
- Minimal operator UI must allow Take Control, Resume, Abort.
- Human operates the same headed browser window.
- Capture human interaction evidence at least as redacted click/change/navigation events plus before/after snapshots.
- On resume, re-observe and validate a checkpoint before continuing.

### Evidence
- Produce deterministic paths and structured logs.
- Capture screenshot on failure; use Playwright tracing for at least discovery and replay if practical.
- Evidence files must not contain secrets or raw sensitive typed values.

## Engineering rules

- Type public interfaces.
- Prefer small modules with explicit responsibilities.
- No bare `except:`.
- No swallowed errors.
- Centralize timeouts/retry policy/config.
- Centralize redaction.
- Centralize policy enforcement.
- Do not duplicate selector-resolution logic between discovery and replay.
- Use stable semantic locators in this priority: role+accessible name, label, placeholder, exact text, stable attributes/CSS; coordinates are discovery-only fallback/hint, not the normal replay identity.
- Avoid brittle `nth-child`/absolute XPath unless explicitly marked as last-resort and documented.
- Keep synthetic target data obviously fictional.
- Tests must cover schema validation, parameter binding, locator strategy resolution where practical, policy rejection, redaction, error classification, result contracts, and at least one end-to-end deterministic replay.

## Phase 2 — MERIDIAN CORE adaptation (supersedes where noted)

Phase 2 adapts this system to a second, remote target: **MERIDIAN CORE**
(`https://web-sample.interface-hiring.com`), a legacy credit-union servicing UI.
It is an adaptation of the existing core, not a rebuild. The product spec is
`phase2_build_pack/03_PHASE2_REQUIREMENTS.md`; the workflow is
`phase2_build_pack/04_IMPLEMENTATION_WORKFLOW.md`.

The following Phase-1 instructions are amended for Phase 2:

- **Target app.** "FastAPI + Jinja2 for local target app" described the Phase-1
  target. In Phase 2 the target is the remote MERIDIAN application; the local
  `demo_app/` (Northstar) is retained unchanged as the **regression target**.
  Both are reached through the same `SurfaceAdapter`, selected by a target
  profile. Northstar behavior and its tests must keep passing.
- **Discovery model.** `DISCOVERY_MODEL=claude-fable-5` remains the Anthropic
  setting; per D013 the default runtime provider is Gemini (`LLM_PROVIDER`).
  Unchanged by Phase 2.
- **"No unnecessary microservices."** Phase 2 requires a capability API, a thin
  chatbot, and a dashboard. These are in-process FastAPI routers sharing one
  event loop with the automation — no queues, brokers, containers, or new
  services. The rule still forbids infrastructure added for appearance.
- **REPORT.md.** The seven-heading structure is a Phase-1 deliverable and stays
  exactly as it is. The Phase-2 write-up is a separate file, `REPORT_PHASE2.md`,
  covering the twelve points in `phase2_build_pack/07_DEMO_AND_DELIVERABLES.md`.
- **Definition of done.** The Phase-1 definition of done is now the regression
  baseline. Phase-2 completion is governed by
  `phase2_build_pack/08_DEFINITION_OF_DONE.md`.

Phase-2 non-negotiables, in addition to all Phase-1 ones:

- Escalation stays a policy/handoff outcome. The error taxonomy remains exactly
  three-way (`business_outcome`, `recoverable`, `hard_failure`).
- After an irreversible POST has been dispatched and its outcome is uncertain,
  automation must never automatically repeat it. It may re-observe, verify,
  stop, or escalate.
- Runtime values may be referenced by parameterized locators at replay time but
  must never be persisted into artifacts or evidence.
- The capability API, chatbot, and dashboard must not become paths around the
  PolicyEngine, redaction, evidence, or handoff.
- Every core change must be justified by a concrete MERIDIAN requirement and
  must preserve Northstar behavior.

## Working method

Before coding:
1. Read `reference/ORIGINAL_ASSIGNMENT.txt` completely.
2. Read all files under `docs/`.
3. Read `prompts/00_MASTER_BUILD_PROMPT.md`.
4. Build a requirement traceability checklist from `docs/01_REQUIREMENTS_TRACEABILITY.md`.
5. Inspect the current repo before modifying it.
6. Create/update `BUILD_STATUS.md` with milestones and acceptance checks.

During coding:
- Work milestone by milestone.
- Run tests after each meaningful milestone.
- Keep `BUILD_STATUS.md` current.
- Use custom subagents in `.claude/agents/` for architecture, requirements, security, and tests when useful.
- Do not declare completion while any MUST requirement is unimplemented or only described.

Before completion:
- Execute the audit in `prompts/02_FINAL_AUDIT_PROMPT.md`.
- Ensure README and REPORT are based on actual implemented behavior, not aspirational claims.
- Ensure `REPORT.md` has exactly these seven headings:
  1. Architecture
  2. Artifact schema
  3. Determinism & error handling
  4. Heterogeneity & multi-tenant
  5. Escalation & handoff
  6. Safety
  7. Cuts
- Keep REPORT approximately 1–3 pages of substantive prose.
- Ensure repository can run in a mock/no-live-LLM mode for tests, while the evidence includes at least one real discovery run.

## Definition of done

Do not say the project is done until all of these are true:

- local target app runs,
- discovery loop works with real Claude API access,
- successful discovery emits a valid artifact,
- replay uses the artifact without an LLM and returns outputs,
- a known business outcome is demonstrated,
- a recoverable condition is tested/demonstrated,
- a hard failure captures evidence,
- safety allowlist blocks a forbidden action/domain,
- risky action can route to human handoff,
- same-session human takeover/resume works,
- human action evidence is captured/redacted,
- core unit/integration tests pass,
- required README/REPORT/evidence paths exist,
- secrets are absent from git-tracked files,
- final requirement audit passes.
