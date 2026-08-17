# Architecture Decision Log

Claude Code: append only meaningful deviations or trade-offs. Keep entries concise.

## D001 — Local target instead of public third-party site
**Decision:** Build a synthetic local legacy-style credit-union servicing app.
**Reason:** It avoids ToS/rate-limit issues, guarantees repeatable exceptional states, uses no real PII, and allows the submission to demonstrate the exact banking-like runtime failures in the brief.

## D002 — Single-process/local-first core
**Decision:** Keep the prototype simple and local, with explicit interfaces rather than scaling infrastructure.
**Reason:** The assignment rewards core abstractions and correctness, not premature queues/clusters/microservices.

## D003 — Hybrid visual + semantic discovery
**Decision:** Give the LLM a screenshot plus a compact semantic element inventory. Execute actions through Playwright.
**Reason:** Screenshot perception keeps the design credible for hostile/no-clean-DOM surfaces while semantic targets allow robust recording/replay on the concrete web implementation.

## D004 — Coordinates are not normal replay identity
**Decision:** Coordinates may be used as bounded discovery fallback/hints but artifacts must record stable locator strategy chains whenever possible.
**Reason:** Replay must be deterministic and robust to harmless viewport/layout variation.

## D005 — Human handoff uses headed browser + minimal operator console
**Decision:** Keep the same Playwright browser/context/page alive; automation pauses, an operator takes ownership and manipulates the existing headed browser, then resumes through a small local control page.
**Reason:** This proves the control-transfer seam without overbuilding real-time co-browsing.

## D006 — JSON artifacts and JSONL evidence
**Decision:** Use human-reviewable JSON capability artifacts and append-only JSONL run logs.
**Reason:** Easy to inspect, version, test, diff, and include in submission evidence.

## D007 — Sub-account capability contract extends to confirmation number
**Decision:** `member.open_sub_account(member_id, account_type) -> confirmation_number: string`, extracted after the human-approved confirm, instead of the suggested `review_reached: boolean`.
**Reason:** It demonstrates the full escalation arc (pause → human confirm in same session → resume → revalidate → extract → structured success) and gives the calling agent a genuinely useful output. The irreversible step itself is still never executed by automation.

## D008 — App error rules come from a per-app profile, applied by the compiler
**Decision:** Known business-outcome/recoverable/hard detectors (`MEMBER_NOT_FOUND`, `KNOWN_INTERSTITIAL`, `SESSION_EXPIRED`, …) live in `discovery/profiles.py` and are attached to artifacts at compile time.
**Reason:** These are deterministic vendor-app knowledge, not model output. In the multi-tenant design this is exactly what a vendor-family base capability would carry, with tenant overrides.

## D009 — Discovery risk classification is deterministic control-text policy
**Decision:** The PolicyEngine classifies control risk from configurable visible-text patterns (e.g. "confirm open account" → irreversible) in addition to declared step risk during replay.
**Reason:** During discovery no artifact risk annotation exists yet; the deterministic policy layer, not the model, must decide that a control is risky. Declared step risk can only raise, never lower, the effective risk in replay.

## D010 — Non-editable install used on the build machine
**Decision:** The build machine force-hides `*.pth` files (macOS flag), which Python 3.12+ site processing skips, breaking `pip install -e`. Locally the package is installed non-editable; `pytest` uses `pythonpath = ["src"]` so tests always run the working tree.
**Reason:** Machine quirk only. `pip install -e '.[dev]'` in the README remains correct for normal environments; a troubleshooting note covers this edge.

## D011 — Transient-load state requires an explicit reload recovery
**Decision:** The demo transient state renders a static "Accounts are loading" page (no auto-refresh); the artifact's `TRANSIENT_LOAD` rule recovers with bounded wait + reload.
**Reason:** With an auto-refreshing page, ordinary condition polling absorbed the delay and the recovery machinery was never exercised; a static interstitial makes the recoverable-condition path real and observable in evidence.

## D012 — CLI input specs from a small registry
**Decision:** `uicap discover --input name=value` maps known names (`member_id`, `account_type`) to typed/sensitive `InputSpec`s from a registry; unknown names become generic string inputs (sensitive when the name matches the redaction list).
**Reason:** In production the calling agent supplies the typed contract; a registry keeps the demo CLI honest without inventing a schema-definition flag language.
