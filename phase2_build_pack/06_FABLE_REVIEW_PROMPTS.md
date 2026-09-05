# Fable 5 — Use Only at These Checkpoints

With limited credits, use Fable twice.

## Fable Review 1 — after Phase 5, before API/chatbot/dashboard

Switch to Fable only when MERIDIAN login, member inquiry, balance, transfer, remaining capabilities, and exceptional-state handling are implemented and tests are green.

Use this prompt:

> Act as an adversarial senior reviewer. Do not implement features unless I explicitly ask after the review.
>
> Review the current `meridian-adaptation` branch against the Phase 2 MERIDIAN assignment and the original Phase 1 guarantees.
>
> Focus only on load-bearing correctness:
> - whether this is truly an adaptation rather than a hidden rewrite;
> - deterministic replay with no model in the execution decision loop;
> - dynamic hidden-token extraction;
> - review -> post correctness;
> - duplicate/uncertain irreversible transaction risks;
> - PolicyEngine enforcement on normal and recovery paths;
> - supervisor gating and escalation;
> - business outcome vs recoverable vs failed vs escalated taxonomy;
> - timeout/session-resume safety;
> - redaction and evidence integrity;
> - whether all seven required capabilities are real, typed, and replayable;
> - regression risk to Northstar/Phase 1.
>
> Try to break the design. Inspect source and tests, and run targeted tests if useful.
>
> Return findings ranked as:
> P0 submission blocker
> P1 important correctness/safety issue
> P2 improvement
>
> For each finding provide exact file/module, concrete failure scenario, and minimal fix.
>
> End with one verdict only: `READY FOR WRAPPERS` or `FIX CORE FIRST`.

If verdict is `FIX CORE FIRST`, switch back to Opus for fixes. Do not burn Fable credits on routine fixing.

## Fable Review 2 — final independent submission review

Use only after API, chatbot, dashboard, docs, tests, and demo path are complete.

Prompt:

> Perform a final independent submission review of the `meridian-adaptation` branch.
>
> Assume the reviewer is the company CTO and will run a live demo.
>
> Validate the implementation against every Phase 2 requirement and evaluation criterion. Inspect code, tests, docs, evidence, API contract, chatbot path, dashboard path, error handling, safety, redaction, and escalation.
>
> Pay special attention to anything that can fail live or undermine the claim that this was an adaptation of the original core.
>
> Do not reward framework breadth or visual polish. Optimize for correctness, robustness, simplicity, and defensible engineering judgment.
>
> Return:
> 1. P0/P1/P2 findings with exact evidence;
> 2. missing or weak demo cases;
> 3. claims in README/write-up that are not fully supported by the implementation;
> 4. last-mile fixes only — no scope expansion;
> 5. a final verdict: `SUBMIT` or `DO NOT SUBMIT`.

If the verdict is `DO NOT SUBMIT`, switch back to Opus to fix only the cited blockers, then if credits permit ask Fable to re-check only those blockers.
