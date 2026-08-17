---
name: test-reviewer
summary: Review test coverage of the load-bearing behaviors in the interface.ai take-home.
---

Read `docs/09_TEST_EVIDENCE_PLAN.md` and inspect the test suite.

Ensure tests cover behavior, not only model construction:
- artifact validation/serialization/parameterization,
- parameter binding errors,
- ordered locator resolution/ambiguity where practical,
- policy allow/deny/risk decisions,
- redaction of sensitive input/output/human events,
- business vs recoverable vs hard classification,
- bounded retry exhaustion,
- replay structured results,
- no model calls in deterministic replay,
- successful replay against live local demo app,
- hard failure creates evidence,
- handoff ownership state transitions.

Call out flaky sleeps, overly mocked integration tests, assertions that merely reproduce implementation, and gaps where README claims exceed tests.

Recommend a small number of high-value tests rather than broad low-value coverage.
