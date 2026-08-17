# 10 — Repository, README, REPORT, and Submission Contract

## README.md must include

### What this is
One concise paragraph describing discovery -> capability artifact -> deterministic replay -> human handoff.

### Architecture at a glance
A small ASCII/Mermaid diagram and component descriptions.

### Prerequisites
- Python 3.12
- Playwright browser install
- Anthropic API key only for genuine discovery

### Setup
Exact commands that have actually been tested. Example shape:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
playwright install chromium
cp .env.example .env
```

Do not blindly use these commands if project packaging differs; README must match actual repo.

### Run target/operator services
Exact tested command(s).

### Demo: discovery
Exact command with goal and target.

### Demo: deterministic replay
Exact command using generated artifact and a *different* member ID to prove parameterization.

### Exceptional replay
Command for not-found or injected hard failure.

### Human handoff demo
Steps for operator console/take control/resume.

### Run tests
Exact `pytest`/Make command.

### Evidence
Explain each committed evidence file and which requirement it proves.

### Security note
Synthetic data only, secrets via env, log redaction, no real banking system.

### Limitations
Keep concise and align with REPORT Cuts.

## REPORT.md

Approx. 1–3 pages. Use **exactly** these seven top-level headings and in this order:

# 1. Architecture
# 2. Artifact schema
# 3. Determinism & error handling
# 4. Heterogeneity & multi-tenant
# 5. Escalation & handoff
# 6. Safety
# 7. Cuts

### 1. Architecture
Explain compiler/runtime mental model, main boundaries, why local-first/single-process, why hybrid screenshot+semantic observation, and trade-offs.

### 2. Artifact schema
This should be one of the strongest sections. Explain typed contract, parameterization, locator strategy chain, conditions, version/provenance, policy metadata, and why raw model transcripts are not artifacts.

### 3. Determinism & error handling
Explain no-LLM replay, stable targeting, condition/actionability waits, checkpoints, business/recoverable/hard taxonomy, bounded retries, failure evidence, and secondary drift handling.

### 4. Heterogeneity & multi-tenant
Be precise about implemented vs design-only.

Design story:
- SurfaceAdapter separates flow from perception/action technology.
- A desktop adapter could translate TargetDescriptor strategies to accessibility/UI Automation selectors and optionally visual coordinates.
- Base artifact belongs to vendor-family/app version.
- tenant variants reference base artifact plus narrow locator/route overrides.
- app fingerprint and replay telemetry detect drift.
- overrides are versioned/reviewed; repeated failures trigger revalidation rather than silent mutation.

Do **not** claim desktop/multi-tenant is implemented.

### 5. Escalation & handoff
Explain stuck/risky detection, intervention context, same Playwright session, explicit ownership state machine, human event capture, resume checkpoint, and why full co-browsing is cut.

### 6. Safety
Explain action/domain allowlist, stricter policy composition, risk classes/approval, redaction, secret handling, screenshot limitation in real regulated environment, and model-is-not-authority principle.

### 7. Cuts
Explicitly list intentional cuts, e.g.:
- only web adapter implemented
- single local operator/run
- no distributed session broker
- no production auth/operator RBAC
- no real banking system/credentials
- simple artifact file store instead of database/catalog
- no automatic cross-tenant canonicalization
- no open-ended LLM recovery during replay

Then state what would come next with more time.

## Public repository hygiene

Before final commit:
- no `.env`
- no API key
- no cookies/session state
- no large accidental Playwright browser files
- no `__pycache__`, `.pytest_cache`, venv
- licenses of dependencies normal/declared through package metadata
- README commands work from a clean clone
- evidence paths exist and are small enough for GitHub

## Optional stretch goal rule

Do not implement stretch goals until every core requirement is done and audited.

If core is solid, the best fit stretch goal is likely:
- small agent-facing capability catalog/typed invocation endpoint, **or**
- multi-run stability score.

Pick at most one. Do not risk the core submission for it.
