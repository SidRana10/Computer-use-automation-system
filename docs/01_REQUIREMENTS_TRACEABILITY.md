# 01 — Requirements Traceability

This file translates the assignment into implementable checks. Claude must keep every MUST item covered by code and/or required design write-up.

## A. Goal-driven discovery loop

| ID | Requirement | Implementation | Evidence/Test |
|---|---|---|---|
| A1 | Accept natural-language goal + target | CLI/API `discover` command | README demo command |
| A2 | Observe live surface | screenshot + URL/title + visible semantic element inventory | discovery log + screenshot/trace |
| A3 | LLM decides next action | Anthropic Messages API, structured action schema | discovery log contains model action summaries |
| A4 | Actually act on UI | Playwright click/fill/select/navigate/extract | real browser demo |
| A5 | Stop on success | explicit `done` action + final success condition validation | discovery success evidence |
| A6 | Stop on max steps/timeout/dead end | Orchestrator guards + repeated-state/action detection | tests + failure log |
| A7 | Bias toward heterogeneous surfaces | `SurfaceAdapter` and hybrid visual/semantic observation | REPORT §4 |

## B. Structured capability artifact

| ID | Requirement | Implementation | Evidence/Test |
|---|---|---|---|
| B1 | Ordered reusable steps | `CapabilityArtifact.steps` | example artifact |
| B2 | Robust target identification | ordered `LocatorStrategy[]` | artifact + locator tests |
| B3 | Typed inputs | `InputSpec` | schema tests |
| B4 | Typed outputs/data shape | `OutputSpec` | schema + replay result |
| B5 | Checkpoint/success condition | `ConditionSpec` | artifact + replay verification |
| B6 | Versioned/reviewable | capability version + schema version + metadata | artifact |
| B7 | Decoupled from raw model transcript | compiler produces normalized artifact | code + no transcript fields in artifact |
| B8 | Parameterized values | `ValueRef(input=...)` rather than discovery literal | artifact test |

## C. Deterministic replay

| ID | Requirement | Implementation | Evidence/Test |
|---|---|---|---|
| C1 | Replay saved artifact + inputs | `replay` command | replay log |
| C2 | No LLM decisions | dependency graph/replay engine has no model client | test/mock assertion |
| C3 | Stable control targeting | LocatorResolver | tests |
| C4 | Verify success | condition evaluator | replay result |
| C5 | Return declared outputs | extraction/binding | success replay evidence |
| C6 | Business outcomes | taxonomy/known UI detectors | not-found demo |
| C7 | Recoverable conditions | retry/known interstitial handler | injected slow/dialog demo/test |
| C8 | Hard failures | structured failure with step/expected/observed | failure screenshot/log |
| C9 | Clear result contract | `RunResult` discriminated model | schema tests |

## D. Safety and privacy

| ID | Requirement | Implementation | Evidence/Test |
|---|---|---|---|
| D1 | Configurable allowlist | `PolicyConfig` domains/routes/actions | policy test |
| D2 | Block out-of-policy action | `PolicyEngine.check()` before SurfaceAdapter | negative test |
| D3 | Distinguish risk | SAFE/REVERSIBLE/RISKY/IRREVERSIBLE | artifact + policy tests |
| D4 | Conservative risky behavior | human approval required for RISKY/IRREVERSIBLE | handoff demo |
| D5 | No secrets in artifacts/logs | no credential schema; central redactor | redaction tests |
| D6 | PII redaction | sensitive field metadata + redactor | logs/evidence review |

## E. Observability

| ID | Requirement | Implementation | Evidence/Test |
|---|---|---|---|
| E1 | Structured record of actions and why | JSONL RunLogger | evidence logs |
| E2 | Richer failure signal | screenshot + optionally Playwright trace | evidence file |
| E3 | Debuggable identifiers | run_id, capability_id, step_id, classification | logs |

## F. Human-in-the-loop

| ID | Requirement | Implementation | Evidence/Test |
|---|---|---|---|
| F1 | Detect stuck/blocked/risky | orchestrator + policy/error classifier | intervention test |
| F2 | Route intervention with context | `InterventionRequest` store + operator UI | screenshot/demo |
| F3 | Same live session | browser/context/page kept alive | handoff demo |
| F4 | Explicit control owner | state machine AUTOMATION/PAUSED/HUMAN | tests |
| F5 | Human can take control | operator button + headed browser | demo |
| F6 | Human can hand back | Resume endpoint/button | demo |
| F7 | Preserve context/evidence | same run ID, before/after observations | logs |
| F8 | Record human actions | injected redacted click/change/navigation capture | human-action evidence |

## G. Heterogeneity and scale (design)

Must be addressed in `REPORT.md` even if not implemented:

- `SurfaceAdapter` is the seam: PlaywrightWebSurface today; Accessibility/Desktop/Vision surface later.
- Artifact actions are surface-neutral enough to map to other adapters.
- TargetDescriptor can carry strategy types relevant to each surface.
- Vendor-family/base capability + tenant/version overrides rather than per-tenant copies.
- Target-app fingerprint/version and replay telemetry support drift detection.
- Never claim desktop or multi-tenant support is implemented; clearly mark design-only.

## H. Deliverables

- public repository
- `/README.md` setup + exact discovery and replay commands
- `/REPORT.md` approx. 1–3 pages with exact seven headings
- `/evidence/` example artifact + discovery log + replay log(s); include exceptional replay if possible
- secrets excluded

## I. Evaluation emphasis

Claude should self-review in this order:
1. system design
2. core loop correctness
3. robustness/error handling
4. human escalation
5. generalization story
6. safety/data handling
7. code quality
8. communication
