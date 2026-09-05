> **Phase 1 historical.** This file drove the original Northstar build. Phase 2 (MERIDIAN CORE) is governed by `phase2_build_pack/`. Kept for provenance; not a current instruction.

Perform a submission-blocking final audit of this repository against `reference/ORIGINAL_ASSIGNMENT.txt`, `CLAUDE.md`, and `docs/01_REQUIREMENTS_TRACEABILITY.md`.

This is not a documentation-only review. Inspect and run the code.

## Audit procedure

1. Run all automated tests and relevant lint/type checks.
2. Trace one discovery flow through code from CLI -> LLM -> policy -> surface -> recorder -> compiler.
3. Trace one replay flow from CLI -> artifact load -> binder -> policy -> locator resolver -> executor -> condition/error handling -> structured result. Verify no LLM decision call is reachable in ordinary replay.
4. Verify artifact schema contains typed inputs/outputs, ordered robust target strategies, parameterization, checkpoints/success conditions, error behavior, version/provenance, policy/app metadata.
5. Verify runtime error taxonomy is actually implemented: business outcome, recoverable, hard failure.
6. Verify policy checks precede execution and cannot be broadened by artifact policy.
7. Verify redaction covers sensitive input/output/log/human-action cases.
8. Verify hard failure creates screenshot or equivalent richer evidence.
9. Verify handoff keeps the same live Playwright session, has explicit ownership transitions, permits Take Control/Resume/Abort, records redacted human actions, and revalidates on resume.
10. Verify target app can deterministically produce not-found, validation, permission, recoverable transient/interstitial, session-expired, hard-failure injection, and risky confirmation behaviors.
11. Verify README setup and demo commands match the real CLI and have been tested.
12. Verify REPORT has exactly seven required headings, is concise, and distinguishes implemented behavior from design-only claims.
13. Scan tracked files for secrets, `.env`, API keys, cookies, authorization tokens, and raw sensitive logged values.
14. Verify `/evidence/` contains only genuine evidence; if real discovery has not yet been run because there was no API key, do not fabricate it—mark that as the only remaining blocker with the exact command.
15. Review git diff for dead code, TODOs in core requirements, accidental generated files, and misleading comments.

Use the custom architecture/requirements/security/test reviewers as independent passes. Fix every substantive issue you find, rerun tests, and repeat the relevant audit checks.

Only after fixes, produce a concise final status containing:
- tests/checks that passed,
- exact core demo commands,
- evidence files present,
- any single unavoidable external blocker (for example missing API key),
- confirmation that all assignment MUST requirements are covered.
