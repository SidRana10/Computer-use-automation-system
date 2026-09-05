# Evidence

**Status: captured from a real run.** Nothing here is fabricated or
hand-edited; every file below was written by `scripts/capture_evidence.py`.

The runtime discovery model for the submitted genuine evidence is **Google
Gemini `gemini-3.6-flash`** (free tier), recorded in `discovery_run.jsonl` and
in the artifact's `provenance.discovery_model` as `gemini:gemini-3.6-flash`.
Anthropic Claude is available as an optional alternative provider
(`--provider anthropic`). Development of the repository was AI-assisted (Claude
Code / Claude Fable 5) — a development tool, not the runtime discovery
provider. Deterministic replay invokes no LLM regardless of provider.

## Files

| File | What it shows |
|---|---|
| `discovery_run.jsonl` | genuine discovery run `disc-3b572d9b32`: alternating model proposals and executed actions across changing page states (redacted) |
| `discovery_trace.zip` | Playwright trace of that discovery session |
| `example_capability.json` | the artifact compiled from that run |
| `replay_success.jsonl` | deterministic replay — policy checks, target resolutions, step completions; no model call of any kind |
| `replay_not_found.jsonl` | `MEMBER_NOT_FOUND` business outcome at step `s3_click` |
| `replay_failure.jsonl` + `failure_screenshot.png` | injected `missing_accounts_control` hard failure: `TARGET_NOT_FOUND` at `s4_click` with expected/observed |
| `handoff_run.jsonl` | same-session handoff `rep-ff489aceae`: `s7_click` refused unattended, intervention raised, ownership `PAUSED → HUMAN → PAUSED → AUTOMATION`, `human_completed_step` with 2 events, `replay_succeeded` |
| `handoff_interventions.json` | intervention record with the two captured human actions (`click` on "Confirm Open Account", then `navigation`), redacted URL, no typed values |
| `handoff_intervention_screenshot.png` | session paused on the review screen — automation did not execute the irreversible step |
| `handoff_resume_screenshot.png` | same session after the human confirmed; the state automation revalidated before resuming |
| `handoff_trace.zip` | Playwright trace across the handoff |

## Reading these logs honestly

Invocation inputs and extracted outputs are redacted in every log, so the
replay logs do not themselves display the member ID. That the replays ran
against **M-10003** rather than the discovery member is shown by
`capture_evidence.py`'s arguments, by the returned balance matching M-10003's
fixture, and visibly by `failure_screenshot.png`.

The JSONL logs and the artifact contain no raw runtime values. The trace and
screenshots do show on-screen synthetic member data, which is inherent to
visual evidence — every value is fictional (see REPORT §6).

In the handoff evidence, the captured click is timestamped inside the HUMAN
window (after Take Control), and the `navigation` event shows capture surviving
the page load that click caused. Human actions taken while the run is merely
PAUSED are deliberately not recorded: under the strict ownership model only a
claimed session produces authorized human actions.

Not covered by these files: recoverable conditions and policy blocking are
exercised by the test suite rather than by a committed evidence file.

## Regenerating

```bash
uicap demo-app &                    # target app on :8001
python scripts/capture_evidence.py  # needs GEMINI_API_KEY in env/.env
```

The script fails loudly if the selected provider's API key is absent and never
falls back to a scripted model. `evidence/runs/` holds per-run working evidence
(gitignored). The pipeline is validated end-to-end by
`scripts/capture_evidence.py --fake`, which uses the scripted test double and
writes to `evidence-dryrun/` — that output is clearly labeled and is never
valid discovery evidence.
