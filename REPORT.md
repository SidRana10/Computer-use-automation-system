# 1. Architecture

The system is a compiler/runtime for UI capabilities. Discovery is
compilation: a natural-language goal plus a live UI plus LLM decisions
produces a normalized capability artifact. Replay is the runtime: artifact
plus invocation inputs produces deterministic UI execution and one structured
result. The two paths share the policy engine, the redactor, the evidence
pipeline, and the `SurfaceAdapter` — and deliberately share nothing about
decision-making: the discovery agent holds the only model client in the
system, and the replay engine cannot even represent one.

Discovery is provider-pluggable behind a single `ModelAdapter` seam with a
factory that knows two genuine providers: Google Gemini (the default provider;
`gemini-3.6-flash` is the runtime model that produced the submitted genuine
evidence, as recorded in the artifact's provenance) and Anthropic Claude as an
optional alternative.
Both expose the same eight narrow UI-action tools via forced function calling
and share one validation path; a missing API key fails loudly, and the
scripted test double can never be substituted for a genuine provider.
(Development of the repository itself was AI-assisted with Claude Code /
Claude Fable 5; deterministic replay invokes no LLM from any provider.)

Everything runs local-first in one process per command: the synthetic target
app (FastAPI/Jinja, deliberately legacy-styled), the automation core, and a
minimal operator console that shares the automation's event loop so both see
the same handoff state and the same live Playwright session. There are no
queues or services because the assignment's hard problems — schema quality,
deterministic replay, error taxonomy, control transfer — are not
infrastructure problems.

Observation is hybrid: each discovery turn gives the model a real screenshot
*and* a compact semantic element inventory with ephemeral refs (`e1`, `e2`…)
plus candidate durable locator strategies the adapter derives itself. The
screenshot keeps the approach credible for hostile/no-clean-DOM surfaces; the
semantic inventory is what lets the compiler emit robust replay targets. The
model picks refs; it never invents selectors, and there is no code/JS action
in its vocabulary. Trade-off: the inventory is bounded (~40 elements), so very
dense screens would need pagination or region-based observation — acceptable
for back-office pages.

# 2. Artifact schema

The artifact is an agent-invocable contract, not a click recording. Its core
blocks: a typed `contract` (inputs with type/pattern/sensitivity; outputs with
type and `source_step_id`), ordered `steps`, `success_conditions`,
`error_rules`, an artifact-scoped `policy`, target-app metadata with a
fingerprint, and `provenance` (run id, model, timestamp). Schema and semantics
are enforced with Pydantic cross-validation: outputs must point at extract
steps, value references must name declared inputs, targeted actions must carry
at least one locator strategy, and an artifact containing an irreversible step
must declare itself irreversible.

Dynamic values are `{"kind":"input","name":"member_id"}` references, never
discovery literals. The compiler uses the explicit discovery invocation
bindings (`member_id=M-10001`) as the deterministic mapping: literals equal to
a binding become input refs; URLs and checkpoint values containing a binding
are parameterized (`/members/*`); and compilation fails loudly if a sensitive
value cannot be parameterized or if the serialized artifact still contains any
bound or extracted sensitive value. Element targets are `TargetDescriptor`s
with an ordered strategy chain (role+name, label, placeholder, text, stable
attribute, restrained CSS); ambiguity is rejected rather than resolved to a
first match. The raw transcript never becomes the artifact: the recorder's
redacted evidence stays in `evidence/runs/…`, and the compiler emits only
normalized steps — this keeps the capability reviewable, diffable, and free of
model reasoning and PII.

# 3. Determinism & error handling

Replay interprets the artifact with zero LLM calls — architecturally (the
engine has no model dependency; a static test forbids the SDK across the
replay/surfaces/policy/handoff packages) and operationally (one real discovery
run, then unlimited cheap replays). Inputs are validated against the contract
before the browser starts. Each step: bind values → policy check → resolve the
target by trying strategies in order until exactly one element matches →
execute with bounded actionability timeouts → evaluate declared checkpoints
(parameterized URL globs plus stable page headings — a click only "worked" if
the expected state actually appeared). Waits are condition polls, never
arbitrary sleeps. Which strategy matched is logged, so repeated fallback use is
visible as a drift signal.

Failures are classified against the artifact's declared error rules, in
order, into three classes with distinct result statuses. Business outcomes
(`MEMBER_NOT_FOUND`, `VALIDATION_REJECTED`, `PERMISSION_DENIED`) return
cleanly to the caller — a "no such member" is a result, not a crash.
Recoverable conditions run explicit bounded recovery (dismiss the known idle
interstitial; wait+reload for the transient load), re-verify the checkpoint,
retry within a small budget, and record every attempt in the result. Hard
failures (`TARGET_NOT_FOUND`, `CHECKPOINT_FAILED`, `SESSION_EXPIRED`,
`RETRY_EXHAUSTED`…) stop immediately with step id, expected vs observed, and a
failure screenshot. UI drift is secondary by design: the fingerprint check,
matched-strategy telemetry, and checkpoint failures are the signals that an
artifact needs review.

# 4. Heterogeneity & multi-tenant

Implemented: one web surface (Playwright). Everything else here is design.

The seam is `SurfaceAdapter`: observe → semantic inventory, execute →
normalized actions, resolve → strategy chains, evaluate → conditions. The
artifact speaks in surface-neutral intents ("click the control named
*Accounts*", "extract the value identified by *X*"), so a desktop adapter
would translate `role_name`/`label` strategies to UI Automation/accessibility
queries, and a vision adapter could add an anchor-based strategy kind; the
`LocatorStrategy.kind` enum and `surface_kind` field are the extension points.
A legacy frameset web app needs only the `frame_path` strategy kind the schema
already reserves. The replay engine, error taxonomy, policy engine, and
handoff model are unchanged in all cases.

For hundreds of tenants running the same vendor product: artifacts carry
`vendor_family`, an app fingerprint, and compatibility metadata. The base
capability would belong to the vendor family; a tenant variant would be a
small versioned *override* (specific locator replacements, route prefixes,
entry point, extra interstitial rules — the same shape as the app-profile
error rules already attached at compile time), never a copied artifact.
Fingerprint mismatches, checkpoint degradation, and rising fallback-strategy
usage across a fleet are the drift detectors that route an artifact to
re-validation or re-discovery instead of silently mutating it.

# 5. Escalation & handoff

Stuck detection during discovery: max steps, wall-clock timeout, repeated
state+action fingerprints, repeated execution errors, repeated policy denials,
or the model explicitly requesting a human. During replay: policy demanding
approval for a risky/irreversible step (the demo path), or hard failure.

Control ownership is an explicit typed state machine — AUTOMATION → PAUSED
(intervention raised) → HUMAN (operator clicks Take Control) → PAUSED
(Resume) → AUTOMATION (only after revalidation) — with guarded transitions, so
automation and the human can never act simultaneously; automation blocks on the
intervention while the Playwright browser/context/page stay open. The
intervention carries run/capability/step, reason, redacted URL and screenshot.
The operator console (same process, same loop) exposes Take Control, Resume,
and Abort. While owner is HUMAN, a static context-level init script records
redacted interaction metadata (click target identity, `value_changed=true,
value=[REDACTED]`, same-origin navigation paths) into `sessionStorage` so it
survives page navigations; Resume collects it, re-sanitizes it in Python, and
attaches it to the intervention. The engine then re-observes and requires the
step's own checkpoint to pass before ownership returns to automation — a human
saying "done" is verified, not trusted. In the demo, automation stops before
the irreversible "Confirm Open Account", the human clicks it in the same
window, and automation resumes to extract the confirmation number. This event
capture is a prototype analogue of production co-browsing/audit tooling, and a
production version would put ownership behind durable session leases.

# 6. Safety

The model proposes; deterministic code decides. Every action — model-proposed
in discovery, artifact-declared in replay, or taken during bounded recovery —
passes the PolicyEngine before the
surface executes: HTTP(S)-only, host/port allowlist, glob route allowlist
(re-checked after navigation, so injected redirects can't silently escape),
action-kind allowlist, and risk gating. Risk has four classes; risky and
irreversible require a human. Declared step risk can only raise the effective
class, and a deterministic control-text classifier ("confirm open account" →
irreversible) provides a floor during discovery, when no annotation exists
yet. Artifact policy composes with global policy by intersection — a
capability can narrow privileges, never broaden them; route containment is
decided by the route-pattern semantics themselves, so a capability cannot
introduce a route the global policy forbids. The model's action
schema contains no shell/JS/code tool at all.

Privacy: one central redactor is the only path to disk. It redacts by
sensitive key names, secret-shaped patterns (API keys, bearer tokens), and
registered concrete runtime values — bound sensitive inputs and extracted
balances — so even incidental appearances in visible-text summaries or error
messages are scrubbed. Artifacts describe sensitive fields but never contain
values (compiler-enforced); sensitive outputs are returned to the caller but
redacted in persisted logs; human typing is never captured. `.env` is
gitignored with a blank `.env.example`. Limits: screenshots and Playwright
traces do show on-screen synthetic data — acceptable here because every value
is fictional; a regulated deployment would need encrypted ephemeral evidence
storage, access controls, and screenshot redaction policy, which I did not
build.

# 7. Cuts

Deliberate cuts: only the web adapter (desktop/accessibility/vision are
seams); one local run at a time with an in-memory intervention store and no
operator auth/RBAC; a JSON file store instead of a capability catalog service;
no cross-tenant canonicalization beyond the vendor-family/override design; no
open-ended LLM recovery during replay (a policy-bounded single-step assisted
fallback is the stretch I'd add first, recorded as evidence); no co-browsing
console — the operator uses the local headed browser, which is honest for a
control-transfer prototype but not remote-operable; screenshot/trace evidence
is unencrypted local files; the demo app's exceptional states are flags rather
than organic backend faults.

Next, in order: artifact approval workflow (draft → approved gating unattended
replay, which the schema already carries), multi-run stability scoring to
catch flaky capabilities before production, a tenant-override mechanism proven
against a second app variant, the bounded LLM-assisted repair step, and remote
session streaming for real operator takeover.
