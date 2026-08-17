# 09 — Test and Evidence Plan

## Test philosophy

Test the load-bearing decisions, not every template line.

Use deterministic fixtures. Unit tests should not call the paid Claude API. One real LLM discovery run is captured separately in `/evidence/`.

## Required unit tests

### Artifact/schema
- valid example artifact serializes/loads
- invalid version/step/action rejected
- missing required input rejected
- sensitive invocation value never appears in serialized artifact after compilation
- output source step must exist
- locator strategy list cannot be empty for targeted actions

### Parameter binding
- input reference binds correct value at execution time
- unknown input reference fails before browser action
- type/pattern validation works

### Policy
- allowed local target route accepted
- external domain rejected before navigation
- unsupported action rejected
- risky/irreversible action returns approval-required decision
- artifact policy cannot broaden global policy

### Redaction
- sensitive dictionary keys redacted recursively
- `InputSpec.sensitive` values redacted in log event
- Authorization/API-key-like strings redacted
- human input/change event does not retain value

### Error taxonomy
- stable not-found UI maps to business outcome
- known interstitial maps to recoverable
- exhausted transient retry maps to hard failure
- unknown locator/checkpoint error maps to hard failure

### Result models
- success/business_outcome/failure/escalated contracts validate
- sensitive outputs are present in return object but log serialization redacts them

### Handoff state machine
- AUTOMATION -> PAUSED -> HUMAN -> PAUSED -> AUTOMATION allowed
- invalid double ownership transition rejected
- abort terminal state enforced

## Required integration tests

1. **Deterministic replay success**
   - start demo app
   - load a fixture/example artifact
   - replay `M-10001`
   - assert success and expected decimal balance
   - assert no model client was called

2. **Business outcome**
   - replay unknown member
   - assert `business_outcome/MEMBER_NOT_FOUND`

3. **Recoverable condition**
   - enable known interstitial or transient load
   - assert recovery was logged and replay still succeeds

4. **Hard failure**
   - enable missing-control injection
   - assert structured failure includes step ID and evidence screenshot path

5. **Policy rejection**
   - attempt off-domain navigation action
   - assert SurfaceAdapter never executes it

6. **Handoff**
   - state-machine/in-process integration is mandatory; full browser manual interaction can be demo/manual evidence if hard to automate in pytest.

## Offline discovery test

Use a scripted fake model adapter that returns deterministic structured actions. This verifies orchestration/compiler wiring without spending API tokens. Label it clearly as a test double.

## Real evidence run

Before submission, with `ANTHROPIC_API_KEY` set:

### Evidence 1 — genuine discovery
Goal:

```text
Look up member M-10001 and return their current savings balance.
```

Save:
- `evidence/discovery_run.jsonl`
- `evidence/discovery_trace.zip` if implemented
- selected screenshots if useful
- resulting `evidence/example_capability.json` (copy of actual generated artifact)

### Evidence 2 — deterministic success replay
Invoke same artifact with another valid synthetic member such as `M-10003`.

Save:
- `evidence/replay_success.jsonl`
- trace optional
- structured result JSON optional

This demonstrates parameterization rather than simply replaying the discovery literal.

### Evidence 3 — exceptional replay
Replay with `M-40400` for known business outcome and/or injected hard failure.

Prefer including both if easy:
- `evidence/replay_not_found.jsonl`
- `evidence/replay_failure.jsonl`
- `evidence/failure_screenshot.png`

The assignment only asks ideally for at least one exceptional case; more is useful only if clean.

### Evidence 4 — handoff
Capture logs/screenshots for a risky sub-account confirmation handoff:
- intervention created
- ownership transfer
- human action metadata
- resume/checkpoint

Optional short screen recording is welcome but not required.

## Evidence hygiene

Before committing `/evidence/`:
- inspect files for API keys/tokens,
- verify typed sensitive values are redacted in logs,
- synthetic values are clearly fictional,
- do not include browser cookies/local storage dumps,
- README explains what each evidence file proves.
