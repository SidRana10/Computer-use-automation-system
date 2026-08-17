# Build Status

Claude Code: maintain this file as work progresses. Do not mark a milestone complete until its acceptance checks pass.

## M0 — Requirements and skeleton
- [x] Assignment and docs read
- [x] Traceability matrix copied/updated (docs/01 used as checklist)
- [x] Repo structure created
- [x] Config and `.env.example` created
- [x] Tests can be discovered by pytest

## M1 — Local legacy-style target app
- [x] Search → member detail → accounts → balance flow works manually
- [x] Synthetic member-not-found behavior (`M-40400`)
- [x] Validation rejection behavior (`BAD` → "Member ID must match M-#####.")
- [x] Permission-denied behavior (`M-10002` sub-account flow)
- [x] Transient slow/interstitial behavior (deterministic one-shot flags)
- [x] Session-expired state (deterministic flag)
- [x] Risky create-sub-account review/confirmation flow
- [x] Injected hard-failure mode (`missing_accounts_control`)

## M2 — Surface abstraction + observation
- [x] `SurfaceAdapter` interface exists (`surfaces/base.py`)
- [x] Playwright implementation exists (`surfaces/playwright_web.py`)
- [x] Screenshot observation works
- [x] Semantic element inventory works (ephemeral refs + candidate strategies)
- [x] Stable locator resolver supports ordered strategy chain, rejects ambiguity
- [x] Playwright context remains alive across handoff

## M3 — Policy + redaction + observability
- [x] Domain/port/route allowlist
- [x] Action allowlist
- [x] Risk classification/approval behavior (declared step risk + control-text heuristic)
- [x] Central redactor (keys, secret patterns, registered runtime values)
- [x] Structured JSONL logs (all writes pass through the redactor)
- [x] Failure screenshots
- [x] Tracing/evidence hooks (Playwright tracing per run)

## M4 — LLM discovery
- [x] Provider-pluggable model adapters: Gemini (`GEMINI_MODEL=gemini-3-flash-preview`, default) and Anthropic (`DISCOVERY_MODEL=claude-fable-5`), selected via `LLM_PROVIDER`; missing keys fail loudly, no fake fallback
- [x] Strict/Pydantic-validated action contract (one tool per action kind)
- [x] Observe → decide → policy → act loop
- [x] Max steps + timeout + repeated-state detection + error/denial budgets
- [x] Goal completion signal (`done` independently verified against live UI)
- [x] Raw discovery trace retained only as evidence, not artifact
- [x] Mock model available for tests/offline run (clearly labeled test double)

## M5 — Artifact compiler/schema
- [x] Pydantic artifact models with cross-validation
- [x] Inputs parameterized (bindings → `InputValueRef`, fails loudly otherwise)
- [x] Typed outputs
- [x] Ordered locator strategies
- [x] Checkpoint/success conditions (parameterized URL globs + stable headings)
- [x] Error/recovery declarations (app-profile rules)
- [x] Policy/risk metadata (artifact can only narrow global policy)
- [x] Version/provenance/app-compatibility metadata
- [x] JSON serialization + validation + sensitive-value scan

## M6 — Deterministic replay
- [x] No LLM dependency in replay path (enforced by construction + static test)
- [x] Input validation/binding before any browser action
- [x] Step interpreter
- [x] Wait/checkpoint verification (condition polling, no arbitrary sleeps)
- [x] Output extraction with type coercion
- [x] Business outcome classification (`MEMBER_NOT_FOUND`, `VALIDATION_REJECTED`, `PERMISSION_DENIED`)
- [x] Recoverable retry/known-dialog handling (interstitial dismiss, transient wait+reload; bounded)
- [x] Hard failure with failed-step/expected/observed/evidence
- [x] Structured `RunResult` discriminated union

## M7 — Human escalation
- [x] Intervention request object/store
- [x] Explicit control owner state (AUTOMATION/PAUSED/HUMAN, guarded transitions)
- [x] Operator page lists interventions
- [x] Take Control works
- [x] Same browser session remains active
- [x] Resume works (collects redacted events, engine revalidates checkpoint)
- [x] Abort works (terminal)
- [x] Human actions captured/redacted (context init script + sanitization)
- [x] Revalidation after resume (step checkpoint must pass before AUTOMATION)

## M8 — Tests
- [x] schema tests
- [x] parameter binding tests
- [x] policy tests
- [x] redaction tests
- [x] error taxonomy tests
- [x] replay contract tests
- [x] locator resolver behavior (ambiguity rejection covered via integration)
- [x] deterministic replay integration test (different member than discovery)
- [x] handoff state-machine test + full same-session handoff integration test
- 84 tests passing: `pytest -q`

## M9 — Submission artifacts
- [x] `README.md`
- [x] `REPORT.md` exact seven headings
- [ ] `/evidence/example_capability.json` — **requires genuine API run** (see below)
- [ ] `/evidence/discovery_run.jsonl` — **requires genuine API run**
- [ ] `/evidence/replay_success.jsonl` — captured together with the genuine run
- [ ] `/evidence/replay_not_found.jsonl` / `replay_failure.jsonl` / `failure_screenshot.png` — captured together with the genuine run
- [x] evidence tooling validated end-to-end via `scripts/capture_evidence.py --fake` (dry run, clearly labeled)
- [x] exact demo commands validated from clean setup

**Genuine evidence:** with the demo app running and `GEMINI_API_KEY` set (the
default Gemini provider; or `ANTHROPIC_API_KEY` with `--provider anthropic`),
run `python scripts/capture_evidence.py`. It fails loudly without a key and
never falls back to a scripted model. No evidence has been fabricated; the
committed evidence set is produced only by that real run.

## M10 — Final audit
- [x] requirements audit (inline, against docs/01 traceability)
- [x] security review (inline: secrets scan, redaction checks, policy gates)
- [x] test review (inline, against docs/09 plan)
- [x] no secrets in repository
- [x] git status clean except intentional files
- [x] final end-to-end demo succeeds (offline path; genuine-evidence command pending API key)
