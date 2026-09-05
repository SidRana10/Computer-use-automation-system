# Demo and Deliverables

## Recommended live demo sequence

Keep the demo short and deterministic.

### 1. Show architecture quickly
Explain:
- LLM is used for discovery/recording.
- Production execution uses deterministic replay.
- MERIDIAN is a new target adapter/configuration on the existing core.
- API hides UI details from callers.

### 2. Successful read flow
From chatbot:
- request balance for member `100234`.

Show:
chatbot -> API -> deterministic replay -> MERIDIAN -> structured result.

Then open dashboard run detail and show:
- capability name/version
- typed input
- success status
- structured output
- steps/evidence/timing

### 3. Successful irreversible flow
Run a small transfer using a safe sample-member setup.

Show:
- dynamic hidden token read from the page
- review step
- post step
- confirmation number
- evidence

Do not expose secrets or unredacted sensitive values in durable logs.

### 4. Exceptional-state flow
Use one deterministic injected condition, preferably a clear business/recoverable state.

Examples:
- notfound -> business outcome
- maintenance -> recoverable/failed according to bounded policy

Show that the system deliberately classifies the result rather than crashing.

### 5. Escalation flow
Use teller credentials to attempt Place Account Hold.

Expected story:
- MERIDIAN requires supervisor permission
- system does not bypass it
- run pauses/escalates with context
- dashboard shows `ESCALATED` / supervisor requirement
- if handoff/resume is implemented, show the safe continuation path

## README must include

- prerequisites
- install commands
- environment variables / model keys
- how to run MERIDIAN target
- how to run discovery
- how to replay a capability directly
- how to run capability API
- how to run chatbot
- how to run dashboard
- exact demo commands/URLs
- offline/mock mode if provided
- test commands
- safety/redaction notes
- known limitations

## 1–2 page technical write-up must cover

1. What adapting to MERIDIAN actually required.
2. Which Phase 1 components were reused unchanged.
3. Which core assumptions were too Northstar-specific and had to be generalized.
4. Why each generalization was necessary.
5. Capability API contract and why it is UI-agnostic.
6. How the legacy UI is driven reliably.
7. Dynamic transaction token handling.
8. Review -> post handling and irreversible-action safety.
9. Runtime error taxonomy and recovery rules.
10. Supervisor gating / escalation.
11. How PolicyEngine, redaction, evidence, and handoff remain intact through API/chatbot/dashboard.
12. What was intentionally cut and what would be next.

## Backup assets

Have ready:
- screenshots/evidence for successful balance
- successful transfer confirmation evidence
- injected exceptional-state evidence
- escalation/handoff evidence
- short screen recording if practical

The live network may fail; the backup should prove the same behavior.
