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
- [x] Provider-pluggable model adapters: Gemini (default provider; `GEMINI_MODEL=gemini-3.6-flash` produced the submitted evidence) and Anthropic (`DISCOVERY_MODEL=claude-fable-5`), selected via `LLM_PROVIDER`; missing keys fail loudly, no fake fallback
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
- [x] `/evidence/example_capability.json` — compiled from genuine run `disc-3b572d9b32`
- [x] `/evidence/discovery_run.jsonl` — genuine Gemini `gemini-3.6-flash` discovery
- [x] `/evidence/replay_success.jsonl` — LLM-free replay, different member than discovery
- [x] `/evidence/replay_not_found.jsonl` / `replay_failure.jsonl` / `failure_screenshot.png`
- [x] `/evidence/discovery_trace.zip`
- [x] evidence tooling validated end-to-end via `scripts/capture_evidence.py --fake` (dry run, clearly labeled)
- [x] exact demo commands validated from clean setup
- [x] handoff evidence — `handoff_run.jsonl`, `handoff_interventions.json`,
      both handoff screenshots and `handoff_trace.zip` from run `rep-ff489aceae`
      (2 captured human events, full ownership cycle, revalidated completion)
- [ ] recoverable-condition and policy-block evidence files — test-covered only

**Genuine evidence:** captured from a real run of
`python scripts/capture_evidence.py` (demo app running, `GEMINI_API_KEY` set;
or `ANTHROPIC_API_KEY` with `--provider anthropic`). It fails loudly without a
key and never falls back to a scripted model. No evidence has been fabricated
or hand-edited.

## M10 — Final audit
- [x] requirements audit (inline, against docs/01 traceability)
- [x] security review (inline: secrets scan, redaction checks, policy gates)
- [x] test review (inline, against docs/09 plan)
- [x] no secrets in repository
- [x] git status clean except intentional files
- [x] final end-to-end demo succeeds, including the genuine Gemini discovery run
- [x] read-only evidence audit performed against the captured evidence set

---

# Phase 2 — MERIDIAN CORE adaptation (branch `meridian-adaptation`)

Baseline recorded at P0: **123 tests passing** (`pytest -q`, 79s, 0 failures).
Note: the "84 tests" figure in README/M8 predates later additions and is stale;
corrected at P9.

## M11 — P0 baseline and instruction reconciliation
- [x] branch `meridian-adaptation`, working tree clean apart from `phase2_build_pack/`
- [x] full suite run and recorded (123 passed)
- [x] Phase-1 instructions reconciled with Phase 2 (CLAUDE.md Phase 2 section)
- [x] `.gitignore` exception so MERIDIAN artifacts are committable
- [x] `.env.example` MERIDIAN + service variables
- [x] Phase-1 build-control docs marked historical
- [x] no source or application behavior changed

## M12 — P1 reconnaissance (complete) and core seams (not started)
- [x] live MERIDIAN reconnaissance: all 14 open questions answered with evidence
- [x] scope corrected from reconnaissance findings (see D018)
- [ ] G5 target profile registry + HTTPS/443 policy fix (Northstar left in place)
- [ ] G3 hidden-value internal extraction (`_token`), `value` mode only
- [ ] G7 structured table extraction (variable share/result sets)
- [ ] G4 irreversible-write no-repeat invariant
- [ ] G8 artifact-scoped supervisor escalation routing
- [ ] G10 row-relative locator via the existing CSS strategy (documented last resort)
- [ ] G11 observation fixes (h1, submit `value`, name/id in inventory, select by value)
- [ ] G12 profile-driven redaction: DOM snapshots + screenshot masking
- [ ] G6a DOM snapshot evidence (run index deferred to the service phases)
- [ ] profile-driven fingerprint recognition
- [ ] CLI target/profile selection
- [ ] MERIDIAN sign-on capability artifact

Explicitly NOT in P1 (deferred or dropped on evidence): parameterized locators
(G1), StepOutputRef (G2), session manager, frame support (G9), run index (G6b),
API, chatbot, dashboard.

## M13–M19 — P2..P9
- [ ] P2 member inquiry + balances
- [ ] P3 funds transfer
- [ ] P4 open share / update member / place hold
- [ ] P5 exceptional-state matrix
- [ ] P6 runner + capability API
- [ ] P7 chatbot
- [ ] P8 dashboard
- [ ] P9 integration, docs, evidence, demo hardening

