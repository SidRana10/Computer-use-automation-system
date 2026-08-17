# 08 — Local Legacy-Style Target App Specification

## Why a local proxy

The assignment allows a local sample/mock target. Use one so the project can safely and deterministically exercise banking-like UI workflows and exceptional states without real credentials, PII, third-party ToS issues, or flaky external dependencies.

## App identity

Name displayed in UI: **Northstar Credit Union — Member Servicing Console (Demo)**

Clearly label it fictional/demo.

Use intentionally plain/legacy styling:
- server-rendered Jinja pages,
- table-heavy layout,
- simple forms,
- no React,
- no `data-testid` attributes,
- a few nested containers/awkward markup,
- accessible text/labels where reasonable so deterministic replay is possible,
- optionally one iframe for a secondary section only if it does not destabilize the core demo.

Do not deliberately make it so hostile that the project becomes a selector contest.

## Synthetic records

Seed obviously fictional members. Values can be adjusted, but keep deterministic fixtures.

Example:

| member_id | display name | savings | behavior |
|---|---|---:|---|
| `M-10001` | Demo Member One | 2540.75 | normal |
| `M-10002` | Demo Member Two | 10325.40 | permission denial on sub-account creation |
| `M-10003` | Demo Member Three | 87.12 | normal |
| `M-40400` | none | n/a | not found |

Never use real names/SSNs/account numbers.

## Primary flow — balance lookup

Routes/pages conceptually:

```text
/ -> dashboard
/members/search -> search form
/members/{id} -> member summary
/members/{id}/accounts -> accounts table
```

Goal used for real discovery evidence:

> Look up member M-10001 and return their current savings balance.

Steps should naturally be:
1. dashboard -> Member Search
2. fill Member ID
3. Search
4. member summary
5. Accounts
6. identify Savings row
7. extract current balance

The LLM should discover this rather than being given the exact steps in its runtime goal prompt.

## Business outcomes

### Member not found
Searching `M-40400` or unknown identifier renders a stable message such as:

```text
No member was found for that identifier.
```

Artifact error rule maps this to `MEMBER_NOT_FOUND`.

### Validation rejected
Malformed member ID such as `BAD` shows:

```text
Member ID must match M-#####.
```

Classify as `VALIDATION_REJECTED`.

### Permission denied
For `M-10002`, attempting the sub-account flow renders a permission message. Classify deliberately as a known business outcome or approval/failure according to the capability contract; document the choice.

## Recoverable runtime conditions

Implement deterministic knobs/fixtures, preferably query flags or test-only/session state rather than randomness.

### Known interstitial
On first navigation to Accounts for a chosen fixture/session, show a modal/banner:

```text
Your session has been idle. Continue session?
[Continue]
```

Replay recognizes/dismisses it and retries/checks the intended state.

### Transient slowness
A fixture or query option delays one response/overlay for ~1–2 seconds. Replay should rely on condition/actionability waits and optionally one bounded recovery retry, not long arbitrary sleeps.

## Hard failure injection

Provide a safe deterministic test/demo switch such as `?failure=missing_accounts_control` or an environment flag that changes/removes an expected control after artifact recording.

Replay should then produce a structured hard failure and screenshot, not proceed blindly.

Clearly label this as an injected simulation for evidence.

## Risky flow — sub-account review/confirmation

Conceptual routes:

```text
/members/{id}/subaccounts/new
/members/{id}/subaccounts/review
/members/{id}/subaccounts/confirmed
```

Inputs:
- member_id
- account_type (e.g. `Holiday Savings`)

The form can include 2–3 fields and a review page. Mark the final `Confirm Open Account` action as irreversible/risky for policy purposes.

Do not model real financial operations. It is a local fake state mutation only.

Preferred handoff demonstration:
- automation reaches review,
- policy requires human for final confirm,
- operator takes control of same browser,
- human confirms,
- automation resumes and verifies confirmation page.

## Session expiration

Include a deterministic route/state that displays a session-expired page. Because the prototype should not store credentials, classify this as hard failure/escalation rather than automatically re-authenticating.

## App reset

Provide a simple dev/test reset mechanism to restore synthetic state between runs, e.g. CLI endpoint used only locally or in-process fixture. Do not expose an unrestricted reset in a production-like policy; document it as demo tooling.
