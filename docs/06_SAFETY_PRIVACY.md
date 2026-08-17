# 06 — Safety, Policy, and Privacy

## Principle

The model proposes; deterministic policy code decides whether an action may execute.

Policy is enforced at the action boundary in both discovery and replay.

## Policy configuration

Implement a typed configurable policy with at least:

```yaml
allowed_domains:
  - 127.0.0.1
  - localhost
allowed_ports:
  - 8001
allowed_route_patterns:
  - /login-demo
  - /members/**
  - /accounts/**
allowed_actions:
  - navigate
  - click
  - fill
  - select
  - extract
  - wait_for
  - assert
max_unattended_risk: reversible
require_human_for:
  - risky
  - irreversible
```

Exact routes can differ with implementation.

## Risk levels

- **safe** — read/extract/navigation with no state mutation
- **reversible** — input/edit before submission or other easily undone local state
- **risky** — meaningful state mutation that may have consequences
- **irreversible** — final confirmation/destructive/financial action

For the demo, risky and irreversible actions should pause and require human approval/takeover.

## Policy composition

There may be:
- global policy,
- target-app policy,
- artifact-specific policy.

Effective policy must be the intersection/strictest combination. A capability artifact must never broaden global privileges.

## URL/domain protection

Before navigation:
- parse URL,
- normalize hostname/port,
- reject non-HTTP(S) schemes unless explicitly supported,
- reject host outside allowlist,
- reject route outside allowed route patterns,
- do not follow an externally injected redirect silently; after navigation verify current URL remains in policy.

## No arbitrary code

LLM discovery must not receive arbitrary code execution or JS evaluation as an action. Surface adapter internally may use known static JavaScript snippets for observation/event instrumentation, but model-controlled script content is forbidden.

## Sensitive data model

Even though demo data is synthetic, implement the system as if member/account values were sensitive.

Mark contract fields with `sensitive: true` and centralize redaction.

### Must never be persisted
- `ANTHROPIC_API_KEY`
- credentials/passwords/session tokens/cookies
- authorization headers
- raw member identifiers in normal logs
- typed sensitive field values
- full account numbers/SSNs or equivalent synthetic placeholders
- raw page dumps containing sensitive data unless specifically redacted/sanitized for evidence

### Allowed persisted metadata
- field name (`member_id`)
- value type
- redacted representation (`[REDACTED]`)
- hash/fingerprint only if needed for correlation and keyed/salted appropriately; simplest demo can avoid this entirely

## Redaction

Implement one Redactor used by loggers, evidence metadata, error observations, and human-action capture.

Redact by:
- known sensitive key names (`member_id`, `account_number`, `password`, `token`, `authorization`, `api_key`, etc.)
- `InputSpec.sensitive` / `OutputSpec.sensitive`
- common secret patterns
- human `input`/`change` event values — log element identity and `value_changed=true`, never value

Do not pretend screenshots are automatically safe. For the controlled synthetic demo, document that screenshots contain only fictional demo data. In a real bank environment, screenshots would need secure ephemeral storage/access controls and potentially region/redaction policy.

## Logs

Good:

```json
{"action":"fill","field":"Member ID","value":"[REDACTED]"}
```

Bad:

```json
{"action":"fill","field":"Member ID","value":"12345"}
```

## Secrets management

- `.env` in `.gitignore`
- `.env.example` with blank/example-safe values
- runtime reads env vars
- repository scan before completion for `sk-ant-`, API key patterns, `.env`, cookies, tokens

## Safety tests

Must include:
- navigate to disallowed domain -> blocked before Playwright action
- unsupported action kind -> blocked
- irreversible action unattended -> escalation/approval required
- logger redacts sensitive input
- artifact serialization never embeds bound sensitive invocation value
