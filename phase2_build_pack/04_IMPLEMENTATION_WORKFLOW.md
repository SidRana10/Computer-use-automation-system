# Implementation Workflow

Follow these phases in order. Do not optimize UI before the replay core is reliable.

## Phase 0 — Baseline and instruction reconciliation

Goals:
- verify branch `meridian-adaptation`
- verify clean working tree
- run the existing test suite and record baseline
- inspect current Phase 1 docs/instructions
- identify any conflicts with Phase 2
- minimally update project guidance only after the conflict is understood

Exit criteria:
- baseline tests pass or pre-existing failures are documented
- no accidental behavior changes

## Phase 1 — MERIDIAN target adapter and authentication

Goals:
- add MERIDIAN as a second target through adapter/configuration seams
- preserve Northstar behavior
- support sign-on with typed inputs
- detect login failures and session-expiry states
- establish stable page/state identification for legacy pages

Prefer semantic/structural locators before brittle coordinates.

Exit criteria:
- deterministic sign-on works for teller and supervisor
- bad-login outcome is structured
- session state is observable
- tests cover adapter/state recognition

## Phase 2 — Member inquiry and balance

Goals:
- search by member number
- search by last name
- select member deterministically
- read shares, balances, status
- classify not-found cleanly
- redact sensitive values in durable evidence according to existing policy

Exit criteria:
- balance capability works end-to-end against at least two seed members
- injected/natural not-found is a business outcome, not a hard crash
- evidence is available

## Phase 3 — Funds transfer

This is load-bearing.

Goals:
- from-share, to-share, amount, memo
- extract the dynamic per-transaction hidden token from the page
- carry dynamic token through deterministic replay without hardcoding
- support review -> validate -> post
- preserve irreversible-action approval/risk rules
- return confirmation number or structured business outcome
- handle insufficient funds/validation deliberately

Exit criteria:
- successful transfer works end-to-end
- token is read dynamically for each transaction
- review data is checked before post
- insufficient funds / validation do not become generic failures
- evidence proves what happened

## Phase 4 — Remaining capabilities

Implement thin but real versions of:
- Open New Share
- Update Member Information
- Place Account Hold

Place Hold must preserve supervisor gating and escalation semantics.

Exit criteria:
- each required capability has a typed artifact and deterministic replay path
- teller attempting a restricted hold stops/escalates safely
- supervisor path succeeds where appropriate

## Phase 5 — Exceptional-state framework

Exercise the target's injectable error states deliberately:
- validation 400
- notfound 404
- permission 403
- timeout 440
- maintenance 503
- server 500

Goals:
- map MERIDIAN-specific pages/statuses into the existing error taxonomy
- define bounded recovery only where safe
- ensure recovery actions still pass through PolicyEngine
- avoid duplicate irreversible posts during retries/resume

Exit criteria:
- each injected state has a deterministic test/demo case
- statuses are separated into business outcome / recoverable / failed / escalated
- no unsafe retry after an uncertain irreversible post

## Phase 6 — Capability API

Keep this thin.

Goals:
- catalog/list endpoint or tool interface
- typed invocation request
- stable capability name/version
- structured result envelope
- run/evidence ID
- consistent error/escalation envelope
- replay engine is the only execution path underneath

Prefer the existing Python stack; FastAPI is appropriate if it already fits the repo.

Exit criteria:
- balance and transfer can be invoked through API without UI knowledge
- all capability schemas are discoverable
- policy/evidence behavior is identical to direct replay

## Phase 7 — Chatbot

Goals:
- minimal natural-language front door
- map request -> capability + typed args
- call API only
- no direct Playwright access
- no independent transaction execution logic
- clear confirmation/error/escalation language

Exit criteria:
- demo request for balance works
- demo request for transfer works
- error/escalation surfaces clearly

## Phase 8 — Dashboard

Goals:
- capability catalog
- run history
- run detail
- inputs / structured outputs
- status
- evidence links/previews
- steps/timings/logs

Use the simplest stack that fits the repository. Avoid spending time on visual polish.

Exit criteria:
- reviewer can understand what happened in a run without reading raw source

## Phase 9 — Integration, docs, evidence, demo hardening

Goals:
- full test suite
- exact setup/run instructions
- demo commands
- offline/mock seam if needed
- 1–2 page write-up
- backup evidence/screen recording if practical
- known limitations and next steps

Exit criteria:
- all items in `08_DEFINITION_OF_DONE.md`
- successful demo path + exceptional path + escalation path
