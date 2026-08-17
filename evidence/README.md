# Evidence

**Status: the genuine discovery evidence has not been captured yet** — it
requires a real LLM API key, and nothing here is fabricated.

The runtime discovery model for the submitted genuine evidence is **Google
Gemini (`gemini-3-flash-preview`, free tier)**; Anthropic Claude is available
as an optional alternative provider (`--provider anthropic`). Development of
the repository was AI-assisted (Claude Code / Claude Fable 5). Deterministic
replay invokes no LLM regardless of provider.

To produce the full canonical evidence set (genuine LLM-driven discovery,
then the LLM-free replays), run from the repo root with the demo app up:

```bash
uicap demo-app &                    # target app on :8001
python scripts/capture_evidence.py  # needs GEMINI_API_KEY in env/.env
```

The script fails loudly if the selected provider's API key is absent and never
falls back to a scripted model. It writes, into this directory:

- `discovery_run.jsonl` — genuine discovery run (redacted structured log)
- `discovery_trace.zip` — Playwright trace of the discovery session
- `example_capability.json` — the compiled artifact from that run
- `replay_success.jsonl` — deterministic replay with a different member (M-10003)
- `replay_not_found.jsonl` — `MEMBER_NOT_FOUND` business outcome (M-40400)
- `replay_failure.jsonl` + `failure_screenshot.png` — injected hard failure

`evidence/runs/` holds per-run working evidence (gitignored). The pipeline is
validated end-to-end by `scripts/capture_evidence.py --fake`, which uses the
scripted test double and writes to `evidence-dryrun/` — that output is clearly
labeled and is never valid discovery evidence.
