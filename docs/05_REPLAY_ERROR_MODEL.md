# 05 — Deterministic Replay and Error Model

## Core invariant

Ordinary replay is LLM-free. The replay package must not instantiate/import/use an Anthropic model client for decision making.

## Replay algorithm

1. Load + Pydantic-validate artifact.
2. Validate invocation inputs against contract.
3. Merge global policy with capability policy, always taking the stricter rule.
4. Start/open target via SurfaceAdapter.
5. Verify target-app fingerprint/preconditions where defined.
6. For each step:
   - bind value references,
   - run policy check,
   - resolve target using ordered locator strategies,
   - execute with configured timeout,
   - evaluate known error-state detectors,
   - apply bounded recovery if classified recoverable,
   - evaluate step checkpoint(s),
   - log structured result.
7. Extract declared outputs.
8. Verify final success conditions.
9. Return structured result.

## Result contract

Use a discriminated Pydantic union or equivalent. Required statuses:

### Success

```json
{
  "status": "success",
  "run_id": "...",
  "capability_id": "member.get_savings_balance",
  "capability_version": "1.0.0",
  "outputs": {"savings_balance": 2540.75},
  "evidence": ["..."]
}
```

Sensitive outputs may be returned to the caller but must be redacted in persisted logs.

### Business outcome

```json
{
  "status": "business_outcome",
  "code": "MEMBER_NOT_FOUND",
  "message": "No member matched the supplied identifier.",
  "step_id": "search_member",
  "outputs": {},
  "evidence": ["..."]
}
```

This is not a crash and should normally have no Python stack trace in user-facing output.

### Failure

```json
{
  "status": "failure",
  "code": "TARGET_NOT_FOUND",
  "category": "hard_failure",
  "step_id": "open_accounts",
  "expected": "Accounts control resolvable by artifact locator strategies",
  "observed": "No strategy matched within 5000ms",
  "recovery_attempts": 0,
  "evidence": ["evidence/...png"]
}
```

### Escalated

```json
{
  "status": "escalated",
  "code": "HUMAN_APPROVAL_REQUIRED",
  "intervention_id": "...",
  "step_id": "confirm_open_account",
  "message": "Irreversible confirmation requires a human operator."
}
```

## Error taxonomy

### 1. Expected business outcomes

Known app states that are meaningful results, not software crashes.

Recommended demo codes:
- `MEMBER_NOT_FOUND`
- `VALIDATION_REJECTED`
- `PERMISSION_DENIED` when the app explicitly reports a domain permission outcome

### 2. Recoverable conditions

Conditions the executor knows how to resolve safely and within a small attempt budget.

Recommended demo codes:
- `KNOWN_INTERSTITIAL` — dismiss known modal/banner, then retry current step
- `TRANSIENT_LOAD` — wait/backoff and retry <= 2
- `TEMPORARY_APP_ERROR` — one bounded refresh/retry only if the artifact/policy explicitly allows it

### 3. Hard failures

Stop rather than guessing:
- `TARGET_NOT_FOUND`
- `AMBIGUOUS_TARGET`
- `CHECKPOINT_FAILED`
- `UNEXPECTED_STATE`
- `OUTPUT_EXTRACTION_FAILED`
- `TARGET_APP_MISMATCH`
- `SESSION_EXPIRED` if no safe credential-free recovery exists
- `POLICY_BLOCKED`
- `RETRY_EXHAUSTED`

A hard failure may be escalated to a human if handoff is enabled and safe.

## Locator resolution

For each `TargetDescriptor`, try strategies in order and log which one matched. Reject ambiguous matches unless the strategy explicitly permits uniqueness handling.

Rules:
- exact semantic locator is preferred,
- wait for actionability rather than arbitrary sleeps,
- use explicit bounded wait for expected async states,
- no silent fallback to random first match,
- no coordinate fallback in ordinary replay unless the artifact explicitly marks a surface-specific emergency strategy and policy permits it (prefer not to implement this in the demo).

## Checkpoints

A step succeeds only if both:
- the action completes, and
- any declared checkpoint is satisfied.

The final run succeeds only if declared `success_conditions` pass.

This protects against false-positive clicks/navigation.

## Recovery strategy

Recovery is explicit, bounded, and logged. Never turn recovery into an open-ended agent loop.

Example:

```text
click Search -> timeout due to loading overlay
  detect TRANSIENT_LOAD
  wait until overlay absent or 2 sec
  retry same step once
  checkpoint passes -> continue
```

If retry limit is exhausted -> hard failure / human escalation.

## Drift handling

UI drift is secondary in this assignment. Still:
- log which locator fallback matched,
- record app fingerprint mismatch,
- treat repeated fallback usage/checkpoint degradation as a signal that artifact review may be needed,
- explain in REPORT how per-tenant/version overrides could specialize locator strategies.
