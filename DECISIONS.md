# Architecture Decision Log

Claude Code: append only meaningful deviations or trade-offs. Keep entries concise.

## D001 — Local target instead of public third-party site
**Decision:** Build a synthetic local legacy-style credit-union servicing app.
**Reason:** It avoids ToS/rate-limit issues, guarantees repeatable exceptional states, uses no real PII, and allows the submission to demonstrate the exact banking-like runtime failures in the brief.

## D002 — Single-process/local-first core
**Decision:** Keep the prototype simple and local, with explicit interfaces rather than scaling infrastructure.
**Reason:** The assignment rewards core abstractions and correctness, not premature queues/clusters/microservices.

## D003 — Hybrid visual + semantic discovery
**Decision:** Give the LLM a screenshot plus a compact semantic element inventory. Execute actions through Playwright.
**Reason:** Screenshot perception keeps the design credible for hostile/no-clean-DOM surfaces while semantic targets allow robust recording/replay on the concrete web implementation.

## D004 — Coordinates are not normal replay identity
**Decision:** Coordinates may be used as bounded discovery fallback/hints but artifacts must record stable locator strategy chains whenever possible.
**Reason:** Replay must be deterministic and robust to harmless viewport/layout variation.

## D005 — Human handoff uses headed browser + minimal operator console
**Decision:** Keep the same Playwright browser/context/page alive; automation pauses, an operator takes ownership and manipulates the existing headed browser, then resumes through a small local control page.
**Reason:** This proves the control-transfer seam without overbuilding real-time co-browsing.

## D006 — JSON artifacts and JSONL evidence
**Decision:** Use human-reviewable JSON capability artifacts and append-only JSONL run logs.
**Reason:** Easy to inspect, version, test, diff, and include in submission evidence.

## D007 — Sub-account capability contract extends to confirmation number
**Decision:** `member.open_sub_account(member_id, account_type) -> confirmation_number: string`, extracted after the human-approved confirm, instead of the suggested `review_reached: boolean`.
**Reason:** It demonstrates the full escalation arc (pause → human confirm in same session → resume → revalidate → extract → structured success) and gives the calling agent a genuinely useful output. The irreversible step itself is still never executed by automation.

## D008 — App error rules come from a per-app profile, applied by the compiler
**Decision:** Known business-outcome/recoverable/hard detectors (`MEMBER_NOT_FOUND`, `KNOWN_INTERSTITIAL`, `SESSION_EXPIRED`, …) live in `discovery/profiles.py` and are attached to artifacts at compile time.
**Reason:** These are deterministic vendor-app knowledge, not model output. In the multi-tenant design this is exactly what a vendor-family base capability would carry, with tenant overrides.

## D009 — Discovery risk classification is deterministic control-text policy
**Decision:** The PolicyEngine classifies control risk from configurable visible-text patterns (e.g. "confirm open account" → irreversible) in addition to declared step risk during replay.
**Reason:** During discovery no artifact risk annotation exists yet; the deterministic policy layer, not the model, must decide that a control is risky. Declared step risk can only raise, never lower, the effective risk in replay.

## D010 — Non-editable install used on the build machine
**Decision:** The build machine force-hides `*.pth` files (macOS flag), which Python 3.12+ site processing skips, breaking `pip install -e`. Locally the package is installed non-editable; `pytest` uses `pythonpath = ["src"]` so tests always run the working tree.
**Reason:** Machine quirk only. `pip install -e '.[dev]'` in the README remains correct for normal environments; a troubleshooting note covers this edge.

## D011 — Transient-load state requires an explicit reload recovery
**Decision:** The demo transient state renders a static "Accounts are loading" page (no auto-refresh); the artifact's `TRANSIENT_LOAD` rule recovers with bounded wait + reload.
**Reason:** With an auto-refreshing page, ordinary condition polling absorbed the delay and the recovery machinery was never exercised; a static interstitial makes the recoverable-condition path real and observable in evidence.

## D012 — CLI input specs from a small registry
**Decision:** `uicap discover --input name=value` maps known names (`member_id`, `account_type`) to typed/sensitive `InputSpec`s from a registry; unknown names become generic string inputs (sensitive when the name matches the redaction list).
**Reason:** In production the calling agent supplies the typed contract; a registry keeps the demo CLI honest without inventing a schema-definition flag language.

