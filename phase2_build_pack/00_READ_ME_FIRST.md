# MERIDIAN CORE Phase 2 — How to Use This Build Pack

This pack is designed for the existing `interface-ai-takehome` repository on branch `meridian-adaptation`.

## Recommended model strategy

Use **Claude Opus 5** for almost all work. It is sufficient for repository inspection, implementation, testing, debugging, refactoring, README/write-up work, and demo preparation.

Reserve **Fable 5** for only two high-value checkpoints because credits are limited:

1. **Critical architecture/adversarial review** after MERIDIAN login + member inquiry + balance + transfer + exceptional-state handling are working end-to-end.
2. **Final independent submission review** after all capabilities, API, chatbot, dashboard, docs, tests, and demo evidence are complete.

Do not spend Fable credits on routine coding, UI polish, basic tests, or ordinary debugging.

## Before starting

Confirm:
- Repository: `interface-ai-takehome`
- Current branch: `meridian-adaptation`
- Working tree: clean
- Phase 1 final baseline commit exists on `main`

## Workflow

1. Start a **fresh Claude Code chat** in the same repository.
2. Upload or copy this entire folder into the repository, for example under `phase2_build_pack/`.
3. Give Claude the prompt from `01_NEW_CHAT_FIRST_PROMPT.txt`.
4. After the architecture/gap analysis, give Claude `02_MASTER_BUILD_PROMPT.txt`.
5. Let Opus work phase-by-phase using `04_IMPLEMENTATION_WORKFLOW.md` and `05_PHASE_PROMPTS.md`.
6. At the first Fable checkpoint, use `06_FABLE_REVIEW_PROMPTS.md`.
7. Finish with the final Fable review, then use `07_DEMO_AND_DELIVERABLES.md`.

## Important rule

Do **not** ask Claude to rewrite the project from scratch. The assignment is explicitly an adaptation of the existing core. The strongest submission demonstrates that discovery, typed capability artifacts, deterministic replay, policy enforcement, redaction, evidence, and escalation were genuinely reusable.
