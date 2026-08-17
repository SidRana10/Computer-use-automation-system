# UI Capabilities — discover once, replay deterministically

A small end-to-end computer-use system for legacy back-office applications that
have no API. An LLM (Claude) **discovers** how to complete a natural-language
goal on a live UI once; the successful run is **compiled** into a typed,
versioned, parameterized **capability artifact**; production execution is a
**deterministic replay** of that artifact with **zero LLM decisions**, explicit
error/outcome handling, configurable safety guardrails, and a **same-session
human handoff** path for risky or stuck situations.

> The model discovers. The artifact is the capability. Deterministic replay is
> production execution.

## Architecture at a glance

```text
CLI (uicap)
   |          discovery                          replay
   v                                               v
DiscoveryAgent --(one structured action/turn)-- ReplayEngine  (no LLM here)
   |   ^                                           |
   |   | Claude (Messages API, strict tools)       |
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
- `src/ui_capabilities/discovery/` — agent loop, Anthropic adapter, scripted test doubles, recorder, compiler
- `src/ui_capabilities/replay/` — binder, error classifier, bounded recovery, replay engine (no model client)
- `src/ui_capabilities/policy/` — allowlist policy engine + central redactor
- `src/ui_capabilities/handoff/` — control-owner state machine, intervention store, operator console
- `src/ui_capabilities/surfaces/` — SurfaceAdapter protocol, Playwright implementation, locator resolver
- `demo_app/` — the fictional target application (all data synthetic)

## Prerequisites

- Python 3.12
- Playwright Chromium (installed below)
- An Anthropic API key — **only** for the genuine discovery run; tests and
  replay never call the API.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
playwright install chromium
cp .env.example .env   # then put your ANTHROPIC_API_KEY in .env (never committed)
```

Troubleshooting: if `import ui_capabilities` fails after an editable install,
your environment may be skipping `.pth` files (some macOS setups mark them
hidden, which Python 3.12+ ignores); use `pip install '.[dev]'` instead.

## Run the target app (and keep it running)

```bash
uicap demo-app --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001 — a deliberately legacy-styled, fictional
credit-union servicing console. Synthetic members: `M-10001`, `M-10002`
(permission-denied on sub-accounts), `M-10003`; `M-40400` does not exist.

## Demo: genuine LLM discovery

In a second terminal (browser opens headed so you can watch):

```bash
uicap discover \
  --goal "Look up member M-10001 and return their current savings balance." \
  --target http://127.0.0.1:8001 \
  --capability-id member.get_savings_balance \
  --input member_id=M-10001 \
  --output artifacts/member.get_savings_balance.v1.json
```

Each turn Claude receives a screenshot plus a compact semantic element
inventory and returns exactly one structured action (strict tool schema —
never code); every action is policy-checked before Playwright executes it. On
success the run is compiled into `artifacts/member.get_savings_balance.v1.json`
— open it: `member_id` is a typed input, not an embedded literal; targets are
ordered locator-strategy chains; checkpoints, error rules, policy and
provenance are explicit.

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

## Demo: deterministic replay (no LLM)

Replay the artifact with a **different** member — proving the capability is
parameterized, not a recorded literal:

```bash
uicap replay \
  --artifact artifacts/member.get_savings_balance.v1.json \
  --input member_id=M-10003
```

Returns `status=success` with `outputs.savings_balance=87.12`. There is no
model decision call anywhere in this path (enforced by construction and by
`tests/unit/test_no_llm_in_replay.py`).

## Demo: business outcome vs failure

```bash
uicap replay \
  --artifact artifacts/member.get_savings_balance.v1.json \
  --input member_id=M-40400
```

→ `status=business_outcome, code=MEMBER_NOT_FOUND` — a legitimate result the
calling agent needs, not a crash.

Recoverable conditions (bounded, recorded recovery):

```bash
uicap replay --artifact artifacts/member.get_savings_balance.v1.json \
  --input member_id=M-10001 --demo-interstitial   # known idle dialog → dismissed
uicap replay --artifact artifacts/member.get_savings_balance.v1.json \
  --input member_id=M-10001 --demo-slow           # transient load → wait+reload
```

Injected hard failure (deterministic simulation for evidence):

```bash
uicap replay \
  --artifact artifacts/member.get_savings_balance.v1.json \
  --input member_id=M-10003 \
  --demo-failure missing_accounts_control
```

→ `status=failure, code=TARGET_NOT_FOUND, step_id=s4_click` with
expected/observed detail and a failure screenshot under the printed evidence
path. (The flag flips demo-app state; it resets on `POST /demo/reset` or app
restart.)

## Demo: human handoff (same live session)

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

## Run tests

```bash
pytest -q
```

84 tests: schema/binding/policy/redaction/error-taxonomy/result-contract/handoff
state-machine units, plus live-browser integration tests (deterministic replay
with a different member, business outcome, both recoverable conditions, injected
hard failure, discovery policy blocking, full same-session handoff). No test
calls the Anthropic API.

## Evidence

Committed evidence is produced by a real run of:

```bash
uicap demo-app &                      # if not already running
python scripts/capture_evidence.py    # requires ANTHROPIC_API_KEY
```

| File | Proves |
|---|---|
| `evidence/discovery_run.jsonl` | genuine Claude-driven discovery: per-step observations, proposed structured actions, policy decisions, results (redacted) |
| `evidence/discovery_trace.zip` | Playwright trace of the discovery session |
| `evidence/example_capability.json` | the compiled artifact: typed contract, parameterized inputs, locator chains, checkpoints, error rules, policy, provenance |
| `evidence/replay_success.jsonl` | deterministic LLM-free replay with a *different* member (M-10003) |
| `evidence/replay_not_found.jsonl` | expected business outcome (`MEMBER_NOT_FOUND`), not a crash |
| `evidence/replay_failure.jsonl` + `failure_screenshot.png` | injected hard failure with step/expected/observed + richer signal |

`scripts/capture_evidence.py --fake` exercises the same pipeline with the
scripted test double (dry run into `evidence-dryrun/`, never committed as
evidence).

## Security note

All member data is synthetic and clearly fictional; the app is local-only.
Secrets live in `.env` (gitignored; `.env.example` ships blank). One central
redactor filters every log write: sensitive keys, secret-shaped patterns, and
registered runtime values (bound inputs, extracted balances). Human typing is
captured as `value_changed=true, value=[REDACTED]` — never the value. The
model is never given code/JS execution, and every action passes the policy
engine before the browser acts. This is a prototype against a synthetic app,
not a hardened banking integration.

## Limitations

Single web surface (Playwright); desktop/legacy-frame adapters are designed-for
seams, not implemented. One local run at a time; in-memory intervention store;
no operator auth. Multi-tenant reuse is a design story (see REPORT §4), not
code. No LLM-assisted recovery during replay — by design. See REPORT §7 (Cuts).