## D013 — Gemini as default runtime discovery provider
**Decision:** Discovery is provider-pluggable behind the existing `ModelAdapter` seam via a small factory (`discovery/providers.py`). Google Gemini (official `google-genai` SDK, free tier) is the default provider; `gemini-3.6-flash`, selected via `GEMINI_MODEL`, is the runtime model that produced the submitted genuine evidence. The Anthropic adapter remains available via `LLM_PROVIDER=anthropic`. Both providers share one action-tool schema module and one Pydantic validation path (`discovery/action_tools.py`); forced function calling means neither can emit free-form text or code. Genuine evidence capture fails loudly without the selected provider's key and can never fall back to the scripted test double. Replay remains LLM-free regardless of provider (statically tested for both SDKs).
**Reason:** Avoids paid API usage for the runtime run without weakening the architecture: the provider seam was already the design, so this is a substitution, not a redesign. Claude Code / Claude Fable 5 was used for development assistance; the runtime discovery model is Gemini.

## D014 — Runtime values are excluded from every derived artifact field, not just step values
**Decision:** The compiler now builds one set of invocation-specific runtime values per run (sensitive input bindings + all extracted values, including money-format variants) and applies it generically: model-suggested success conditions and derived checkpoints embedding a runtime value are dropped in favor of structural conditions; candidate locator strategies whose identity embeds a runtime value are filtered out (failing loudly if no invocation-independent strategy survives); free-text descriptions are scrubbed. The discovery agent likewise rejects a DONE whose success condition embeds a bound input *or extracted output*, with corrective feedback so the model can propose a stable-UI condition in the same run.
**Reason:** The first genuine Gemini run (disc-81829dead3) proposed `text_present: <extracted balance>` as its success condition; the sensitive-value scanner correctly refused the artifact, exposing that only *input bindings* were being parameterized in derived fields. The scanner is unchanged and remains the backstop; the fix closes the gap upstream for the whole value class, not this one member/balance.

## D015 — Phase 2 target profiles; Northstar retained as regression target
**Decision:** MERIDIAN CORE is added as a second target behind a target-profile
registry (policy factory, error rules, fingerprint, input specs, credential
input names). The local Northstar demo app stays in the repository unchanged as
the regression target, and its tests must keep passing.
**Reason:** The assignment is explicitly an adaptation. Keeping Northstar green
is the evidence that the core was genuinely reusable rather than rewritten.

