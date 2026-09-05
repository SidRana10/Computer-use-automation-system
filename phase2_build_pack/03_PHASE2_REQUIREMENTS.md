# Phase 2 Product Requirements — MERIDIAN CORE

## Product intent

Prove that the existing computer-use capability core is real and reusable by adapting it to a deliberately messy legacy credit-union UI.

The desired path is:

capabilities recorded once -> exposed as an API an agent can call -> invoked from a chatbot -> results/evidence visible on a dashboard

The adaptation should be configuration + adapter work wherever possible, not a rewrite.

## Target application

MERIDIAN CORE at:
https://web-sample.interface-hiring.com

Characteristics:
- server-rendered HTML
- table-based layout
- numbered/menu-oriented legacy navigation
- no test IDs or clean component boundaries
- per-transaction hidden token that must be read from the page before submission
- idle session timeout
- supervisor-gated restricted actions
- UI is the only integration surface

Demo users:
- `teller1` / `password` / teller
- `super1` / `password` / supervisor

Seed members:
- 100234
- 100987
- 101555
- 102777
- 103001

One member has a share already on HOLD.

## Required capabilities

Record and support deterministic replay for every function:

1. Sign on / session
   - operator ID
   - password
   - branch
   - idle timeout handling

2. Member inquiry / selection
   - search by member number
   - search by last name

3. Member record / balance
   - read shares
   - balances
   - status

4. Funds Transfer
   - from-share
   - to-share
   - amount
   - memo
   - review
   - post
   - irreversible

5. Open New Share
   - share type
   - initial deposit
   - review
   - post

6. Update Member Information
   - email
   - phone
   - mailing address

7. Place Account Hold
   - share
   - reason code
   - notes
   - review
   - post
   - risky/irreversible
   - supervisor override required

At minimum balance and transfer must be especially robust, but do not omit whole capabilities.

## Runtime / exceptional states

The application can inject or naturally produce these states:

- validation / HTTP 400
  - field or transaction rejection
- notfound / HTTP 404
  - member not found
- permission / HTTP 403
  - supervisor override required
- timeout / HTTP 440
  - session expired mid-flow
- maintenance / HTTP 503
  - maintenance interstitial
- server / HTTP 500
  - hard application error

Natural business/application outcomes include:
- bad login
- insufficient funds / overdraw
- invalid email or phone
- hold attempted by non-supervisor
- idle session timeout

The replay layer must distinguish:

### Business outcome
Expected domain result. Example: member not found, insufficient funds, invalid field.
Do not mislabel it as infrastructure failure or retry indefinitely.

### Recoverable condition
Known transient or resumable state. Example: known interstitial, expired session where safe re-authentication/resume is possible, transient maintenance if policy permits retry.

### Hard failure
Unknown/unrecoverable server or UI state. Stop, preserve evidence, return structured failure.

### Escalation
The system is blocked by a risky permission/approval/human requirement or cannot continue safely. Pause with context and provide a handoff/resume path.

## Capability API

Expose a callable catalog where a caller can:
- list capabilities and their typed schemas
- invoke a capability by stable name/version
- provide typed arguments
- receive a structured result
- receive status/error/escalation metadata
- obtain run/evidence identifiers

The caller must not need to know MERIDIAN UI details.

Each invocation must execute deterministic replay under the existing safety policy.

## Thin chatbot

The chatbot should:
- understand a simple user request
- select the correct capability
- extract/validate typed arguments
- call the capability API
- clearly report success, business outcome, recoverable failure, hard failure, or escalation
- surface useful structured results such as balances or confirmation numbers

Do not make the chatbot a second automation engine.

## Lightweight dashboard

Show:
- capability catalog
- discovery and replay run history
- run inputs
- structured outputs
- status: success / business outcome / recoverable / failed / escalated
- steps
- screenshots
- DOM snapshots
- timings
- logs/evidence

Keep it simple and reliable.

## Safety / privacy / escalation

Preserve:
- route/action allowlists
- conservative handling of irreversible writes
- supervisor gating
- human approval where appropriate
- no persistence of secrets
- redaction of regulated/sensitive financial data in durable evidence where required
- evidence/tracing
- stop-and-escalate behavior
- policy enforcement for recovery actions as well as primary actions

## Demo requirement

A reviewer should be able to:
1. open chatbot or dashboard;
2. request a task;
3. watch deterministic replay drive MERIDIAN CORE;
4. see a correct structured result;
5. inspect evidence;
6. see at least one deliberately triggered exceptional state handled cleanly;
7. ideally see a real escalation such as teller -> supervisor-required Place Hold.
