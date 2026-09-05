# 13 — Acceptance Scenarios and Intended CLI

> **Phase 1 historical.** This file drove the original Northstar build. Phase 2 (MERIDIAN CORE) is governed by `phase2_build_pack/`. Kept for provenance; not a current instruction.

Claude Code should implement a CLI close to this contract so the README/demo is simple and reproducible. If a library-specific limitation forces a naming change, keep equivalent functionality and document it.

## Console entry point

Expose a console script named:

```text
uicap
```

## Intended commands

### Start demo target app

```bash
uicap demo-app --host 127.0.0.1 --port 8001
```

This can internally run FastAPI/Uvicorn.

### Discover a capability

```bash
uicap discover \
  --goal "Look up member M-10001 and return their current savings balance." \
  --target http://127.0.0.1:8001 \
  --capability-id member.get_savings_balance \
  --input member_id=M-10001 \
  --output artifacts/member.get_savings_balance.v1.json
```

Behavior:
- launch headed browser unless `--headless`,
- start local operator console in-process or otherwise make it reachable if escalation occurs,
- call Claude Fable 5 through configured model adapter,
- perform genuine discovery,
- save artifact and evidence/log paths,
- return structured terminal summary.

### Replay

```bash
uicap replay \
  --artifact artifacts/member.get_savings_balance.v1.json \
  --input member_id=M-10003
```

Behavior:
- no LLM decision calls,
- headed by default for demo,
- returns structured result and evidence path.

### Business-outcome replay

```bash
uicap replay \
  --artifact artifacts/member.get_savings_balance.v1.json \
  --input member_id=M-40400
```

Expected:

```text
status=business_outcome
code=MEMBER_NOT_FOUND
```

### Hard failure injection

Provide one clear dev-only flag, for example:

```bash
uicap replay \
  --artifact artifacts/member.get_savings_balance.v1.json \
  --input member_id=M-10003 \
  --demo-failure missing_accounts_control
```

If cleaner, the failure switch may be set on the demo app instead. README must give one deterministic procedure.

Expected:

```text
status=failure
code=TARGET_NOT_FOUND or CHECKPOINT_FAILED
step_id=<specific step>
evidence=<failure screenshot>
```

### Offline test discovery

Provide a clear test-only path, for example:

```bash
uicap discover \
  --goal "Look up member M-10001 and return their current savings balance." \
  --target http://127.0.0.1:8001 \
  --input member_id=M-10001 \
  --model-adapter fake \
  --output /tmp/test-artifact.json
```

Label this as a test double. It cannot be used for `evidence/discovery_run.jsonl`.

## Human handoff acceptance scenario

Provide a second fixture/artifact or discovery path for:

```text
Open a Holiday Savings sub-account for member M-10001 and reach the confirmation step.
```

The automated path may fill safe/reversible form fields and reach review. The final mutation action must be risk-classified so the policy creates an intervention.

Expected operator flow:
1. terminal reports intervention and operator URL,
2. operator page shows screenshot/reason/step,
3. click Take Control,
4. manually operate same headed browser,
5. click Resume Automation in operator page,
6. system re-observes/verifies confirmation checkpoint,
7. run finishes with structured result or designed post-human result,
8. logs show ownership transitions and redacted human actions.

## Test command

Prefer a single command:

```bash
pytest -q
```

Optionally add Make targets, but do not require Make for core setup.
