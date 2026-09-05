# Exact Phase Prompts for Claude Code (Opus 5)

Use these sequentially. Do not paste all at once unless Claude has already completed the prior phase.

---

## Prompt A — Phase 0

Implement Phase 0 from `phase2_build_pack/04_IMPLEMENTATION_WORKFLOW.md` only.

Do not start MERIDIAN feature work yet.

Verify the baseline, reconcile Phase 1 project instructions with Phase 2, and propose the smallest instruction/doc changes needed so Phase 2 work is not blocked by stale Phase 1 constraints.

Run the existing tests. Do not hide pre-existing failures.

At the end, report:
- baseline test result;
- instruction conflicts found;
- files changed, if any;
- why each change was necessary;
- whether Phase 1 behavior changed.

Stop after Phase 0.

---

## Prompt B — Phase 1

Implement Phase 1: MERIDIAN target adapter + authentication.

Constraints:
- extend the existing target/adapter/configuration seams rather than creating a parallel automation engine;
- preserve Northstar support and tests;
- keep typed inputs/outputs;
- all browser actions must continue through the same policy-controlled execution path;
- do not add API/chatbot/dashboard yet.

Use the live MERIDIAN target and public demo users where appropriate.

Add tests for MERIDIAN state recognition, successful sign-on, bad login classification, and session-expiry detection where testable.

Run targeted tests and the full suite.

Commit only if green. Stop after Phase 1 and summarize changes/risks.

---

## Prompt C — Phase 2

Implement Phase 2: member inquiry/selection + member record/balance.

Requirements:
- search by member number;
- search by last name;
- deterministic member selection;
- read shares, balances, and status;
- map not-found to a deliberate business outcome;
- preserve redaction/evidence rules;
- use the existing capability schema and replay engine rather than bespoke scripts.

Create/record the necessary MERIDIAN capability artifact(s) using the existing discovery path whenever live discovery is available. If a boundary must be mocked, keep the seam clean and document it.

Run real end-to-end replay against at least two seed members when possible.

Add tests and evidence. Run full suite. Stop after Phase 2.

---

## Prompt D — Phase 3

Implement Phase 3: Funds Transfer. Treat this as load-bearing.

Requirements:
- typed inputs: member, from-share, to-share, amount, memo;
- dynamically extract the per-transaction hidden token from the live page;
- never hardcode a token;
- carry the extracted token through deterministic replay;
- implement review -> validate -> post;
- preserve existing risky/irreversible action safeguards;
- do not retry an irreversible post when final transaction state is uncertain;
- return structured confirmation data on success;
- classify insufficient funds and validation rejections as business outcomes;
- preserve screenshots/DOM/log/timing evidence with redaction.

Use the existing capability artifact/replay abstraction. Generalize the core only where MERIDIAN proves a real coupling issue; document each such generalization.

Add targeted regression tests for dynamic extraction, review/post gating, outcome classification, and no-duplicate-post behavior.

Run targeted tests + full suite + one live successful transfer if safe in the sample app.

Stop after Phase 3 and summarize exactly what changed.

---

## Prompt E — Phase 4

Implement the remaining required MERIDIAN capabilities:
- Open New Share
- Update Member Information
- Place Account Hold

Keep each implementation thin but real.

Requirements:
- typed/versioned capability artifacts;
- deterministic replay;
- review/post handling where present;
- business validation outcomes for invalid email/phone or transaction rejection;
- Place Account Hold must preserve risk classification and supervisor-only behavior;
- teller attempting a restricted hold must stop/escalate safely rather than bypassing permissions;
- supervisor path should succeed where the target permits it.

Preserve PolicyEngine, redaction, evidence, and handoff semantics.

Add tests + live verification where practical. Run full suite. Stop after Phase 4.

---

## Prompt F — Phase 5

Implement and verify MERIDIAN exceptional-state handling.

Exercise all supported injected states deliberately:
- `?inject=validation`
- `?inject=notfound`
- `?inject=permission`
- `?inject=timeout`
- `?inject=maintenance`
- `?inject=server`

Map each state into the existing error taxonomy and return deliberate structured status.

Rules:
- business outcomes are not infrastructure failures;
- recoverable conditions get bounded, policy-controlled recovery only;
- hard failures stop and preserve evidence;
- permission/risky states may escalate;
- recovery actions must go through PolicyEngine;
- never create duplicate irreversible effects during retry/resume;
- unknown UI states must fail closed.

Add regression tests for each category and at least one live injected verification per category where practical.

Run the full suite and stop after Phase 5.

---

## Prompt G — Phase 6

Implement the capability API only.

Keep it intentionally small and built on top of the existing replay engine.

Required behavior:
- list/catalog capabilities;
- expose name/version/input/output schema;
- invoke capability by stable name with typed args;
- structured result envelope containing status, output/business outcome/error/escalation, run ID, and evidence reference;
- replay engine remains the sole browser-execution path;
- callers do not know MERIDIAN selectors/routes;
- PolicyEngine/redaction/evidence/handoff semantics remain unchanged.

Prefer the existing Python stack. If FastAPI is already appropriate, use it rather than introducing a heavier framework.

Add API tests, especially balance, transfer, validation failure, and escalation response shapes.

Run full suite. Stop after Phase 6.

---

## Prompt H — Phase 7

Implement the thin chatbot.

Architecture rule: chatbot -> capability API -> deterministic replay. The chatbot must not call Playwright or execute transaction steps itself.

It should:
- accept a simple user request;
- choose the capability;
- extract/validate typed args;
- call the API;
- clearly render success, business outcome, recoverable error, hard failure, or escalation;
- surface useful structured values such as balances and confirmation numbers.

Keep UI and prompt logic minimal and auditable. Do not build a general autonomous agent.

Add tests around intent/capability routing and result rendering. Stop after Phase 7.

---

## Prompt I — Phase 8

Implement the lightweight dashboard.

Show at minimum:
- capability catalog;
- discovery/replay run history;
- run status;
- inputs;
- structured outputs;
- step list;
- screenshots;
- DOM/evidence references;
- timings/logs;
- error/escalation details.

Use the simplest stack already compatible with the repo. Do not spend time on visual polish, animations, auth systems, or production scaling.

The dashboard is an observability/demo surface, not a second control plane around PolicyEngine.

Add basic tests where practical. Stop after Phase 8.

---

## Prompt J — Phase 9

Perform Phase 9 integration and demo hardening.

Do not add speculative features.

Tasks:
- run all unit/integration/end-to-end tests;
- run representative live MERIDIAN flows;
- verify every required capability exists and is callable;
- verify API -> replay, chatbot -> API -> replay, and dashboard visibility;
- verify redaction and no-secret persistence;
- verify policy enforcement and escalation through every wrapper;
- create/update README setup instructions;
- document exact demo commands;
- write the requested 1–2 page technical write-up;
- document intentional cut lines and next steps;
- prepare a deterministic demo sequence;
- preserve evidence/logs/screenshots for backup.

Use `08_DEFINITION_OF_DONE.md` as a hard checklist.

Stop when all achievable items are verified. Clearly list anything incomplete rather than hiding it.
