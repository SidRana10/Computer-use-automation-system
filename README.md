# UI Capabilities — discover once, replay deterministically

A small end-to-end computer-use system for legacy back-office applications
that have no API. An LLM **discovers** how to complete a natural-language
goal on a live UI once; the successful run is **compiled** into a typed,
versioned, parameterized **capability artifact**; production execution is a
**deterministic replay** of that artifact with **zero LLM decisions**,
explicit error/outcome handling, configurable safety guardrails, and a
**same-session human handoff** path for risky or stuck situations.

> The model discovers. The artifact is the capability. Deterministic replay is
> production execution.

Two targets exercise the same core:

- **Phase 2 — MERIDIAN CORE** (`https://web-sample.interface-hiring.com`), a
  remote legacy credit-union servicing UI. **This is the current phase — read
  this section first.**
- **Phase 1 — Northstar**, the local synthetic demo app kept as the
  regression baseline. See [Phase 1](#phase-1--northstar-regression-baseline)
  below; its tests still pass unchanged.

---

## Phase 2 — MERIDIAN CORE (start here)

Seven MERIDIAN capabilities (`artifacts/meridian/*.json`) were each produced
by a genuine Gemini-driven discovery run against the live target, then
replay-verified with zero LLM calls. A capability API, a thin deterministic
chatbot, and a read-only dashboard sit on top of the same replay path — the
caller never needs to know MERIDIAN is a browser UI at all.

### Architecture at a glance

```text
Browser chat UI ─┐
                  ├─▶ CapabilityService ──▶ CapabilityRunner ──▶ ReplayEngine (no LLM)
POST /api/...  ───┘         │                      │                   │
                             │                      │                   ▼
                    validates args,          same PolicyEngine   PlaywrightWebSurface
                    injects operator          + Redactor +       (headed Chromium, stays
                    credentials server-       HandoffManager     alive across handoff)
                    side, rejects any                │                   │
                    caller-supplied ones              ▼                   ▼
                                             Operator console      MERIDIAN CORE
                                             (Take Control /       (live remote target)
                                              Resume / Abort)

GET /dashboard/*  ──▶ RunStore ──▶ evidence/runs/<run_id>/  (redacted logs,
                                    masked screenshots, redacted DOM, result.json)
```

- `src/ui_capabilities/api/` — `CapabilityCatalog` (reads the 7 committed
  artifacts), `CapabilityService` (validates input, injects credentials,
  rejects server-supplied/`human_approved` fields before touching the
  catalog), `CapabilityRunner` (the *only* module here that imports a
  surface or the replay engine), `RunStore` (per-run `result.json`), routes.
- `src/ui_capabilities/chatbot/` — deterministic regex/keyword NLU
  (`nlu.py`), multi-turn slot filling, calls the identical
  `CapabilityService` the HTTP routes use.
- `src/ui_capabilities/dashboard/` — read-only Jinja2 pages: capability
  catalog, run history, run detail. No invoke form, no browser-control route.
- `src/ui_capabilities/targets/meridian.py` — the MERIDIAN target profile:
  policy, error rules, fingerprint, credential input names, screenshot mask
  selectors, redaction patterns.
- `artifacts/meridian/*.v1.json` — the 7 committed capabilities.
- `evidence/meridian/runs/` — committed discovery/replay evidence for
  MERIDIAN (see [Backup evidence](#backup-evidence-if-the-live-network-fails)).

### Requirements / setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
playwright install chromium
cp .env.example .env
```

Then edit `.env`:

- A Google Gemini API key (free tier: https://aistudio.google.com/apikey) —
  only needed to run a *new* discovery. Replay, the API, the chatbot, and the
  dashboard never call an LLM.
- The MERIDIAN demo operator credentials published in the Phase-2 assignment
  (`phase2_build_pack/03_PHASE2_REQUIREMENTS.md`): one teller account, one
  supervisor account. These are the sample application's own published demo
  credentials, not real customer/institution secrets.

### Required environment variables

All read from `.env` (gitignored; `.env.example` ships with every name
blank/placeholder — no real values are committed).

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `gemini` (default) or `anthropic` — discovery only |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | discovery provider (default provider) |
| `ANTHROPIC_API_KEY` / `DISCOVERY_MODEL` | optional alternative discovery provider |
| `MERIDIAN_BASE_URL` | `https://web-sample.interface-hiring.com` |
| `MERIDIAN_TELLER_ID` / `MERIDIAN_TELLER_PASSWORD` | teller demo credentials — injected server-side at invoke time, never accepted from a caller |
| `MERIDIAN_SUPERVISOR_ID` / `MERIDIAN_SUPERVISOR_PASSWORD` | supervisor demo credentials — used for the sign-on/escalation discovery runs and live tests, not by the caller-facing API |
| `MERIDIAN_BRANCH` | e.g. `MAIN-001` |
| `OPERATOR_BASE_URL` | operator console address, default `http://127.0.0.1:8002`; the API/chatbot spin up a fresh operator console here per live invocation |
| `EVIDENCE_DIR` / `ARTIFACT_DIR` | default `evidence` / `artifacts` |

`operator_id`, `password`, and `branch` are declared inputs on every MERIDIAN
capability's contract (each embeds its own sign-on), but the API/chatbot
layer excludes exactly those three names from what a caller may supply
(`api/schemas.py::SERVER_SUPPLIED_INPUTS`) and injects them itself from the
env vars above — a caller only ever supplies the business arguments
(`member_number`, `amount`, …).

### Start the capability API + chatbot + dashboard

```bash
uicap serve --host 127.0.0.1 --port 8003
```

One FastAPI process, one event loop, in-process routers — no queues, no
extra services (`src/ui_capabilities/api/app.py`).

### Access each UI

| UI | URL |
|---|---|
| Chatbot (browser chat page) | http://127.0.0.1:8003/chatbot/ |
| Chatbot message API | `POST http://127.0.0.1:8003/chatbot/message` |
| Dashboard (capability catalog, run history/detail) | http://127.0.0.1:8003/dashboard |
| Capability API + interactive docs | http://127.0.0.1:8003/api/capabilities, http://127.0.0.1:8003/docs |
| Operator console (opened automatically per live invocation) | http://127.0.0.1:8002 |

### Discovery against MERIDIAN

Runs a genuine Gemini-driven discovery session (headed browser opens so you
can watch) against a **read-only** capability, so no approval gate is hit:

```bash
uicap discover \
  --app meridian \
  --target https://web-sample.interface-hiring.com \
  --goal "Look up member 100234 by number and report their name and status." \
  --capability-id meridian.member_inquiry \
  --input operator_id="$MERIDIAN_TELLER_ID" \
  --input password="$MERIDIAN_TELLER_PASSWORD" \
  --input branch="$MERIDIAN_BRANCH" \
  --input search_mode=number \
  --input search_value=100234 \
  --output /tmp/demo_member_inquiry.json
```

Writing to `/tmp/...` avoids overwriting the committed canonical artifact.
The compiled output's `provenance.discovery_model` names the real model that
produced it. A risky/irreversible capability (transfer, hold, open share,
update member) would pause discovery at the confirm step for human approval
via the operator console, exactly like replay does — see
[Demo 2](#demo-2--successful-transaction-funds-transfer).

### Replay a recorded capability (no LLM)

```bash
uicap replay \
  --artifact artifacts/meridian/meridian.get_member_balances.v1.json \
  --input operator_id="$MERIDIAN_TELLER_ID" \
  --input password="$MERIDIAN_TELLER_PASSWORD" \
  --input branch="$MERIDIAN_BRANCH" \
  --input member_number=100234
```

The target profile (policy, error rules, redaction) is derived automatically
from the artifact's `target.app_id`. Zero LLM calls, enforced by construction
and by `tests/unit/test_no_llm_in_replay.py`.

### Invoke a capability through the API

```bash
curl -s http://127.0.0.1:8003/api/capabilities | python3 -m json.tool

curl -s -X POST http://127.0.0.1:8003/api/capabilities/meridian.get_member_balances/invoke \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"member_number": "100234"}}' | python3 -m json.tool
```

`operator_id`/`password`/`branch` are injected server-side; supplying any of
them (or `human_approved`) in the request body is rejected with HTTP 400
before the catalog is even touched. The run then appears at
`GET /api/runs` and in the dashboard.

### Live demo script

Run `uicap serve` first (above). Three short scenes, in order.

#### Demo 1 — successful read (chatbot → API → replay → dashboard)

1. Open http://127.0.0.1:8003/chatbot/ and send:
   ```
   Check the balances for member 100234
   ```
   (This exact phrase already ran successfully live during P6–P8
   verification — run `api-645b4c28d7`.) The chatbot's regex NLU matches
   "balance" → `meridian.get_member_balances`, extracts `member_number=100234`
   from the message, and calls the same `CapabilityService` the HTTP route
   uses — no second invocation path.
2. The reply names the run id and share count. Open
   http://127.0.0.1:8003/dashboard/runs to see it, then the run's own detail
   page for the structured result, step timeline, and masked screenshot.

#### Demo 2 — successful transaction (funds transfer)

Uses the existing validated $1 internal-transfer path
(member `100234`, `100234-S0001-12` → `100234-MMKT-21`, per `DECISIONS.md`
D035) — the smallest real, already-rehearsed movement on the shared sandbox.

```bash
curl -s -X POST http://127.0.0.1:8003/api/capabilities/meridian.funds_transfer/invoke \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"member_number": "100234", "from_share": "100234-S0001-12", "to_share": "100234-MMKT-21", "amount": "1.00", "memo": "P9 demo"}}'
```

This call blocks: the artifact reaches MERIDIAN's review screen, observes the
hidden per-request `_token` internally (never published), and policy pauses
before the irreversible "post" click.

1. Open http://127.0.0.1:8002 (the operator console `CapabilityRunner` just
   started for this invocation) and click **Take Control**.
2. In the same headed browser window MERIDIAN opened, click the post/confirm
   control yourself.
3. Back in the console, click **Resume**. The engine re-observes, verifies
   the completion checkpoint, and the blocked curl call above returns
   `status: success`.

Known limitation, intentionally not worked around here: the result's
`outputs` is empty — `confirmation_number` is not a typed output (D035). The
completed transfer is directly visible on the MERIDIAN confirmation page and
in the run's screenshot/DOM evidence; it is just not surfaced as a structured
field. Do not re-run this beyond one rehearsal — it is a real, settled
transaction against a shared sandbox each time.

#### Demo 3 — escalation (teller → supervisor Place Hold)

**Do not re-run this live** — a genuine hold was already applied to member
100234's share in run `rep-2b1dd06224`, and repeating it would needlessly
mutate more shared state for a rehearsal. Walk through the canonical evidence
instead:

```bash
cat evidence/meridian/runs/rep-2b1dd06224/run.jsonl | python3 -m json.tool 2>/dev/null | less
cat evidence/meridian/runs/rep-2b1dd06224/interventions.json
open evidence/meridian/runs/rep-2b1dd06224/screenshots/intervention_s13_click.png
open evidence/meridian/runs/rep-2b1dd06224/screenshots/resume_int-a712876a.png
```

The event log shows the arc end to end: a teller-signed-on replay reaches the
hold step, `policy_escalation` fires with `code: SUPERVISOR_REQUIRED`
(`meridian.place_hold`'s artifact-level `escalate_on_codes`, D034) —
`meridian.place_hold`'s own discovery run was performed *as* a supervisor
precisely so this restricted state is never bypassed. Control transfers to
`HUMAN`, the supervisor completes the gated step in the same live browser
session, control returns to `AUTOMATION`, the engine re-verifies, and a
*second* intervention fires for the still-irreversible "apply hold" click
(`HUMAN_APPROVAL_REQUIRED`) before `replay_succeeded`. Two independent gates,
both real. (This run's evidence directory does not show up in the dashboard —
the dashboard only indexes API/chatbot-invoked runs with a `result.json`,
per `RunStore`; CLI/script runs like this one are read directly from
`evidence/meridian/runs/`.)

### Run tests

```bash
pytest -q
```

328 passed, 15 skipped, no LLM API calls, no live network traffic. The 15
skips are the MERIDIAN live-network tests below.

### Live MERIDIAN tests (opt-in)

Two integration test files hit the real MERIDIAN target and are skipped by
default:

```bash
MERIDIAN_LIVE=1 \
MERIDIAN_TELLER_ID=... MERIDIAN_TELLER_PASSWORD=... \
MERIDIAN_SUPERVISOR_ID=... MERIDIAN_SUPERVISOR_PASSWORD=... \
MERIDIAN_BRANCH=MAIN-001 \
pytest tests/integration/test_meridian_signon.py tests/integration/test_meridian_exceptional_states.py -q
```

These exercise: teller/supervisor sign-on, bad login, and all six `?inject=`
exceptional states (validation/notfound/permission/timeout/maintenance/
server) plus natural insufficient-funds/invalid-email/teller-attempts-hold/
unrecognized-value cases — all classified against the live target, not
simulated.

### Known limitations

- **`meridian.funds_transfer` has no typed `confirmation_number` output**
  (D035, `DECISIONS.md`). Root-caused, not silently patched: discovery's
  `extract_mode` isn't forwarded to the executed action
  (`DiscoveryAgent._to_executable`), so a discovery run can report an
  extraction as successful without it actually reading what it declared.
  Fix is scoped in `DECISIONS.md` D035; deliberately not applied in P9
  (docs/evidence-only phase).
- **`meridian.member_inquiry`'s table output can carry a duplicate header
  row.** The static table serializer (`playwright_web.py::_TABLE_ROWS_JS`)
  treats the first row as a header when it looks like one; on MERIDIAN's
  markup this occasionally duplicates that row as the first data row too.
  The data itself is correct — one extra row, not corrupted values. Not
  fixed in P9 per instruction.
- **Chatbot NLU is deterministic regex/keywords, not a model call** (D037).
  Intentionally thin per the P7 instruction; swapping in a structured-output
  LLM call is a documented, scoped future change behind the same
  `detect_capability`/`extract_slots` signature.
- **Execution is serialized.** `CapabilityRunner` holds one lock; two
  concurrent live invocations queue rather than run in parallel — correct
  for one shared headed browser/operator console, a real limit for
  multi-caller load.
- **No cross-tenant canonicalization beyond the vendor-family/override
  design** described in `REPORT.md` §4 — not implemented for a second
  tenant, only designed for one.

### Backup evidence (if the live network fails)

All committed under `evidence/meridian/runs/`; no live network needed to
inspect any of them.

| Scenario | Run id | What it shows |
|---|---|---|
| Successful balance read | `evidence/runs/api-645b4c28d7` (also `api-4c95f56f66`, `api-60d17ba0b6`) | real API/chatbot/dashboard invocations of `meridian.get_member_balances` for member 100234, `result.json` + redacted `run.jsonl` + masked screenshot |
| Successful transaction / review→post | `evidence/meridian/runs/disc-887e90fe6a` | genuine live $1 transfer reaching MERIDIAN's TRANSACTION COMPLETE page (discovery evidence — see D035 for why this isn't also the canonical replay artifact) |
| Supervisor escalation | `evidence/meridian/runs/rep-2b1dd06224` | teller→supervisor Place Hold: `policy_escalation` (`SUPERVISOR_REQUIRED`) → intervention → human step → resume → second irreversible-approval gate → `replay_succeeded` |
| Exceptional state | `evidence/meridian/runs/exc-permission-098b61` (also `exc-notfound-53171f`, `exc-timeout-0691a3`, `exc-maintenance-6de384`, `exc-server-06a05b`, `exc-validation-cc1ab8`) | one of the six live `?inject=` states classified correctly, with screenshot + redacted DOM snapshot |

---

## Phase 1 — Northstar (regression baseline)

The original submission target: a local synthetic credit-union servicing
console (`demo_app/`). Kept unchanged and green as proof the core is
genuinely reusable, not rewritten for MERIDIAN. Discovery is
provider-pluggable behind one adapter seam: **Google Gemini is the default
provider, and `gemini-3.6-flash` (free tier) is the runtime model used for
the submitted genuine evidence** — set via `GEMINI_MODEL`, which
`.env.example` ships. Anthropic Claude remains available via
`LLM_PROVIDER=anthropic`. Development of this repository was AI-assisted
(Claude Code / Claude Fable 5); that is a development tool, distinct from the
runtime discovery provider. Deterministic replay invokes no LLM of any kind.

### Architecture at a glance

```text
CLI (uicap)
   |          discovery                          replay
   v                                               v
DiscoveryAgent --(one structured action/turn)-- ReplayEngine  (no LLM here)
   |   ^                                           |
   |   | LLM provider (Gemini default | Anthropic) |
   |   |   forced function calling, strict tools   |
   |   +--- screenshot + semantic inventory        |
   +---------------------+-------------------------+
                         v
                   PolicyEngine   (allowlists, risk classes, human approval)
                         v
                  SurfaceAdapter  (protocol)
                         v
              PlaywrightWebSurface (headed Chromium; stays alive across handoff)
                         v
        Northstar Credit Union demo app (synthetic, local, FastAPI/Jinja)

DiscoveryAgent -> Recorder -> ArtifactCompiler -> artifacts/*.json
any block/risk -> HandoffManager -> InterventionStore -> Operator Console (8002)
everything     -> RunLogger/EvidenceManager -> evidence/runs/<run_id>/ (JSONL, screenshots, traces)
```

- `src/ui_capabilities/models/` — typed schemas: actions, artifact, conditions, results, interventions
- `src/ui_capabilities/discovery/` — agent loop, provider factory + Gemini/Anthropic adapters, scripted test doubles, recorder, compiler
- `src/ui_capabilities/replay/` — binder, error classifier, bounded recovery, replay engine (no model client)
- `src/ui_capabilities/policy/` — allowlist policy engine + central redactor
- `src/ui_capabilities/handoff/` — control-owner state machine, intervention store, operator console
- `src/ui_capabilities/surfaces/` — SurfaceAdapter protocol, Playwright implementation, locator resolver
- `demo_app/` — the fictional target application (all data synthetic)

### Prerequisites

- Python 3.12
- Playwright Chromium (installed below)
- A Google Gemini API key (free tier: https://aistudio.google.com/apikey) —
  **only** for the genuine discovery run; tests and replay never call any LLM
  API. Optionally an Anthropic key instead (`LLM_PROVIDER=anthropic`).

### Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
playwright install chromium
cp .env.example .env   # then put your GEMINI_API_KEY in .env (never committed)
```

Troubleshooting: if `import ui_capabilities` fails after an editable install,
your environment may be skipping `.pth` files (some macOS setups mark them
hidden, which Python 3.12+ ignores); use `pip install '.[dev]'` instead.

### Run the target app (and keep it running)

```bash
uicap demo-app --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001 — a deliberately legacy-styled, fictional
credit-union servicing console. Synthetic members: `M-10001`, `M-10002`
(permission-denied on sub-accounts), `M-10003`; `M-40400` does not exist.

### Demo: genuine LLM discovery

In a second terminal (browser opens headed so you can watch):

```bash
uicap discover \
  --goal "Look up member M-10001 and return their current savings balance." \
  --target http://127.0.0.1:8001 \
  --capability-id member.get_savings_balance \
  --input member_id=M-10001 \
  --output artifacts/member.get_savings_balance.v1.json
```

Each turn the model (Gemini, `gemini-3.6-flash` in the submitted evidence)
receives a screenshot plus a compact semantic element inventory and returns
exactly one structured action via forced function calling (strict tool schema —
never code); every action is Pydantic-validated and policy-checked before
Playwright executes it. On success the run is compiled into
`artifacts/member.get_savings_balance.v1.json` — open it: `member_id` is a
typed input, not an embedded literal; targets are ordered locator-strategy
chains; checkpoints, error rules, policy and provenance are explicit. The
artifact's `provenance.discovery_model` records exactly which model produced
it.

To use Anthropic Claude instead, set `LLM_PROVIDER=anthropic` (plus
`ANTHROPIC_API_KEY`) or pass `--model-adapter anthropic`.

Offline test double (wiring demo only — **not** valid discovery evidence):

```bash
uicap discover \
  --goal "Look up member M-10001 and return their current savings balance." \
  --target http://127.0.0.1:8001 \
  --capability-id member.get_savings_balance \
  --input member_id=M-10001 \
  --model-adapter fake \
  --output /tmp/test-artifact.json
```

### Demo: deterministic replay (no LLM)

**No API key needed for anything below.** `evidence/example_capability.json` is
the committed artifact compiled from the genuine Gemini run, so every replay
demo works from a fresh clone without running discovery first. (If you did run
discovery above, `artifacts/member.get_savings_balance.v1.json` is the
equivalent freshly-compiled file.)

Replay the artifact with a **different** member — proving the capability is
parameterized, not a recorded literal:

```bash
uicap replay \
  --artifact evidence/example_capability.json \
  --input member_id=M-10003
```

Returns `status=success` with `"savings_balance": "$87.12"` — M-10003's
balance, not the member discovery ran against. The submitted artifact declares
`savings_balance` as a **string**, because that is the output type the
discovery model chose for the extract step, so the value is returned exactly as
the UI renders it; the type is part of the artifact contract and a re-recorded
capability could declare `decimal` instead. There is no model decision call
anywhere in this path (enforced by construction and by
`tests/unit/test_no_llm_in_replay.py`).

### Demo: business outcome vs failure

```bash
uicap replay \
  --artifact evidence/example_capability.json \
  --input member_id=M-40400
```

→ `status=business_outcome, code=MEMBER_NOT_FOUND` — a legitimate result the
calling agent needs, not a crash.

Recoverable condition (bounded, recorded recovery):

```bash
uicap replay --artifact evidence/example_capability.json \
  --input member_id=M-10001 --demo-interstitial
```

→ `status=success` with `recoveries: [{code: KNOWN_INTERSTITIAL, outcome:
recovered}]` — the known idle dialog was dismissed and the step retried.

There is also a transient-load knob (`--demo-slow`). With this particular
artifact it returns `status=failure, code=POLICY_BLOCKED`, because the
capability's declared policy never included `navigate` (the discovery model
reached every page by clicking links), so its reload recovery is not
authorized. That is the policy boundary working as intended — recovery gets no
weaker path to the browser than an ordinary step. The successful
wait-and-reload recovery path is covered by the test suite, which uses a
fixture artifact that does declare `navigate`.

Injected hard failure (deterministic simulation for evidence):

```bash
uicap replay \
  --artifact evidence/example_capability.json \
  --input member_id=M-10003 \
  --demo-failure missing_accounts_control
```

→ `status=failure, code=TARGET_NOT_FOUND, step_id=s4_click` with
expected/observed detail and a failure screenshot under the printed evidence
path. (The flag flips demo-app state; it resets on `POST /demo/reset` or app
restart.)

### Demo: human handoff (same live session)

```bash
python scripts/make_subaccount_artifact.py   # writes artifacts/member.open_sub_account.v1.json
uicap replay \
  --artifact artifacts/member.open_sub_account.v1.json \
  --input member_id=M-10001 --input "account_type=Holiday Savings"
```

1. Automation fills the form and stops at **Confirm Open Account** — the step
   is irreversible, policy demands a human. The headed browser stays open.
2. Open the operator console at http://127.0.0.1:8002 — it shows the
   intervention (run/step/reason/screenshot). Click **Take Control**.
3. Click **Confirm Open Account** yourself *in the same browser window*.
4. Back in the console, click **Resume Automation**. The engine re-observes,
   validates the confirmation checkpoint, extracts the confirmation number,
   and returns `status=success` — with your (redacted) actions recorded on the
   intervention. **Abort** instead returns `status=escalated`.

### Run tests

```bash
pytest -q
```

84 Phase-1 tests (of the 328 in the full suite): schema/binding/policy/redaction/error-taxonomy/result-contract/handoff
state-machine units, plus live-browser integration tests (deterministic replay
with a different member, business outcome, both recoverable conditions, injected
hard failure, discovery policy blocking, full same-session handoff). No test
calls any LLM API.

### Evidence

Committed evidence is produced by a real run of:

```bash
uicap demo-app &                      # if not already running
python scripts/capture_evidence.py    # requires GEMINI_API_KEY (default provider)
```

The committed evidence was produced with Gemini `gemini-3.6-flash` (set via
`GEMINI_MODEL`); `--provider anthropic` with an Anthropic key is the
alternative. The script **fails loudly** if the selected provider's key is
absent — it never falls back to a scripted model for genuine evidence.

| File | Proves |
|---|---|
| `evidence/discovery_run.jsonl` | genuine LLM-driven discovery (`gemini:gemini-3.6-flash`, recorded in the log): per-step observations, proposed structured actions, policy decisions, results (redacted) |
| `evidence/discovery_trace.zip` | Playwright trace of the discovery session |
| `evidence/example_capability.json` | the compiled artifact: typed contract, parameterized inputs, locator chains, checkpoints, error rules, policy, provenance (including the discovery model) |
| `evidence/replay_success.jsonl` | deterministic replay containing no model call of any kind — only policy checks, target resolutions, and step completions |
| `evidence/replay_not_found.jsonl` | expected business outcome (`MEMBER_NOT_FOUND`) at step `s3_click`, not a crash |
| `evidence/replay_failure.jsonl` + `failure_screenshot.png` | injected hard failure (`TARGET_NOT_FOUND` at `s4_click`) with expected/observed + screenshot |
| `evidence/handoff_run.jsonl` | same-session handoff run `rep-ff489aceae`: policy refuses `s7_click` unattended, intervention raised, ownership `PAUSED → HUMAN → PAUSED → AUTOMATION`, `human_completed_step` with 2 events, then `replay_succeeded` |
| `evidence/handoff_interventions.json` | the intervention record: reason, redacted URL, and the two captured human actions — a `click` on "Confirm Open Account" and the resulting `navigation`, with no typed values |
| `evidence/handoff_intervention_screenshot.png` | live session paused on the review screen, irreversible step not executed by automation |
| `evidence/handoff_resume_screenshot.png` | same session after the human confirmed, showing the confirmation page automation then revalidated |
| `evidence/handoff_trace.zip` | Playwright trace spanning the whole handoff |

Reading the logs honestly: invocation inputs and extracted outputs are redacted
in every log, so the replay logs do not themselves display the member ID. That
the replays ran against **M-10003** rather than the discovery member is shown
by `capture_evidence.py`'s arguments, by the returned balance matching
M-10003's fixture, and visibly by `failure_screenshot.png`.

The handoff evidence proves the human acted *after* claiming control: the
captured click is timestamped inside the HUMAN window, and the `navigation`
event shows capture surviving the page load the click caused.

What the committed evidence does **not** cover: recoverable conditions and
policy blocking are exercised by the test suite rather than by a committed
evidence file.

`scripts/capture_evidence.py --fake` exercises the same pipeline with the
scripted test double (dry run into `evidence-dryrun/`, never committed as
evidence).

---

## Security note

All member/customer data used in demos is synthetic or the target
application's own published sample data. Secrets live in `.env` (gitignored;
`.env.example` ships blank). One central redactor filters every log write:
sensitive keys, secret-shaped patterns, and registered runtime values (bound
inputs, extracted balances). Human typing is captured as
`value_changed=true, value=[REDACTED]` — never the value. The model is never
given code/JS execution, and every action passes the policy engine before the
browser acts. MERIDIAN evidence additionally masks screenshots and redacts
DOM snapshots at capture time, and disables durable Playwright traces (they
were found to leak POST bodies and unmasked frame images — see `DECISIONS.md`
D021). This is a prototype, not a hardened banking integration.

## Limitations

Single web surface (Playwright); desktop/legacy-frame adapters are
designed-for seams, not implemented. One live invocation at a time
(`CapabilityRunner` serializes with a lock); in-memory intervention store and
chatbot session store; no operator auth. Multi-tenant reuse is a design story
(see `REPORT.md` §4), not code. No LLM-assisted recovery during replay — by
design. See `REPORT.md` §7 (Cuts) and the
[Phase 2 known limitations](#known-limitations) above.
