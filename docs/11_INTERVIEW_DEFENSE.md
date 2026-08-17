# 11 — What You Must Be Able to Defend

This is not required by the assignment, but use it before submission because the brief says you own and must explain AI-generated work.

For each topic below, be able to explain the decision without saying “Claude chose it.”

## Architecture
- Why discovery and replay are separate.
- Why replay intentionally has no LLM in the normal path.
- Why a SurfaceAdapter is useful even though only Playwright is implemented.
- Why single-process/local-first is appropriate for the take-home.

## Artifact
- Why the artifact is more than a recorded click list.
- How inputs become parameters rather than concrete values.
- How outputs are typed and extracted.
- Why locator strategies are ordered.
- Why the raw LLM transcript is kept separate.
- How artifact versioning/approval/provenance would work.

## Locators/determinism
- Why role/label/text is stronger than screen coordinates for replay.
- What happens if the first locator strategy stops matching.
- Why checkpoint verification matters after a click.
- Why arbitrary sleeps are inferior to actionability/condition waits.

## Errors
- Difference between `MEMBER_NOT_FOUND` and a crash.
- What qualifies as recoverable.
- Why retries are bounded.
- What information a hard failure returns.

## Safety
- Why policy runs outside the LLM.
- How domain/action allowlists are enforced.
- How risky actions trigger human approval.
- What is redacted and what the screenshot limitation would be in production.

## Handoff
- How the browser remains the same session.
- How control ownership prevents simultaneous actions.
- How human activity is recorded without logging typed sensitive values.
- What is validated before automation resumes.

## Scale/generalization
- How a desktop adapter could fit.
- How one vendor capability could be reused across tenants.
- How tenant/version overrides avoid copying whole artifacts.
- How drift would be detected and reviewed.

## Likely “why not?” questions

### Why not Selenium?
Playwright has strong modern locator/actionability/tracing ergonomics. Selenium could also satisfy the problem; the architecture hides this choice behind the surface adapter.

### Why not pure screenshot coordinates?
They generalize to non-DOM surfaces but are weak for deterministic replay. The prototype uses visual observation for discovery while compiling stable semantic web targets for replay. Future desktop/vision adapters could use different target strategies.

### Why not use the LLM to recover every replay failure?
That would undermine deterministic, auditable production behavior. The core path uses explicit bounded recovery and human escalation. A policy-bounded single-step LLM fallback is only a stretch goal.

### Why build a fake banking app?
It is explicitly allowed, avoids real PII/credentials/ToS risks, and lets the demo deterministically exercise the runtime failure modes the assignment emphasizes.

### Why JSON instead of database?
For a take-home, human reviewability/versioning/simplicity matter more. CapabilityStore is a seam that could later back onto a database/registry.
