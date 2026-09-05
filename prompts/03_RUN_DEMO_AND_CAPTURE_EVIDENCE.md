> **Phase 1 historical.** This file drove the original Northstar build. Phase 2 (MERIDIAN CORE) is governed by `phase2_build_pack/`. Kept for provenance; not a current instruction.

Run the genuine final evidence workflow for this submission. Do not fabricate or hand-edit logs to make the result look successful.

Prerequisite: `ANTHROPIC_API_KEY` must already be available in my environment or `.env` (which must remain gitignored). Use `DISCOVERY_MODEL=claude-fable-5` unless repository config intentionally overrides it.

## 1. Clean/reset controlled demo state
- reset the synthetic target app data/session state,
- clear only regenerable evidence from prior test runs while preserving directory structure,
- start required local services,
- use headed Playwright for visual verification/handoff.

## 2. Genuine LLM discovery
Run the real discovery goal:

`Look up member M-10001 and return their current savings balance.`

Provide the discovery invocation binding `member_id=M-10001` through the implemented CLI so the model can reference the typed input while the executor binds the real value and the compiler can parameterize it deterministically.

Requirements:
- actual Claude API call(s),
- actual live UI observation,
- actual model-decided UI actions,
- policy checks,
- goal verification,
- artifact compiler output.

Save sanitized evidence as agreed in `docs/09_TEST_EVIDENCE_PLAN.md`, including `evidence/discovery_run.jsonl` and the real generated `evidence/example_capability.json`. Save trace/screenshots if implemented.

Validate that the artifact contains no concrete bound member ID where a parameter reference should be.

## 3. Deterministic parameterized replay success
Replay the generated artifact with a different valid synthetic member, preferably `M-10003`.

Verify:
- no LLM decision calls,
- success checkpoint passes,
- savings balance output is typed decimal,
- logs redact the sensitive invocation/output values as configured.

Save `evidence/replay_success.jsonl` and any trace/result evidence.

## 4. Business outcome replay
Replay with `M-40400`.

Verify structured `business_outcome` with code `MEMBER_NOT_FOUND`, not an uncaught exception.

Save `evidence/replay_not_found.jsonl`.

## 5. Hard-failure evidence
Enable the documented deterministic missing-control or equivalent injected failure and replay.

Verify structured hard failure includes:
- failed step ID,
- expected state/control,
- observed condition,
- evidence path.

Save `evidence/replay_failure.jsonl` and `evidence/failure_screenshot.png` or the actual configured filename.

## 6. Human handoff demo
Run the risky sub-account flow through the real handoff mechanism:
- reach irreversible confirmation,
- policy creates intervention,
- automation pauses,
- Take Control,
- manually act in the same headed browser,
- Resume,
- automation re-observes/revalidates and completes or reports the designed result,
- human event evidence is recorded with input values redacted.

Save the handoff log/evidence using clear filenames.

## 7. Evidence/security verification
Inspect every new committed evidence file for:
- API keys,
- auth headers/tokens/cookies,
- `.env` contents,
- sensitive typed values that policy says must be redacted.

Remove/redo evidence if it leaks anything.

## 8. Final smoke check
Rerun tests and README demo commands as practical. Update README evidence section only if filenames differ. Do not change architecture merely to make evidence prettier.
