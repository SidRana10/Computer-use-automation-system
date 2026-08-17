# 14 — Suggested Evaluator Demo Script

Use this only after the project works. Keep the live demo focused on the assignment's through-line rather than showing every file.

## 0. One-sentence framing

> This system uses an LLM only to discover a UI workflow once, compiles that run into a typed reusable capability, and then executes the capability deterministically with explicit error handling, policy checks, and human handoff.

## 1. Show target app briefly

Open the fictional Northstar Credit Union demo app and show that it is a real live browser surface with a multi-step member search/accounts flow. Mention that it is intentionally local/synthetic so exceptional states are deterministic and no real credentials/PII are involved.

Do not manually reveal the entire workflow before the discovery demo if you want the evidence to clearly look like real model discovery.

## 2. Genuine discovery

Run the README discovery command with:
- natural-language goal,
- target URL,
- input binding `member_id=M-10001`.

While it runs, point out:
- each turn observes the current screenshot/semantic UI,
- Claude returns one structured action,
- PolicyEngine approves/blocks before Playwright acts,
- recorder captures resolved target strategies/evidence,
- stopping conditions bound the agent.

At success, open the generated artifact.

## 3. Show the artifact — spend time here

Highlight:
- capability ID/version,
- `member_id` typed input rather than `M-10001` embedded in steps,
- typed `savings_balance` output,
- ordered locator strategies,
- checkpoints/success conditions,
- error rules,
- risk/policy metadata,
- provenance.

Explain that the artifact is deliberately separate from the raw model transcript.

## 4. Deterministic replay with a different input

Replay the generated artifact with `M-10003`.

State clearly:
> There is no model decision call in this path; the replay engine is an interpreter for the saved capability.

Show returned structured success/output and logs.

This is the strongest proof that the artifact is actually parameterized and reusable.

## 5. Business outcome

Replay with `M-40400`.

Show:

```text
status=business_outcome
code=MEMBER_NOT_FOUND
```

Explain why this is not treated as an automation crash.

## 6. Hard failure / richer evidence

Enable the deterministic missing-control injection and replay.

Show:
- structured failure,
- failed step ID,
- expected vs observed,
- screenshot/trace evidence.

Explain that the executor stops rather than guessing.

## 7. Human handoff

Run the risky sub-account flow.

Show:
- irreversible action hits policy,
- intervention created,
- current browser stays open,
- operator console shows context/screenshot,
- Take Control changes ownership,
- human acts in the same browser,
- Resume returns ownership,
- automation re-observes/checks state,
- redacted human actions are recorded.

This is enough; do not spend time making the console look fancy.

## 8. Close with generalization

Open architecture diagram or REPORT and explain:
- `SurfaceAdapter` is how browser support could extend to desktop/accessibility/vision surfaces,
- capability schema describes logical controls/actions rather than leaking Playwright throughout the system,
- vendor-family base artifacts plus versioned tenant overrides would support institutions sharing the same underlying product,
- repeated fallback/fingerprint failures become drift signals.

## Target demo duration

Aim for roughly 5–8 minutes if recording. Most time should go to:
1. artifact,
2. deterministic replay/error behavior,
3. human handoff.

Those are more important than showing lots of code or UI polish.
