# Opus 5 vs Fable 5

## Default: Opus 5

Use Opus for ~90–95% of the project:
- repository inspection
- architecture/gap analysis
- adapter work
- browser automation
- capability artifacts
- tests
- error handling
- API
- chatbot
- dashboard
- docs
- debugging
- fixes from reviews

Opus is enough for normal implementation.

## Fable 5 — only two recommended uses

### Use 1: Core correctness review
Timing: after Phase 5.

Why this is worth credits:
By then the riskiest engineering is present: dynamic token, irreversible writes, policy, recovery, error taxonomy, supervisor gating. A stronger adversarial review can catch architectural or safety flaws before wrappers hide them.

### Use 2: Final submission review
Timing: after Phase 9.

Why this is worth credits:
This is the highest-value use because it checks the entire submission as a reviewer would see it and catches unsupported claims, demo risks, and last-mile blockers.

## Do not use Fable for
- ordinary implementation
- styling/UI
- straightforward unit tests
- basic README edits
- routine selector/debug fixes
- fixing issues Fable already identified

Switch back to Opus for all fixes.

## If credits become extremely tight
Skip Review 1 and save Fable only for the final independent review.
