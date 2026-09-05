> **Phase 1 historical.** This file drove the original Northstar build. Phase 2 (MERIDIAN CORE) is governed by `phase2_build_pack/`. Kept for provenance; not a current instruction.

Build this project completely from the repository specification already present here.

Start by reading, in full:
- `CLAUDE.md`
- `reference/ORIGINAL_ASSIGNMENT.txt`
- every file in `docs/`
- `reference/ANTHROPIC_IMPLEMENTATION_NOTES.md`
- `BUILD_STATUS.md`
- `DECISIONS.md`

Do not ask me to choose the architecture, framework, target site, schema direction, error taxonomy, or handoff approach: those decisions have already been made in these files. If a minor implementation detail is unspecified, make the simplest defensible decision consistent with the assignment and record only meaningful deviations in `DECISIONS.md`.

Your job is to produce the actual finished take-home repository, not merely a plan or skeleton.

## Operating instructions

1. First inspect the repository and restate to yourself a requirement checklist using `docs/01_REQUIREMENTS_TRACEABILITY.md`.
2. Create/update `BUILD_STATUS.md` and work through milestones M0 → M10 in order.
3. Implement a thin-but-real end-to-end version of every MUST requirement before polishing any individual subsystem.
4. Run tests frequently and fix failures rather than documenting them away.
5. Use the custom reviewers in `.claude/agents/` when useful, especially after core implementation.
6. Do not add unnecessary distributed infrastructure or frontend polish.
7. Do not claim a feature exists unless it works in code.
8. Do not put secrets or sensitive invocation values in source, artifacts, or logs.
9. Do not use a raw model transcript as the capability artifact.
10. Ordinary replay must make zero LLM decisions.

## Required concrete implementation

Build the architecture specified in `docs/02_ARCHITECTURE_BLUEPRINT.md` using:
- Python 3.12
- async Playwright
- Pydantic v2
- Anthropic Python SDK / Messages API
- FastAPI + Jinja2
- pytest + pytest-asyncio
- JSON capability artifacts
- JSONL structured logs

Use `DISCOVERY_MODEL=claude-fable-5` as the default runtime discovery model via environment configuration. Do not hardcode an API key. Follow current Anthropic SDK conventions; do not add obsolete manual thinking configuration. Prefer strict schema-constrained tool inputs/structured outputs for discovery actions; regardless, Pydantic-validate every model-proposed action before execution.

## Build phases

### Phase 1 — repository/config/typed domain models
Create packaging, config, `.env.example`, `.gitignore`, core Pydantic models, enums, result contracts, and the package/module boundaries from the architecture document.

Acceptance:
- package installs/imports,
- pytest runs,
- result/artifact models validate,
- no browser/LLM behavior yet required.

### Phase 2 — synthetic target application
Implement `Northstar Credit Union — Member Servicing Console (Demo)` exactly in spirit of `docs/08_MOCK_APP_SPEC.md`.

It must provide:
- dashboard/member search/member details/accounts balance flow,
- deterministic synthetic fixtures,
- member not found,
- validation rejection,
- permission denial,
- known interstitial and/or transient load,
- deterministic hard-failure injection,
- session-expired state,
- sub-account form → review → final confirmation flow for risky-action handoff.

Keep it obviously fake and local. No real credentials or PII.

Acceptance:
- a person can manually perform the main flows in a browser,
- exceptional states are reproducible rather than random.

### Phase 3 — SurfaceAdapter + Playwright implementation
Implement:
- browser lifecycle,
- current URL/title/visible state,
- screenshot capture,
- compact semantic element inventory with ephemeral refs,
- candidate stable locator strategy generation,
- ordered locator resolver,
- click/fill/select/navigate/extract/wait/assert operations,
- condition evaluation,
- tracing/evidence hooks,
- browser context that stays alive during handoff.

Do not expose arbitrary model-generated JavaScript execution.

Acceptance:
- adapter integration test can navigate/search/read demo app,
- locator resolver uses strategy chain and rejects ambiguity,
- screenshots work.

### Phase 4 — policy, redaction, logging/evidence
Implement central:
- PolicyConfig/PolicyEngine,
- URL/domain/route/action allowlist,
- risk levels and human-required decisions,
- Redactor,
- structured JSONL RunLogger,
- EvidenceManager.

Every action path must call policy before surface execution.

Acceptance:
- off-domain action blocked before browser executes,
- irreversible action requires human,
- sensitive values are redacted in logs/tests.

### Phase 5 — LLM discovery loop
Implement a model adapter interface and an Anthropic implementation.

The genuine model loop must:
- accept goal + target and optional explicit invocation parameter bindings (use `member_id=M-10001` in the demo so parameterization/redaction is deterministic),
- observe screenshot + compact semantic state,
- ask Claude for one strict structured next action,
- Pydantic-validate it,
- policy-check it,
- execute it on the live UI,
- record it,
- repeat until verified done or bounded stopping condition,
- escalate when stuck/unsafe.

