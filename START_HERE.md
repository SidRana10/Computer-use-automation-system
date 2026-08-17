# START HERE — Claude Code Build Pack

This folder is a build-control package for the interface.ai engineering take-home assignment in `reference/ORIGINAL_ASSIGNMENT.txt`.

## Intended usage

1. Create an empty public-GitHub-bound repository locally.
2. Copy **everything in this build pack** into the repository root, including the hidden `.claude/` directory.
3. Open a terminal in that repository.
4. Make sure Claude Code is current enough for Fable 5 (Anthropic currently documents Claude Code v2.1.170+). Run `claude update` if needed, start `claude`, then select it with `/model fable` (subject to account access/usage credits).
5. Start Claude Code from the repository root.
6. Paste the contents of `prompts/00_MASTER_BUILD_PROMPT.md` as the first instruction.
7. Let Claude inspect all project-control files before it writes code.
8. If it stops after a milestone, use `prompts/01_CONTINUE_PROMPT.md`.
9. Before submission, use `prompts/02_FINAL_AUDIT_PROMPT.md`.
10. For the real discovery/replay evidence run, use `prompts/03_RUN_DEMO_AND_CAPTURE_EVIDENCE.md`.
11. After the project is finished, use `prompts/05_EXPLAIN_AND_DEFEND_AFTER_BUILD.md` so Claude teaches you the actual code before an interview.

## Important

This pack intentionally chooses a concrete implementation so Claude does not waste time re-deciding the architecture:

- Python 3.12
- Async Playwright for browser control
- Anthropic Messages API with `claude-fable-5` as the default discovery model
- Pydantic v2 for typed artifacts/results/config
- FastAPI + Jinja2 for the local legacy-style target app and minimal operator console
- JSON artifacts + JSONL structured logs
- pytest for tests
- one-process/local-first architecture with explicit seams for future surfaces/services

The target demo is a **local fictional credit-union back-office application**. It contains only synthetic data and intentionally includes runtime conditions the assignment cares about: not-found, validation rejection, permission denial, transient slowness, session expiration, confirmation/risk escalation, and an injected failure mode.

## What Claude is expected to produce

The final repository must contain the actual source code plus the exact required submission files:

- `/README.md`
- `/REPORT.md` using the seven required headings exactly
- `/evidence/` with a saved artifact, discovery log, replay-success log, replay-exception log, and richer failure evidence

This build pack is not itself the submission. Claude should use it as requirements/context, then create the finished project in the same repository.
