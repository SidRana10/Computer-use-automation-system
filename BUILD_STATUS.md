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

## M12 — P1: MERIDIAN adapter, core seams, sign-on (implemented, awaiting review)
- [x] live MERIDIAN reconnaissance: all 14 open questions answered with evidence
- [x] scope corrected from reconnaissance findings (see D018)
- [x] G5 target profile registry + HTTPS/443 policy fix (Northstar left in place)
- [x] G3 hidden-value internal extraction (`value` mode + `internal` steps)
- [x] G7 structured table extraction (`json` output type, variable-length rows)
- [x] G4 irreversible-write no-repeat invariant (`IRREVERSIBLE_OUTCOME_UNCERTAIN`)
- [x] G8 artifact-scoped supervisor escalation routing (`escalate_on_codes`)
- [x] G10 row-relative locators via the existing CSS strategy — no new kind (D019)
- [x] G11 observation fixes (h1 via profile, submit `value`, name/id in inventory, select by value)
- [x] G12 profile-driven redaction: DOM snapshot scrubbing + screenshot masking
- [x] G6a DOM snapshot evidence (run index deferred to the service phases)
- [x] profile-driven fingerprint recognition
- [x] CLI target/profile selection (`--app`)
- [x] MERIDIAN sign-on capability artifact + live teller/supervisor verification
- [x] P1 audit: Playwright traces disabled for MERIDIAN (D021)
- [x] P1 audit: sensitive-value scan narrowed to run-derived fields (D022)
- [x] canonical `meridian.sign_on` is genuinely discovery-generated: Gemini
      gemini-3.6-flash, run disc-1d408f679a, compiled via unmodified
      ArtifactCompiler, deterministic replay verified for teller + supervisor
      (D025)
- [x] P1 audit: narrow credential/field-name locator exemption (D024) resolves
      the D023 collision without weakening D014
- 226 offline tests passing (123 Phase-1 unchanged + 103 new); 232 with live tests

Explicitly NOT in P1 (deferred or dropped on evidence): parameterized locators
(G1), StepOutputRef (G2), session manager, frame support (G9), run index (G6b),
API, chatbot, dashboard.

## M13–M16 — P2-P5 (implemented, awaiting review)
- [x] P2 member inquiry (search by number and by last name, single/multi/no
      match) + get_member_balances (variable share table, two members with
      structurally different share counts: 31 vs 8)
- [x] P3 funds transfer (hidden-token internal extraction, review→post gate,
      irreversible no-repeat, insufficient-funds business outcome, one real
      live transfer proving the flow)
- [ ] P3 gap: `meridian.funds_transfer` still does not expose
      `confirmation_number` as a typed output. Investigated in depth (see
      DECISIONS.md D035): a fifth core generalization (`observation.py` now
      enumerates MERIDIAN's label/value result cells, e.g. "Confirmation:",
      the same pattern D019/D020 already used for masking) makes the value
      genuinely observable and extractable, verified live. Two further
      genuine discovery runs and two minimal ($1) real live transfers were
      spent confirming this; the second compiled a seemingly-valid artifact,
      but replay verification caught a real defect before it was kept
      canonical: `DiscoveryAgent._to_executable` doesn't forward
      `extract_mode`, so discovery silently always extracts in "text" mode
      regardless of what it records, masking that the goal wording asked for
      the wrong mode ("value", correct only for the hidden `_token` form
      field, not a plain result cell) for this new case. Canonical artifact
      reverted to its original state rather than kept half-working. Fix is
      understood and scoped (agent.py forward the mode; correct the goal
      text to `extract_mode="text"`) and needs one clean discovery run with
      no further live transfer required to test the observation fix itself.
- [x] P4 open share (risky, real live post), update member info (risky, real
      live post + invalid-email business outcome), place hold (irreversible,
      teller→supervisor escalation demonstrated end-to-end in the same
      session, real live hold applied)
- [x] P5 exceptional-state matrix: all six `?inject=` states classified
      correctly against the live target (validation/notfound/permission/
      timeout/maintenance/server), plus natural bad login, insufficient
      funds, invalid email, teller-attempts-hold, and unrecognized-value
      fail-closed — 9 live integration tests, all passing
- [x] four core generalizations, each driven by a genuine live discovery
      failure, not speculative: table-element observation (D028), hidden
      form-field observation (D032), compiler-forced JSON type for table
      extracts (D031), bidirectional runtime-value containment check (D030);
      plus Gemini free-tier rate-limit/transient-error backoff (D029) and two
      new MERIDIAN error rules/policy classifications (D033, D034) found live
- [x] all 7 required capability artifacts exist, genuinely discovery-generated
      (Gemini, several models — see DECISIONS.md D029), replay LLM-free
- 274 offline tests passing (226 P1 baseline + 43 P2-P5 + 5 new for the
  label/value result-cell observation fix, D035); 9 additional live
  exceptional-state tests pass with MERIDIAN_LIVE=1
- API, chatbot, dashboard explicitly NOT built yet (P6-P8, per instruction)

## M17–M19 — P6..P9
- [ ] P6 capability API
- [ ] P7 chatbot
- [ ] P8 dashboard
- [ ] P9 integration, docs, evidence, demo hardening

