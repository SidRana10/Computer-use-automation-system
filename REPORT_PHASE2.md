# Phase 2 — MERIDIAN CORE adaptation

## 1. Adapting the existing core

This was an adaptation, not a rewrite. Everything above the surface line
carried over unchanged: the artifact schema, the `PolicyEngine`, the central
`Redactor`, the three-way error taxonomy, the `HandoffManager` state machine,
the `ReplayEngine`, and the discovery loop itself. MERIDIAN is reached through
the same `SurfaceAdapter` Northstar uses, selected by a target-profile
registry (`targets/meridian.py`) that carries policy, error rules, a
fingerprint, credential input names, and redaction/mask selectors — the same
seam design already anticipated a second target profile.

What MERIDIAN forced us to generalize, each driven by a concrete live
failure rather than speculation:

- **Legacy DOM observation.** MERIDIAN renders no `id`, `aria-label`,
  `data-*`, or `<label>` attributes. The observation inventory gained
  bordered-`<table>` detection, hidden-`<input>` visibility (needed to let
  discovery *read* a per-request security token without ever making it
  clickable), and label/value result-cell detection anchored on MERIDIAN's
  own `.lbl` class — a content-based, not positional, locator strategy.
- **Structured table extraction.** Member share lists and search results are
  variable-length legacy tables with no schema. A `extract_mode="table"`
  path serializes them into typed JSON rows; the compiler now force-sets
  `output_type="json"` for any table extract so the contract can't disagree
  with what the extraction mechanism actually produces.
- **Hidden-token handling.** Funds transfer and hold both submit a per-request
  hidden `_token` field. Discovery can observe and internally verify it
  (`ExtractAction.internal=True`) without it ever becoming a published
  output or a persisted value — the schema already had this boundary; the
  compiler just wasn't wiring `internal` through until MERIDIAN needed it.
- **Irreversible no-repeat protection.** Once a review→post click is
  dispatched and its outcome is uncertain, automation must never retry it
  automatically. This is enforced structurally, not by convention.
- **Supervisor escalation.** MERIDIAN gates some actions (placing a hold) to
  supervisor-only. This did not need a fourth error class — it's a policy
  decision (`policy.escalate_on_codes`) layered on the existing three-way
  taxonomy, routed through the same `HandoffManager` path Northstar's
  irreversible-action approval already used.
- **Evidence/redaction differences.** MERIDIAN renders live session ids,
  transaction tokens, and real member data the run never supplied. Screenshot
  masking and structural DOM scrubbing were added at capture time (region
  scrubbing must run before value redaction, or a redacted number inside a
  sentence leaves the surrounding name intact). Durable Playwright traces are
  disabled for MERIDIAN specifically because an early trace was found to
  contain the sign-on POST body and unmasked frame images verbatim — nothing
  in the redaction path can reach inside Playwright's own recorder.

## 2. Capability API / contract

`caller → capability API → existing guarded replay path → MERIDIAN`. A single
`CapabilityService` is the only entry point that turns "invoke capability X
with these arguments" into a replay run; the HTTP routes and the chatbot both
call it in-process — never a second Playwright execution path
(`api/runner.py` is the only module in `api/`/`chatbot/`/`dashboard/` allowed
to import a surface, statically pinned by a test).

Every MERIDIAN capability's typed contract declares `operator_id`,
`password`, and `branch` as inputs, because each one embeds its own sign-on
for hermetic replay. The point of the API is that a caller doesn't need to
know that: those three names are excluded from the public schema and injected
server-side from environment credentials, so a caller only ever supplies the
business arguments a member-servicing task actually varies per call
(`member_number`, `amount`, `to_share`, …). A caller naming a server-supplied
field, or `human_approved`, is rejected with HTTP 400 before the catalog
lookup is even bound to input — no side effects, no evidence directory, no
browser.

## 3. Reliable legacy UI driving + errors

