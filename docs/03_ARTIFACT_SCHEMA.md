# 03 — Capability Artifact Schema

This is the focal design artifact. Implement it with Pydantic v2 and serialize as readable JSON.

## Design goals

The artifact must be:
- typed,
- parameterized,
- versioned,
- human-reviewable,
- agent-invocable,
- independent of a raw LLM transcript,
- deterministic enough for replay,
- explicit about error/recovery behavior,
- compatible with future surface adapters and tenant overrides.

## Top-level shape

Recommended conceptual schema:

```json
{
  "schema_version": "1.0",
  "capability_id": "member.get_savings_balance",
  "capability_version": "1.0.0",
  "name": "Get member savings balance",
  "description": "Searches a member and returns the current savings balance.",
  "approval_state": "draft",
  "risk_level": "safe",
  "target": {},
  "contract": {},
  "preconditions": [],
  "steps": [],
  "success_conditions": [],
  "error_rules": [],
  "policy": {},
  "provenance": {}
}
```

## Target metadata

```python
class TargetAppSpec(BaseModel):
    app_id: str                       # e.g. mock_credit_union_admin
    vendor_family: str | None         # future reuse grouping
    surface_kind: Literal["web"]     # prototype; schema should be extensible
    entry_point: str                  # URL template or named entry point
    compatible_variants: list[str] = []
    app_fingerprint: dict[str, str] = {}
```

Do not over-engineer the fingerprint. A few stable markers (app title, route family, version marker) are enough for the prototype.

## Typed invocation contract

```python
class InputSpec(BaseModel):
    name: str
    type: Literal["string", "integer", "decimal", "boolean"]
    required: bool = True
    description: str
    sensitive: bool = False
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None

class OutputSpec(BaseModel):
    name: str
    type: Literal["string", "integer", "decimal", "boolean"]
    description: str
    sensitive: bool = False
    source_step_id: str

class CapabilityContract(BaseModel):
    inputs: list[InputSpec]
    outputs: list[OutputSpec]
```

For the demo balance capability:

```text
input: member_id: string, sensitive=true, constrained to demo format
output: savings_balance: decimal, sensitive=true
```

Artifacts describe sensitive fields but must not embed the concrete invocation values.

## Parameter/value references

Do not store discovery literals for dynamic invocation data.

```python
class InputValueRef(BaseModel):
    kind: Literal["input"] = "input"
    name: str

class LiteralValue(BaseModel):
    kind: Literal["literal"] = "literal"
    value: str | int | float | bool
    sensitive: bool = False
```

Dynamic action values should look like:

```json
{"kind":"input","name":"member_id"}
```

not:

```json
{"value":"12345"}
```

## Target descriptor and locator strategies

A target must describe **what control is intended**, with an ordered fallback strategy chain.

```python
class LocatorStrategy(BaseModel):
    kind: Literal[
        "role_name",
        "label",
        "placeholder",
        "text",
        "stable_attribute",
        "css",
        "frame_path"
    ]
    role: str | None = None
    name: str | None = None
    value: str | None = None
    attribute: str | None = None
    exact: bool = True
    confidence: float | None = None

class TargetDescriptor(BaseModel):
    description: str
    strategies: list[LocatorStrategy]
```

Priority for web replay:
1. role + accessible name
2. associated label
3. placeholder
4. exact visible text
5. stable `name`/other durable attribute
6. restrained CSS
7. frame-aware strategy where necessary

Absolute XPath and `nth-child` are last-resort only. Coordinate targeting is **not** a normal replay strategy; if discovery required a coordinate, the compiler should try to resolve the interacted element to a semantic descriptor before saving.

## Step model

Suggested action kinds:

- `navigate`
- `click`
- `fill`
- `select`
- `extract`
- `wait_for`
- `assert`

The LLM discovery action contract may additionally use `done` and `request_human`, but those are control signals and need not become ordinary artifact steps.

```python
class StepSpec(BaseModel):
    id: str
    name: str
    action: str
    target: TargetDescriptor | None = None
    value: InputValueRef | LiteralValue | None = None
    output_name: str | None = None
    timeout_ms: int | None = None
    risk: Literal["safe", "reversible", "risky", "irreversible"] = "safe"
    checkpoint_after: list[ConditionSpec] = []
    on_error: StepErrorPolicy | None = None
```

## Conditions

Support a small, testable set instead of an over-generic expression language:

```python
class ConditionSpec(BaseModel):
    kind: Literal[
        "url_matches",
        "text_present",
        "text_absent",
        "element_present",
        "element_absent",
        "element_value_matches"
    ]
    target: TargetDescriptor | None = None
    value: str | None = None
    timeout_ms: int | None = None
```

Use conditions for:
- post-step checkpoint,
- final success verification,
- known business-outcome detectors,
- known recoverable-state detectors.

## Error rules

```python
class ErrorRule(BaseModel):
    code: str
    classification: Literal["business_outcome", "recoverable", "hard_failure"]
    when: list[ConditionSpec]
    recovery: list[RecoveryAction] = []
    max_attempts: int = 0
    caller_message: str
```

Examples:
- `MEMBER_NOT_FOUND` -> business_outcome
- `VALIDATION_REJECTED` -> business_outcome
- `KNOWN_INTERSTITIAL` -> recoverable, dismiss then retry
- `TRANSIENT_LOAD_TIMEOUT` -> recoverable, wait/retry <= 2
- unknown target/checkpoint mismatch -> hard failure

## Policy metadata

```python
class CapabilityPolicy(BaseModel):
    allowed_domains: list[str]
    allowed_route_patterns: list[str]
    allowed_actions: list[str]
    max_unattended_risk: Literal["safe", "reversible", "risky", "irreversible"]
    require_human_for: list[str]
```

The artifact can narrow global policy, never broaden it.

## Provenance

```python
class Provenance(BaseModel):
    discovery_run_id: str
    discovered_at: datetime
    discovery_model: str
    source_app_fingerprint: dict[str, str]
```

Do not store raw chain-of-thought. A concise model/action rationale may be in redacted run evidence, not the production capability contract.

## Example capability that must be generated

Primary capability:

```text
member.get_savings_balance(member_id: string) -> savings_balance: decimal
```

Expected flow:
1. navigate to Member Search
2. fill member ID from input
3. click Search
4. detect `MEMBER_NOT_FOUND` if present
5. open member detail/accounts if result exists
6. extract savings balance
7. verify Accounts/Savings checkpoint
8. return structured output

A second small risky flow is useful for handoff:

```text
member.open_sub_account(member_id: string, account_type: string) -> review_reached: boolean
```

The automated capability should stop at or before the irreversible final-confirm action and route human approval if the demo exercises confirmation.