## D016 — Escalation stays a policy outcome, not a fourth error classification
**Decision:** The error taxonomy remains exactly three-way (`business_outcome`,
`recoverable`, `hard_failure`). MERIDIAN's supervisor-required state is detected
as a normal declared rule; routing it to the human-handoff path is a *policy*
decision (an opt-in list on the artifact's policy block), reusing the existing
`_escalate_step` → `HandoffManager` path.
**Reason:** "What happened" and "who must handle it" are different concerns. The
taxonomy describes the observed state; policy decides authority. Adding a fourth
classification would blur that and change the meaning of every existing rule.

## D017 — No session manager unless MERIDIAN forces one
**Decision:** Sign-on is modelled as an ordinary capability artifact with typed
sensitive inputs bound from the environment by the runner; each capability
artifact carries its own sign-on prefix so runs are hermetic. A dedicated
session-manager module is introduced only if reconnaissance or implementation
shows a concrete need.
**Reason:** Introducing session infrastructure before proving it is necessary
would be architecture for appearance. Reconnaissance confirmed sign-on is a
plain form post and that an expired session is a full re-authentication, which
the existing capability/error-rule seams already express.

## D018 — P1 scope corrected by live reconnaissance
**Decision:** Reconnaissance against the live MERIDIAN application removed two
planned core changes and promoted three others. Parameterized locators (G1) and
step-output value references (G2) are NOT implemented: every MERIDIAN locator
keys on a static identity, member selection is a `navigate` template over a
declared input, and the hidden `_token` is submitted by the form itself.
Structured table extraction (G7) and the observation fixes (G11) were promoted
to required, because share sets are variable per member (30 vs 11 observed) and
the target has zero `id`, `aria-label`, `data-*` or `<label>` attributes.
**Reason:** Implementing G1/G2 without a concrete MERIDIAN requirement would be
speculative generalization; both remain available if a later phase proves them
necessary.

## D019 — Row-relative locators use the existing CSS strategy, not a new kind
**Decision:** MERIDIAN renders no `id`, `aria-label`, `data-*` or `<label>`
attributes, so some regions can only be identified structurally. This is
expressed with the existing `LocatorKind.CSS`, anchored on a label cell's text
(`td.lbl:text-is("Name:") + td`), which Playwright resolves natively. No new
locator strategy kind was added.
**Reason:** The existing strategy proved sufficient once verified live. Two
findings shaped the form: an unscoped `tr:has(td.lbl:text-is("E-mail:"))`
matched 34 ancestor rows because the target nests tables, and
`tr:has(...) > td:nth-child(2)` selected the wrong cell because several
label/value pairs share one `<tr>`. Anchoring on the label cell and taking the
adjacent cell is content-based rather than positional. Only the balance and
identifier *columns* remain positional (`td:nth-child(n)`), documented in the
profile as a deliberate last resort, since CSS cannot address a table column by
its header.

## D020 — Durable evidence is masked at capture; the caller still gets the value
**Decision:** Screenshots are captured with Playwright `mask=` over
profile-declared regions, so sensitive pixels never reach disk; DOM snapshots
are scrubbed structurally (each masked element's inner markup is replaced)
before the central Redactor applies target-declared patterns. Structured results
returned to the caller are unaffected.
**Reason:** Phase 1 accepted unredacted screenshots because all data was
synthetic and local. MERIDIAN renders a live session id, a per-session
transaction token, member contact details and balances the run never supplied,
and Phase 2 puts that evidence behind a dashboard. Registered runtime values
alone do not cover data the run never touched. Two implementation findings are
load-bearing: region scrubbing must run *before* value redaction (otherwise
redacting a member number inside "Member 100234 - Lovelace, Ada" leaves the
region text unmatched and the name survives), and it must be structural rather
than text-based (inline `<b>` tags and `<select>` options break text matching).

## D021 — Durable Playwright traces are disabled for MERIDIAN
**Decision:** `TargetProfile.durable_traces` gates `start_trace()`. MERIDIAN sets
it False; Northstar keeps Phase-1 tracing unchanged.
**Reason:** The P1 audit extracted a MERIDIAN `trace.zip` and found the sign-on
POST body verbatim (`operator=teller1&password=...`), every `fill` action's
parameter value, unmasked frame JPEGs, and raw DOM resources. Screenshot masking
and DOM redaction act on what the surface writes; nothing in the redaction path
reaches inside Playwright's recorder, and the frame images cannot be masked after
capture. Rather than ship evidence that cannot be sanitised, the target records
none. Redacted JSONL logs, masked screenshots, redacted DOM snapshots, timings
and the structured result remain.

## D022 — The sensitive-value backstop scans run-derived fields only
**Decision:** `_assert_no_sensitive_values` walks the artifact by path and skips
declared vocabulary: parameter names (`contract.inputs[i].name`,
`outputs[i].name`, an `InputValueRef`'s `name`), their registry-authored
descriptions, and `error_rules` in full (produced by the profile's rule factory,
which takes no run input). Every other field stays scanned, and the error now
names the offending path.
**Reason:** MERIDIAN's demo password is the literal word "password", which is
also the parameter name, the value-reference name, and part of the target's own
"Invalid operator ID or password." detector. Scanning the whole serialized blob
made the parameter *name* look like leaked data, so no capability taking
credentials could compile at all. The bound values themselves are still absent
by construction (`InputValueRef` parameterization) and a leak in any value
position is still refused — pinned by `tests/unit/test_sensitive_scan_scope.py`.

## D023 — Known limitation: a credential equal to a form field name
**Decision:** Not worked around. MERIDIAN's password field is `name="password"`,
so its durable locator `stable_attribute name=password` is byte-identical to the
demo credential. The compiler's runtime-value filter therefore drops that
strategy, and a discovery-compiled sign-on artifact keeps only `role_name` and
`label` strategies — neither of which resolves on a target that renders no
`<label>` elements. Verified: such an artifact compiles and then fails replay
with `TARGET_NOT_FOUND` at the password step.
**Reason:** Exempting locator identities from the filter would re-open exactly
the Phase-1 hole D014 closed (a member id embedded in a locator being
persisted), and no string-containment rule can tell a field name from a secret
that happens to be a dictionary word. The canonical sign-on artifact therefore
remains hand-authored until this is resolved; see the P1 audit report.

## D024 — Narrow credential/field-name collision exemption (resolves D023)
**Decision:** `InputSpec` gains `credential: bool = False` (implies `sensitive`).
The compiler's runtime-value filter and final leak scan both gain one narrow,
independently-verifiable exemption: a `stable_attribute` locator strategy with
`attribute="name"` survives when its value exactly equals a declared
credential input's bound value. Scoped deliberately: only that locator kind
and attribute, only exact string equality (never substring containment), only
against `credential=True` inputs — never member numbers or any other
invocation-varying sensitive input, never TEXT/ROLE_NAME/LABEL/CSS locators,
never descriptions/literals/conditions/URLs. The final scan re-derives the
exemption from the artifact itself (kind/attribute/value), independent of how
compilation reached that state, so it cannot be satisfied by intent alone.
A second, related fix: the scan now strips `{declared_input_name}` placeholder
syntax before checking containment, because `_parameterize_text`/`_url_template`
render a bound value as literally `{that_value's_own_name}` — when a
credential's value equals its own name, that placeholder trivially contains
the value as a substring, indistinguishable from a leak without this.
**Reason:** An HTML `name=` attribute is fixed page structure, not rendered
content — unlike accessible text/name, it does not vary with what value is
ever typed into the field. MERIDIAN's password field is `name="password"`,
and the sample app's own published demo credential is also the literal word
"password" — two independent strings colliding, not the locator embedding
invocation-specific identity (the concern D014 exists for). Verified against
the live target: the discovery-compiled sign-on artifact previously failed
replay with `TARGET_NOT_FOUND` at the password step (only `role_name`/`label`
strategies survived, and MERIDIAN renders no real `<label>`/ARIA for them to
resolve against); with this fix it replays successfully end-to-end.
`tests/unit/test_credential_locator_exemption.py` pins both the positive case
and eight negative cases (TEXT/CSS/ROLE_NAME never exempt, `id` attribute not
exempt, non-credential sensitive values in the same locator kind still
rejected, conditions/literals/descriptions never exempt, no `credential_values`
argument means the old strict behavior).

## D025 — Canonical meridian.sign_on is genuinely discovery-generated
**Decision:** `artifacts/meridian/meridian.sign_on.v1.json` is now the direct
output of a real discovery run (Gemini `gemini-3.6-flash`, run
`disc-1d408f679a`) compiled through the unmodified `ArtifactCompiler`, replacing
the hand-authored placeholder from earlier in P1. Verified: deterministic
replay succeeds for both teller and supervisor, and bad credentials return
`business_outcome/BAD_LOGIN` — with zero LLM calls in the replay path.
**Reason:** the assignment requires genuine discovery evidence, not a
hand-authored stand-in, once a real provider key is available. Two findings
from running it for real, both disclosed rather than patched over:
(1) a first attempt recorded no `select` step for `branch` — the model saw the
default option already matched the requested value and didn't interact with
it, so a caller supplying a different branch would silently get MAIN-001
anyway. A second genuine run recorded all four fields, including a real
`select` on branch, and that run's artifact is the one made canonical; the
first is documented, not force-edited. (2) the discovery loop's own
before/after screenshots exposed the operator id in clear text mid-fill — the
existing `screenshot_mask_selectors` covered rendered *state* (status bars,
member records) but not the sign-on form's own credential inputs while being
typed into. Fixed by adding `input[name="operator"]`/`input[name="password"]`
to the MERIDIAN profile's mask selectors (the password field itself was never
at risk — a browser never renders typed characters into a `type="password"`
field). Both the tainted evidence directory and the first artifact were
discarded and regenerated rather than patched, since the goal was a genuinely
clean discovery-generated capability, not a retrofitted one.
`ScriptedMeridianSignOnModel` is kept as an offline regression fixture only
(pipeline-shape coverage without an API call); it is never referenced as, or
substitutable for, discovery provenance — enforced by
`test_meridian_signon_artifact.py::test_artifact_exists_and_validates`
asserting `provenance.discovery_model` names a real provider.

## D026 — Open Share is risky, not irreversible (live-verified distinction)
**Decision:** `meridian_policy()` adds `"open share"` to
`risky_control_patterns` (alongside the existing `"save changes"`). It is not
added to `irreversible_control_patterns`.
**Reason:** Live P2 reconnaissance found the open-share confirmation screen
renders no "IRREVERSIBLE ACTION" banner (unlike the transfer and hold confirm
screens, both verified to render one) and its submit caption is "Open Share",
matching neither existing irreversible pattern. This is a genuine product
distinction the target itself draws: a new share can be closed later, while a
posted transfer or an applied hold cannot. Classifying it risky still routes
it through `require_human_for` by default and keeps it a write-once step in
replay (`effective_risk in (RISKY, IRREVERSIBLE)`), without overstating its
reversibility. Pinned by `tests/unit/test_meridian_risk_patterns.py`.

## D027 — Compiler now sets `StepSpec.internal` from a recorded extract
**Decision:** `ExtractAction` gains `internal: bool = False`, settable by the
discovery model (documented in the tool description and system prompt: use it
when a value is read only to complete the current flow — e.g. confirming a
hidden security/transaction token is present before a write — and must never
become a capability output). `ArtifactCompiler._compile_step` now passes
`internal=action.internal` through to the compiled `StepSpec`.
**Reason:** `StepSpec.internal` and its cross-validation (an internal step can
never source a declared output) were already built in P1
(`tests/unit/test_extract_modes.py`), but nothing in the compiler ever set it
— every recorded extract became a published output regardless of intent. This
blocked the funds-transfer requirement to explicitly observe the per-request
hidden `_token` before posting without leaking it into the contract. The
model, not a target-specific heuristic, declares intent (consistent with how
`done`/`request_human` already work); the compiler and schema still enforce
the boundary structurally regardless of what the model claims. Generalizable
to any future target with a similar hidden-token flow, not MERIDIAN-specific.
Pinned by `tests/unit/test_compiler.py::test_compile_passes_internal_flag_through_and_excludes_it_from_outputs`.

## D028 — Observation inventory gains bordered `<table>` elements
**Decision:** `_INVENTORY_SELECTOR` now includes `table[border]:not([border="0"])`;
`_element_kind` maps a `<table>` tag to kind `"table"`; `candidate_strategies`
gives a table a single CSS strategy `table[border="N"]` when the element
carries a `border` attribute.
**Reason:** MERIDIAN's variable-length data tables (a member's shares, a
last-name search's results) carry no `id`, `name`, `class`, or `<label>` —
only the legacy `border` attribute distinguishes them from layout tables
(verified live: every layout/form table on this target is `border="0"`, every
data table `border="1"`). Without this, `build_inventory` never enumerated a
`<table>` at all, so discovery had no `ref` to extract with — table
extraction (`extract_mode="table"`, G7, already implemented at the binder
level in P1) was unreachable from a genuine discovery run. Scoped narrowly to
non-zero-border tables so ordinary layout tables never clutter the
inventory. Not MERIDIAN-specific: any legacy bordered-table target benefits.
Pinned by `tests/unit/test_observation_meridian.py`.

## D029 — Bounded backoff and pacing for transient Gemini provider failures
**Decision:** `GeminiModelAdapter` now (a) proactively paces consecutive calls
at least `_MIN_CALL_INTERVAL_S` (13s) apart, and (b) reactively retries, up to
`_MAX_RATE_LIMIT_RETRIES` (4) times each: a `429` (RESOURCE_EXHAUSTED),
sleeping the API's own suggested `retryDelay` (parsed from the error text) or
a 20s default; and a `503` (UNAVAILABLE, "experiencing high demand"), sleeping
a fixed 15s. Every other error still propagates immediately — this is not a
general retry-everything wrapper.
**Reason:** Live P2 discovery runs hit three distinct real failures in one
session, all confirmed against the actual API, none assumed: the free tier's
`GenerateRequestsPerMinutePerProjectPerModel-FreeTier` cap (5/minute/model);
the model pinned by D013's separate 20/day cap, already exhausted by earlier
sessions; and a transient 503 on two different, previously-untouched fresh
models back to back. A multi-turn discovery run makes one model call per
step; any of these unhandled mid-run previously crashed the whole session
outright, with no path to recover short of restarting from step 1. The
proactive pacing floor exists because a burst of calls under ~1s apart
(observation/decision turns are sometimes that fast) immediately tripped the
per-minute cap and fell into escalating reactive backoff — pacing avoids
discovering the limit reactively in the common case. This is ordinary
provider-robustness engineering ("centralize timeouts/retry policy" per
CLAUDE.md), not MERIDIAN-specific — any caller of the free tier hits the same
limits. Because several models' daily quotas were exhausted by testing within
the same session, P2-P5 discovery runs are spread across whichever available
Gemini model has headroom at the time (via `GEMINI_MODEL`); provenance on
every P2-P5 artifact names the actual model used for that run. Pinned by
`tests/unit/test_providers.py` (`test_gemini_adapter_survives_a_transient_rate_limit`,
`test_gemini_adapter_gives_up_after_bounded_retries`,
`test_gemini_adapter_does_not_retry_non_rate_limit_errors`,
`test_gemini_adapter_paces_consecutive_calls`,
`test_gemini_adapter_survives_a_transient_server_error`,
`test_gemini_adapter_does_not_retry_non_503_server_errors`).

## D030 — Runtime-value containment is checked in both directions
**Decision:** `ArtifactCompiler._contains_runtime_value` and
`DiscoveryAgent._embeds_runtime_value` (D014's two enforcement points) now
check containment both ways: a runtime value found inside the candidate text
(the original check), OR the candidate text found inside a runtime value.
**Reason:** The genuine `meridian.member_inquiry` discovery run (Gemini
`gemini-3.1-flash-lite`) proposed `text_present: "Lovelace, Ada"` as its
success condition — a member's name, quoted directly from inside the row it
had just extracted via the new table-extraction path (D028,
`extract_mode='table'`). The extracted "value" there is a JSON blob covering
every result row, not a short scalar; the old check only tested whether a
known runtime value was a substring of the condition text, which holds for a
short balance quoted in a longer sentence but never holds when the condition
is a short fragment quoted from inside a much larger blob. The artifact still
compiled — silently, because the one-directional check found nothing — with a
success condition that would only ever be true for member 100234, exactly the
class of bug D014 exists to prevent, now reachable through the output shape
D028 introduced. This is a strict generalization of the existing filter, not
new policy: the compiler already refuses to persist a runtime-value-bearing
condition instead of the caller silently receiving an invocation-locked
artifact. Pinned by `tests/unit/test_leak_regression.py`
(`test_condition_sourced_from_inside_a_table_extract_is_also_caught`,
`test_verify_done_rejects_condition_sourced_from_inside_a_table_extract`).
Discovery was re-run after this fix to produce the canonical artifact.

## D031 — Table-extract output type is compiler-forced to `json`
**Decision:** `ArtifactCompiler._compile_step` now sets a compiled extract
step's `output_type` to `"json"` whenever `extract_mode == "table"`,
overriding whatever `output_type` the model proposed. `OutputSpec.type` is
read from the compiled step (single source of truth) rather than re-read
from the raw recorded action, so the contract and the step never disagree.
**Reason:** The same genuine `meridian.member_inquiry` run proposed
`extract_mode="table"` with `output_type="string"`. `_TABLE_ROWS_JS` always
serializes a table to JSON rows regardless of what the model calls the
output type — that is a structural fact about the extraction mechanism
(`playwright_web.py::_extract`, mode `"table"`), not a model decision, so it
should not be model-controlled. Left uncorrected, a caller declared
`output_type="string"` would receive an opaque JSON-in-a-string instead of
parsed rows through `binder.coerce_output`, defeating the purpose of
structured table extraction (G7) for exactly the capability it was built for.
Pinned by `tests/unit/test_compiler.py::test_compile_forces_json_output_type_for_table_extracts`.

## D032 — Hidden form fields are observable, never actionable
**Decision:** `build_inventory`'s visibility gate now also admits
`<input type="hidden">` elements (previously excluded, like every element
with zero layout box). `_element_kind` gives them a distinct kind, `"hidden"`,
never reused by any clickable/fillable kind.
**Reason:** The first genuine `meridian.funds_transfer` discovery attempt
reached the review screen and the model correctly tried to follow the P3
instruction to extract the hidden `_token` field's current value — and
immediately requested human intervention, reporting that no hidden token
element appeared in INTERACTIVE ELEMENTS at all. It was right: the visibility
check (`offsetWidth || offsetHeight || getClientRects().length`) is exactly
zero for a hidden input by definition, so `D027`'s `internal` extract flag had
no element to ever target on ANY hidden-token form, on MERIDIAN or elsewhere.
Scoped narrowly to `type="hidden"` specifically (not a general "show
everything" relaxation) so a person or model still can never click or type
into something no one could see; only reading its current value is possible
for exactly this element type, keeping D027's internal/output boundary the
only decision left to the model. Pinned by `tests/unit/test_observation_meridian.py`
(`test_hidden_token_field_maps_to_hidden_kind`,
`test_hidden_field_gets_a_stable_attribute_strategy_but_no_role_name`,
`test_element_info_script_treats_hidden_inputs_as_visible`).

## D033 — New rule: OPEN_SHARE_VALIDATION_FAILED
**Decision:** Added an error rule matching the text "The request could not be
validated:", classified `BUSINESS_OUTCOME`, code `OPEN_SHARE_VALIDATION_FAILED`.
**Reason:** Verified live: opening a Certificate below its $500 minimum
deposit renders "OPEN NEW SHARE — The request could not be validated: —
Certificates require a minimum opening deposit of $500.00." — wording
distinct enough from the existing `TRANSACTION_REJECTED` rule ("The
transaction could not be validated:", "transaction" not "request") that it
matched no declared rule and fell through to an unclassified hard failure. A
field/amount validation rejection belongs in the business-outcome family like
every other one already declared, not treated as an infrastructure failure.
Pinned by `tests/unit/test_meridian_error_rules.py::test_open_share_below_minimum_deposit_is_business_outcome`.

## D034 — meridian.place_hold declares SUPERVISOR_REQUIRED as escalate_on_codes
**Decision:** After genuine discovery (as supervisor, so the recorded run
itself never hits the teller-restricted state), `meridian.place_hold`'s
`policy.escalate_on_codes` is set to `["SUPERVISOR_REQUIRED"]`.
**Reason:** `escalate_on_codes` is never populated by generic compilation
(`ArtifactCompiler.compile` passes no value, so it defaults to `[]`) — it is
exactly the per-capability, human-authored policy decision D016 describes:
"who must handle it" is a product decision distinct from "what happened."
Sign-on's own artifact (D025) explicitly declares `escalate_on_codes: []`
with the same reasoning inverted (it has no supervisor-gated step). Setting
it here is not hand-authoring capability logic — no step, locator, or
condition is touched — it is the one policy flag the schema documents as an
artifact-level decision no discovery run makes for itself.

## D035 — Observation gains read-only result cells; confirmation_number output remains blocked (root cause identified, not yet fixed)
**Decision:** `observation.py`'s inventory selector now also enumerates
`td.lbl + td:not(:has(input, select, textarea, a, button))` — the same
label/value row pattern already relied on for screenshot masking (D019/D020:
"Member:", "From:", "Confirmation:", …), scoped away from any cell that
itself wraps a form control (already reachable through that control's own
selector) so it never produces a duplicate element. `candidate_strategies`
gives such a cell a CSS strategy `td.lbl:text-is("{label}:") + td`, gated on
a new `label_from_lbl_cell` flag so it only fires for a genuine `.lbl`-class
label sibling, never for the pre-existing generic label fallback. Pinned by
new tests in `tests/unit/test_observation_meridian.py`. Full offline suite
re-run after this change: 274 passed, 15 skipped (was 269; +5 new tests),
confirming no Northstar regression.

**Reason this was necessary:** `meridian.funds_transfer` does not expose
`confirmation_number` as a typed output (`BUILD_STATUS.md` P3, `08_DEFINITION_OF_DONE.md`).
Inspecting the genuine discovery run behind the canonical artifact
(`disc-09032250da`) showed the model reached the `TRANSACTION COMPLETE` page
and declared `done` without ever extracting the confirmation number — because
the inventory selector required an `id` attribute on any `td`/`th`, and
MERIDIAN's confirmation row (`<td class="lbl">Confirmation:</td><td>…</td>`)
carries none. There was no element ref for the model to target at all.

**What was actually tried, in order, and why the artifact was NOT replaced:**
1. A fresh discovery run with a strengthened goal succeeded procedurally
   (`disc-c0bfce3b6c`) after one genuine live $1 transfer (member 100234,
   `100234-S0001-12` → `100234-MMKT-21`) — the new "cell" element was seen and
   `extract(internal=false, output_name=confirmation_number)` succeeded — but
   the model then re-issued the identical extract four more times instead of
   calling `done`, hitting `max_steps`. No artifact results from a run whose
   `success` flag is false (`ArtifactCompiler.compile` refuses it).
2. A second, explicitly authorized final attempt with a sharper goal
   ("extract exactly once, your next call MUST be done") succeeded end to end
   (`disc-887e90fe6a`, one further genuine live $1 transfer, same member,
   `100234-S0001-12` → `100234-MMKT-21`), compiled cleanly (genuine
   `gemini:gemini-3.5-flash-lite` provenance, `confirmation_number` present in
   `contract.outputs`, no leaked runtime values), and was provisionally made
   canonical.
3. Replay verification (required before any artifact replacement) then failed
   live: `EXECUTION_ERROR` at the confirmation-extract step, `"could not
   extract via mode 'value'"`. Root cause, confirmed with an offline,
   zero-live-risk test (`page.set_content` + `'value' in el` against a plain
   `<td>`): a `<td>` has no `.value` DOM property at all — `extract_mode:
   "value"` (evaluating `el => ('value' in el) ? el.value : null`) can only
   ever work on a real form control (`input`/`select`/`textarea`), never on a
   display cell. The compiled step faithfully recorded the model's declared
   `extract_mode: "value"` (matching this task's own goal wording, which
   wrongly told the model to use `value` mode for the confirmation cell by
   analogy with the hidden `_token` step) — so replay, which correctly passes
   the declared mode through, failed exactly as it should have.
4. That the *discovery* run nonetheless reported the extraction as
   successful is a second, independent, pre-existing bug: `DiscoveryAgent._to_executable`
   (`discovery/agent.py`) builds the extract `ExecutableAction` without
   forwarding `action.extract_mode` at all (contrast
   `ReplayEngine._to_executable`, `replay/engine.py`, which does). Every
   discovery-time extraction — this one included — silently executes in
   `PlaywrightWebSurface._extract`'s default `"text"` mode regardless of what
   the model declares, which happens to read the right thing for a `<td>`
   (`.innerText`) but is not what the recorded step says it did. This is a
   genuine, confirmed defect in shared discovery-loop code, not a MERIDIAN
   quirk and not model flakiness — it just never surfaced before because no
   earlier `extract` step's *declared* mode differed in observable effect from
   `"text"` (the internal `_token` step's extracted content is never checked
   for correctness, only that it is non-empty).

Per the resolved-gap criteria, the artifact was reverted to its original,
pre-existing state (`outputs: []`, provenance `disc-09032250da`) rather than
kept: it compiled but did not replay deterministically. No further live
transfer was attempted after the second, and the run was not hand-patched to
paper over the `extract_mode` mismatch, per explicit instruction.

**To resolve in a future session (no further live transfer needed to reach
the actual fix):** (a) fix `DiscoveryAgent._to_executable` to forward
`extract_mode` for `ExtractAction`, so discovery genuinely executes what it
records; (b) correct the discovery goal to request `extract_mode="text"` (not
`"value"`) for the confirmation cell — `value` mode remains correct only for
the hidden `_token` field, which is a real form control. With both in place,
one clean discovery run should compile *and* replay on the first attempt.
Two genuine, minimal ($1, same-member, internal) live transfers were
performed against the shared sandbox in the course of this investigation
(`disc-c0bfce3b6c`, `disc-887e90fe6a`); both are real, already-settled
transactions, not test doubles, and are documented here rather than hidden.

## D036 — P6-P8: one CapabilityService, no second invocation path, credentials never a caller concern
**Decision:** `api/service.py::CapabilityService` is the single place that
turns "invoke capability X with these arguments" into a deterministic replay
run. Both the HTTP routes (`api/routes.py`) and the chatbot
(`chatbot/router.py`) call it directly, in-process — the chatbot does not
make an HTTP call to its own server. `api/runner.py` is the only module
anywhere under `api/`, `chatbot/`, or `dashboard/` allowed to import a
surface or `ReplayEngine` (statically pinned by
`tests/unit/test_chatbot_no_playwright_path.py`, via `ast`-parsed imports
rather than a text search, since several docstrings *describe* not using
Playwright). Every MERIDIAN artifact's contract declares `operator_id`,
`password`, and `branch` as required inputs (each capability carries its own
sign-on prefix per D017); the API/chatbot layer excludes exactly these three
names from the public schema (`schemas.SERVER_SUPPLIED_INPUTS`) and injects
them at invoke time from `MERIDIAN_TELLER_ID`/`MERIDIAN_TELLER_PASSWORD`/
`MERIDIAN_BRANCH` (the same env vars the existing live integration tests
already read) — a caller can never supply, override, or see them. A request
naming any of those three, or `human_approved`, is rejected
(`InvalidArgumentsError`, HTTP 400) before the catalog lookup's artifact is
even bound to input, let alone before a browser launches. A contract-invalid
business argument (bad pattern, missing required field) is instead resolved
via `binder.validate_and_bind` called directly in the service — the exact
check `ReplayEngine.replay` performs first — so it returns a structured
`FailureResult(code=INVOCATION_INVALID)` with zero side effects (no evidence
directory, no operator-console port bind, no browser), not merely "before
the browser launches."
**Reason:** "The caller must not need to know MERIDIAN UI details" (docs)
extends naturally to "the caller must not need to know MERIDIAN has a
sign-on step at all" — every one of the 7 capabilities embeds it, so hiding
it is what makes the API's inputs match what a member-servicing task
actually varies per call. Sharing one service object rather than routing the
chatbot through its own HTTP client avoids a redundant network hop in a
single-process demo while still guaranteeing, structurally, that there is
exactly one invocation path — the thing "must not create a second Playwright
execution path" actually requires.

## D037 — P7 chatbot NLU is deterministic regex/keywords, not a model call
**Decision:** `chatbot/nlu.py` maps a request to a capability id and typed
slots with regex/keyword matching — no LLM call. Multi-turn slot-filling
state is an in-memory per-session dict (`chatbot/session.py`), mirroring how
the existing `InterventionStore` is already in-memory-only for a demo-scale
system.
**Reason:** P7's own instructions are explicit — "thin," "do not build a
sophisticated agent framework," "use the simplest existing model/provider
integration" — and CLAUDE.md ranks "genuine LLM discovery loop" below
artifact/replay/handoff/safety quality already; chatbot NLU is further still
from that priority list. A regex mapper is exhaustively unit-testable
offline (`tests/unit/test_chatbot_nlu.py`), with zero API cost or network
flakiness in the two demo-prioritized requests (balance, transfer) and
representative coverage of the other four caller-facing capabilities.
Swapping `detect_capability`/`extract_slots` for a structured-output call to
the same Gemini/Anthropic adapters discovery already uses is a natural,
scoped future improvement — the chatbot loop in `router.py` only depends on
their function signatures, not on how they're implemented — and is
documented rather than built, per the instruction to document
nonessential enhancements and continue.

## D038 — P8 dashboard is read-only; no invoke form
**Decision:** `dashboard/` renders the capability catalog and run
history/detail (inputs redacted per contract sensitivity, structured result,
step/policy events, masked screenshots, redacted DOM snapshots) with no form
anywhere on any page (pinned by
`test_dashboard_router.py::test_catalog_page_has_no_mutating_form`).
Invocation happens via the chatbot or `POST /api/capabilities/{id}/invoke`
(discoverable at `/docs`), not a dashboard control.
**Reason:** "The dashboard must not introduce browser-control or
policy-bypass endpoints" is trivially, structurally true of a page that
issues no POSTs at all — the safest way to satisfy it, not merely the
easiest. Evidence files are served read-only through the same traversal-safe
`RunStore.evidence_file_path` (rejects any resolved path outside the run's
own directory; pinned in `test_run_store.py`); DOM snapshots are served as
`text/plain` regardless of their `.html` extension so a redacted capture is
never re-executed as a live page inside the dashboard's own browser context.