Create a deterministic fake model adapter for tests. Do not confuse fake discovery tests with the required real evidence run.

Model action schema must be narrow: navigate/click/fill/select/extract/wait/done/request_human. Never arbitrary shell/code/JS.

The runtime discovery prompt should tell the model the goal, current observation, allowed actions and safety rules, but should not secretly provide the exact hardcoded click path for the real discovery demo.

Acceptance:
- offline scripted discovery integration test works,
- with API key, real Claude can genuinely operate the live demo surface.

### Phase 6 — recorder + artifact compiler
Implement the exact design goals in `docs/03_ARTIFACT_SCHEMA.md`.

Compiler responsibilities:
- normalize successful recorded actions,
- convert ephemeral element refs into durable TargetDescriptors,
- use ordered locator strategy chains,
- parameterize invocation-specific inputs using explicit discovery invocation bindings as the primary mapping,
- declare typed outputs,
- attach conditions/error rules/policy/version/provenance,
- never persist raw sensitive input values,
- fail if it cannot create a valid reusable artifact.

Primary artifact contract:
`member.get_savings_balance(member_id: string) -> savings_balance: decimal`

Acceptance:
- discovery with M-10001 produces an artifact that can later replay M-10003,
- artifact JSON is human-readable and Pydantic-valid,
- no raw transcript/chain-of-thought embedded.

### Phase 7 — deterministic replay engine
Implement artifact interpretation exactly per `docs/05_REPLAY_ERROR_MODEL.md`.

Replay must:
- validate artifact and invocation,
- bind inputs,
- policy-check every step,
- resolve targets by ordered strategies,
- use condition/actionability waits,
- evaluate business/recoverable/hard error rules,
- perform bounded explicit recovery,
- verify checkpoints and final success conditions,
- extract typed outputs,
- return structured Success / BusinessOutcome / Failure / Escalated result.

Prove the replay path does not call the model. Architect it so the replay engine has no LLM-client dependency.

Acceptance:
- valid different member succeeds,
- unknown member returns `MEMBER_NOT_FOUND`, not a crash,
- known interstitial/transient condition recovers and records recovery,
- injected missing control returns hard failure with step/expected/observed/evidence.

### Phase 8 — human escalation and same-session control transfer
Implement `docs/07_HUMAN_HANDOFF.md`.

Must include:
- InterventionRequest,
- control-owner state machine AUTOMATION/PAUSED/HUMAN,
- minimal operator console,
- Take Control/Resume/Abort,
- same Playwright browser/context/page kept alive,
- human uses the existing headed browser,
- safe redacted human click/change/navigation event capture,
- fresh observation/checkpoint validation before automation resumes.

Preferred demo: sub-account final confirmation is marked irreversible → policy requires human → operator takes over same browser → human confirms → operator resumes → automation verifies confirmation.

Acceptance:
- state-machine tests pass,
- manual demo is genuinely possible and documented,
- no simultaneous automation/human control.

### Phase 9 — comprehensive tests
Implement all required tests in `docs/09_TEST_EVIDENCE_PLAN.md`.

Run the entire suite. Fix defects. Do not simply lower assertions to make tests pass.

### Phase 10 — submission docs and evidence tooling
Create the actual required:
- `/README.md`
- `/REPORT.md`
- `/evidence/`

README must contain exact tested commands for setup, target/operator app, genuine discovery, replay, exceptional replay, handoff, and tests.

REPORT must be concise (~1–3 pages) and have exactly these seven top-level headings in this order:
1. Architecture
2. Artifact schema
3. Determinism & error handling
4. Heterogeneity & multi-tenant
5. Escalation & handoff
6. Safety
7. Cuts

Only claim implemented behavior that is actually implemented. Clearly distinguish design-only desktop/multi-tenant support.

Create scripts/commands to generate the required evidence. If `ANTHROPIC_API_KEY` is available in the environment, perform the genuine discovery run and save sanitized evidence. If it is not available, finish all code/tests/docs/evidence tooling and clearly tell me the single command I need to run after setting the key; do not fabricate a “real” discovery log.

## Final required audit

Before telling me the build is complete:

1. Run full pytest suite.
2. Run formatter/linter/type checks if configured and fix meaningful issues.
3. Run requirement auditor against every assignment MUST.
4. Run security reviewer for keys, PII leakage, policy bypasses, unsafe model actions.
5. Run test reviewer for missing load-bearing tests.
6. Inspect README commands against actual CLI.
7. Inspect REPORT claims against actual code.
8. Search repository for `.env`, API-key patterns, cookies/tokens, and raw sensitive logged values.
9. Confirm ordinary replay has no model decision call.
10. Confirm injected hard failure creates richer evidence.
11. Confirm same-session human handoff is implemented, not a TODO.
12. Update `BUILD_STATUS.md` truthfully.

Do not stop after producing a plan. Proceed to implementation, testing, documentation, and audit. If a tool/API signature has changed, consult official documentation or installed package help and adapt while preserving the architecture and requirements.