One genuine discovery run per capability, then unlimited deterministic
replays with zero LLM calls in that path — architecturally true (no model
client is even reachable from the replay/surfaces/policy/handoff packages)
and operationally exercised for all seven against an invocation different
from each capability's own discovery run. The three read capabilities
(sign-on, member inquiry, balances) complete unattended end to end. The four
risky/irreversible capabilities (funds transfer, open share, update member
info, place hold) correctly execute every automated step up to their
policy-gated human-approval click and stop there for an unattended replay —
the intended behavior, not a shortfall — and go on to complete when that
approval is granted, as place hold and update member info are both shown
doing in committed evidence. Each step binds inputs, checks policy, resolves
a locator strategy chain, executes, then verifies a declared checkpoint — a
click only "worked" if the expected state actually appeared.

The hidden session/transaction token is read internally where the flow
requires it and never persisted. Funds transfer and hold both follow a
review→post shape: fill, reach a review screen showing the values entered,
then a single irreversible post click gated by policy. Failures classify
into exactly three outcomes, unchanged from Phase 1: **business outcomes**
(insufficient funds, invalid email, member not found) return cleanly to the
caller as a result, not a crash; **recoverable** conditions retry within a
bounded budget and record the attempt; **hard failures** stop with
expected/observed detail and a screenshot. Escalation is a fourth concern
layered on top by policy, not a fourth taxonomy value — "what happened" and
"who must handle it" answer different questions.

## 4. Safety, evidence and escalation

Policy stays on the execution path for every action, in discovery and
replay alike — model-proposed, artifact-declared, or bounded-recovery
actions all pass the same `PolicyEngine` before the surface executes.
Risky and irreversible controls (open share, save changes, post transfer,
apply hold) require a human by default; artifact policy can only narrow
global policy, never broaden it.

The teller→supervisor handoff is demonstrated end to end: a teller-signed-on
replay hits `SUPERVISOR_REQUIRED` at the hold step, control transfers to a
human in the same live browser session, the supervisor completes the gated
step, control returns to automation, the engine re-verifies before
proceeding, and a second, independent irreversible-approval gate still
applies to the actual "apply hold" click. Two real gates, not one dressed up
as two.

Durable evidence is masked at capture — screenshots via Playwright's own
`mask=` region list, DOM snapshots via structural scrubbing before the
central redactor's pattern pass — so sensitive pixels and markup never reach
disk in the first place, while the structured result returned to the caller
is unaffected. MERIDIAN's raw Playwright traces are disabled entirely: an
early trace was inspected and found to contain the sign-on POST body and
unmasked frame JPEGs, and nothing in the redaction pipeline can reach inside
Playwright's own recorder to fix that after the fact. Redacted JSONL logs,
masked screenshots, redacted DOM snapshots, and the structured result remain
the durable record instead.

## 5. Deliberate cuts / next steps

- **`meridian.funds_transfer` has no typed `confirmation_number` output.**
  Root cause is understood and documented (`DECISIONS.md` D035): discovery's
  executable-action builder doesn't forward the model's declared
  `extract_mode`, so a discovery run can silently extract in the wrong mode
  and still report success. Two genuine live $1 transfers were spent
  isolating this; the fix is a one-line forward plus a corrected goal
  string, deliberately not applied in this documentation/evidence phase so
  as not to touch capability logic during delivery.
- **The chatbot's intent routing is deterministic regex/keywords, not a
  model call.** This matches the assignment's own instruction to keep it
  thin rather than build a second agent framework; swapping in a
  structured-output call to the same Gemini/Anthropic adapters discovery
  already uses is a scoped, natural next step behind the same function
  signature.
- **Execution is serialized.** One live invocation runs at a time
  (`CapabilityRunner` holds a lock, matching one shared headed
  browser/operator console) — correct for a single-operator demo, a real
  ceiling under concurrent load.
- **`meridian.member_inquiry`'s table extraction can duplicate its header
  row** as an extra first data row on some renders. Data integrity is
  unaffected; not fixed here. Separately, its contract declares two output
  fields (`member_results`, `member_results_table`) that carry equivalent
  data — the canonical discovery run issued the same extract twice before
  calling `done`, and the compiler recorded both rather than collapsing
  them. Also not fixed here, to avoid rediscovering this capability.

These were accepted in favor of finishing the required end-to-end system —
seven genuinely discovery-generated capabilities, a caller-facing API, a
chatbot, and a dashboard, all sharing one guarded replay path — rather than
spending further live-transaction budget chasing one non-blocking output
field.
