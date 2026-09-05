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
