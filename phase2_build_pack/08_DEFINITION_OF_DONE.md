# Definition of Done

Do not call the project complete until these are checked.

## Core adaptation
- [ ] MERIDIAN support is implemented as adapter/config/generalization rather than a parallel rewrite.
- [ ] Original Northstar behavior remains working or any compatibility change is explicitly documented.
- [ ] Existing discovery loop is reused.
- [ ] Existing typed/versioned capability artifact system is reused.
- [ ] Existing deterministic replay engine is reused.
- [ ] No LLM decides normal replay actions.

## Required capabilities
- [ ] Sign on/session
- [ ] Member inquiry by member number
- [ ] Member inquiry by last name
- [ ] Member record/balance
- [ ] Funds Transfer
- [ ] Open New Share
- [ ] Update Member Information
- [ ] Place Account Hold

## Transfer / irreversible correctness
- [ ] Hidden transaction token is dynamically extracted, never hardcoded.
- [ ] Review screen is validated before post.
- [ ] Irreversible action policy/approval still applies.
- [ ] Replay/recovery cannot accidentally duplicate an uncertain post.
- [ ] Successful transaction returns structured confirmation.

## Exceptional states
- [ ] validation/400 classified deliberately
- [ ] notfound/404 classified deliberately
- [ ] permission/403 classified deliberately
- [ ] timeout/440 classified deliberately
- [ ] maintenance/503 classified deliberately
- [ ] server/500 classified deliberately
- [ ] natural bad login handled
- [ ] natural insufficient funds handled
- [ ] invalid email/phone handled
- [ ] teller hold attempt handled
- [ ] business outcome vs recoverable vs failed vs escalated are distinct

## Safety
- [ ] PolicyEngine remains mandatory for browser actions.
- [ ] Recovery actions also go through PolicyEngine.
- [ ] Route/action allowlists cover MERIDIAN without unsafe broadening.
- [ ] Risky/irreversible actions fail closed.
- [ ] Supervisor-only behavior cannot be bypassed by API/chatbot/dashboard.
- [ ] Secrets are not committed or persisted.
- [ ] Sensitive financial data is redacted in durable evidence according to project policy.

## Evidence / observability
- [ ] discovery evidence exists
- [ ] replay evidence exists
- [ ] screenshots available
- [ ] DOM snapshots/equivalent evidence available
- [ ] timings/logs available
- [ ] run IDs link API/chatbot/dashboard results to evidence

## Capability API
- [ ] catalog/list supported
- [ ] stable capability name/version
- [ ] typed input schema
- [ ] typed/structured output schema
- [ ] structured error/business/recovery/escalation envelope
- [ ] run/evidence ID returned
- [ ] API only invokes deterministic replay

## Chatbot
- [ ] chatbot maps natural request to capability
- [ ] typed args validated
- [ ] chatbot calls API only
- [ ] no direct Playwright path
- [ ] success/error/escalation messages are clear

## Dashboard
- [ ] capability catalog visible
- [ ] run history visible
- [ ] inputs visible
- [ ] structured outputs visible
- [ ] status visible
- [ ] steps visible
- [ ] evidence visible
- [ ] timings/logs visible

## Testing
- [ ] targeted MERIDIAN tests pass
- [ ] original regression tests pass
- [ ] full suite passes
- [ ] live balance verified
- [ ] live transfer verified
- [ ] at least one injected exceptional state verified
- [ ] escalation path verified

## Deliverables
- [ ] README updated
- [ ] exact setup/run commands documented
- [ ] exact demo path documented
- [ ] 1–2 page write-up complete
- [ ] intentional cut lines documented
- [ ] next steps documented
- [ ] backup evidence/recording prepared where practical

## Final review
- [ ] Fable final verdict is `SUBMIT`, or all cited blockers are fixed and independently rechecked.
