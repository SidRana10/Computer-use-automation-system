# 07 — Human Escalation and Same-Session Handoff

## Goal

Demonstrate a real control-transfer seam without building a full co-browsing product.

The browser/context/page used by automation must remain alive while the human takes over.

## State machine

```text
AUTOMATION
   |
   | stuck / policy approval / hard failure eligible for help
   v
PAUSED
   |
   | operator clicks Take Control
   v
HUMAN
   |  \
   |   \ Abort -> ABORTED
   |
   | operator clicks Resume
   v
PAUSED / VALIDATING
   |
   | checkpoint/re-observation passes
   v
AUTOMATION
```

Track state in typed models; do not represent control only as console text.

## InterventionRequest

Include at least:

```python
class InterventionRequest(BaseModel):
    intervention_id: str
    run_id: str
    mode: Literal["discovery", "replay"]
    capability_id: str | None
    goal_summary: str
    step_id: str | None
    reason_code: str
    reason_message: str
    control_owner: ControlOwner
    screenshot_path: str
    current_url: str
    created_at: datetime
    status: Literal["open", "claimed", "resumed", "aborted", "resolved"]
    operator_id: str | None
```

Do not place raw sensitive values in the request.

## Minimal operator console

A tiny FastAPI/Jinja app is enough. It should show:

- open intervention(s)
- run ID / capability / current step
- reason
- current redacted URL/context
- current screenshot
- current control owner
- buttons: `Take Control`, `Resume Automation`, `Abort`
- optional operator note

Do not spend time on visual polish.

## Same-session mechanism

Use headed Playwright for demo.

When intervention is created:
1. automation stops issuing surface actions,
2. Playwright browser/context/page remain open,
3. operator console changes owner to HUMAN only through a guarded transition,
4. human manually uses the already-open browser window,
5. event instrumentation records human interaction metadata,
6. operator clicks Resume,
7. handoff manager gathers human events and a fresh observation/screenshot,
8. control moves to PAUSED/VALIDATING,
9. resume checkpoint is evaluated,
10. if valid, control returns to AUTOMATION; otherwise remain escalated with a clear reason.

## Recording human actions

For the web prototype, inject an event listener using a static trusted script, preferably with `browser_context.add_init_script`, that records only safe metadata for events while `control_owner == HUMAN`.

For same-origin web navigation, a practical implementation is to keep the `human_mode` flag and redacted event buffer in `sessionStorage` so the init script survives page navigations; retrieve and clear the buffer on Resume. Do not store typed values in that buffer.

Capture things like:

```json
{
  "event":"click",
  "tag":"button",
  "text":"Continue",
  "aria_label":null,
  "timestamp":"..."
}
```

For text inputs:

```json
{
  "event":"change",
  "tag":"input",
  "name":"member_id",
  "value_changed":true,
  "value":"[REDACTED]"
}
```

Also record navigation URL (redacted/allowlisted) and before/after screenshot paths.

This event capture is only a prototype analogue of production co-browsing/audit instrumentation; state that limitation in REPORT.

## Demo escalation scenarios

At least one should work end-to-end.

Preferred scenario: risky sub-account confirmation.

```text
artifact/replay reaches Review New Sub-Account
  -> next action is risk=irreversible
  -> PolicyEngine returns HUMAN_APPROVAL_REQUIRED
  -> intervention created
  -> automation pauses
  -> operator takes control
  -> human clicks final Confirm in same browser
  -> operator resumes
  -> automation verifies confirmation screen
  -> run completes / returns structured output
```

Also permit hard-failure escalation, but do not make every failure recover via human; some should remain clear failures.

## Concurrency scope

A single active local run is enough for the submission. Use a lock/ownership check so both human and automation cannot issue actions simultaneously. Explain how a production implementation would use durable session leases/locks, but do not build distributed coordination.
