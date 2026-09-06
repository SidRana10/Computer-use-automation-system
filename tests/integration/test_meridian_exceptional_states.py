"""P5 exceptional-state matrix against the live MERIDIAN target.

Opt in with MERIDIAN_LIVE=1 (plus credentials); skipped otherwise so the
default suite stays hermetic and offline. Each of the six documented
`?inject=` states is exercised as a genuine per-request query parameter on a
plain member-record read — never via the global `/settings` fault-injection
console, which CLAUDE.md explicitly reserves for a human operator so the
shared demo app is never polluted for other users.

The seven production capability artifacts are all click-driven (member
selection happens by clicking a search result, not a `navigate` step with a
url_template), so there is no step whose URL a test can append `?inject=` to
without mutating a committed artifact. Instead this file builds one small,
test-only artifact — sign on, then `navigate` straight to
`/members/{member_number}` — reusing the exact same profile, policy,
error-rule factory, and `ReplayEngine` as the real capabilities. This is
deliberately not a production capability (no discovery run backs it, and nothing
persists it), only a fixture for exercising the real classification pipeline
against real HTTP responses.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

from ui_capabilities.config import Settings
from ui_capabilities.models.artifact import (
    CapabilityArtifact,
    CapabilityContract,
    CapabilityPolicy,
    Provenance,
    StepSpec,
    TargetAppSpec,
)
from ui_capabilities.models.conditions import ConditionKind, ConditionSpec
from ui_capabilities.models.errors import RiskLevel
from ui_capabilities.models.targets import LocatorKind, LocatorStrategy, TargetDescriptor
from ui_capabilities.observability.evidence import EvidenceManager
from ui_capabilities.observability.logger import RunLogger
from ui_capabilities.policy.engine import PolicyEngine
from ui_capabilities.policy.redaction import Redactor
from ui_capabilities.replay.engine import ReplayEngine
from ui_capabilities.surfaces.playwright_web import PlaywrightWebSurface
from ui_capabilities.targets import get_profile

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("MERIDIAN_LIVE") != "1", reason="set MERIDIAN_LIVE=1 to run live MERIDIAN tests"),
]


def _field(name: str, caption: str, kind: str = "textbox") -> TargetDescriptor:
    return TargetDescriptor(
        description=f"{kind} '{caption}'",
        strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value=name)],
    )


def _test_artifact(profile, inject: str | None) -> CapabilityArtifact:
    """Sign on, then navigate straight to the member record — optionally with
    a per-request `?inject=` query parameter on that one navigation only."""
    url_template = "/members/{member_number}"
    if inject:
        url_template += f"?inject={inject}"
    return CapabilityArtifact(
        capability_id="test.meridian_exceptional_state_probe",
        capability_version="1.0.0",
        name="Exceptional-state probe (test-only, never a production capability)",
        description="Sign on then read a member record, optionally with a per-request fault injected.",
        risk_level=RiskLevel.SAFE,
        target=TargetAppSpec(
            app_id=profile.app_id,
            vendor_family=profile.vendor_family,
            surface_kind="web",
            entry_point=profile.default_entry_point,
            app_fingerprint={"app_title": profile.title_marker},
        ),
        contract=CapabilityContract(
            inputs=[
                profile.input_specs["operator_id"],
                profile.input_specs["password"],
                profile.input_specs["branch"],
                profile.input_specs["member_number"],
            ],
            outputs=[],
        ),
        steps=[
            StepSpec(
                id="s1_fill",
                name="Fill Operator ID",
                action="fill",
                target=_field("operator", "Operator ID"),
                value={"kind": "input", "name": "operator_id"},
            ),
            StepSpec(
                id="s2_fill",
                name="Fill Password",
                action="fill",
                target=_field("password", "Password"),
                value={"kind": "input", "name": "password"},
            ),
            StepSpec(
                id="s3_select",
                name="Select Branch",
                action="select",
                target=_field("branch", "Branch", kind="combobox"),
                value={"kind": "input", "name": "branch"},
            ),
            StepSpec(
                id="s4_click",
                name="Click Sign On",
                action="click",
                target=TargetDescriptor(
                    description="button 'Sign On'",
                    strategies=[LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Sign On")],
                ),
                checkpoint_after=[ConditionSpec(kind=ConditionKind.URL_MATCHES, value="/menu")],
            ),
            StepSpec(
                id="s5_navigate",
                name="Open member record (optionally fault-injected)",
                action="navigate",
                url_template=url_template,
                checkpoint_after=[
                    ConditionSpec(kind=ConditionKind.URL_MATCHES, value="/members/*"),
                    ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="MEMBER RECORD"),
                ],
            ),
        ],
        success_conditions=[
            ConditionSpec(kind=ConditionKind.URL_MATCHES, value="/members/*"),
            ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="MEMBER RECORD"),
        ],
        error_rules=profile.error_rules_factory(),
        policy=CapabilityPolicy(
            allowed_domains=[profile.policy().allowed_domains[0]],
            allowed_route_patterns=["/signon", "/menu", "/members", "/members/**"],
            allowed_actions=["navigate", "click", "fill", "select", "wait_for", "assert"],
            max_unattended_risk=RiskLevel.REVERSIBLE,
            require_human_for=[RiskLevel.RISKY, RiskLevel.IRREVERSIBLE],
        ),
        provenance=Provenance(
            discovery_run_id="test-fixture-not-a-capability",
            discovered_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            discovery_model="test fixture (hand-authored; exercises the real replay/classification pipeline only)",
        ),
    )


async def _run(tmp_path, inject: str | None, member_number: str = "101555"):
    profile = get_profile("meridian")
    artifact = _test_artifact(profile, inject)
    settings = Settings(playwright_headless=True, evidence_dir=tmp_path / "evidence")
    evidence = EvidenceManager(settings.evidence_dir, f"live-exc-{uuid.uuid4().hex[:8]}")
    redactor = Redactor(text_patterns=profile.redaction_text_patterns)
    surface = PlaywrightWebSurface(
        settings,
        evidence,
        headless=True,
        heading_selector=profile.heading_selector,
        mask_selectors=profile.screenshot_mask_selectors,
        redactor=redactor,
        enable_tracing=profile.durable_traces,
    )
    engine = ReplayEngine(
        surface=surface,
        global_policy=PolicyEngine(profile.policy()),
        settings=settings,
        logger=RunLogger(evidence.log_path, redactor, evidence.run_id),
        evidence=evidence,
        redactor=redactor,
    )
    inputs = {
        "operator_id": os.environ.get("MERIDIAN_TELLER_ID", ""),
        "password": os.environ.get("MERIDIAN_TELLER_PASSWORD", ""),
        "branch": os.environ.get("MERIDIAN_BRANCH", "MAIN-001"),
        "member_number": member_number,
    }
    try:
        return await engine.replay(artifact, inputs)
    finally:
        await surface.close()


async def test_no_injection_reaches_the_member_record(tmp_path):
    result = await _run(tmp_path, None)
    assert result.status == "success", result.model_dump()


async def test_inject_validation_is_a_business_outcome(tmp_path):
    result = await _run(tmp_path, "validation")
    assert result.status == "business_outcome"
    assert result.code == "VALIDATION_REJECTED"


async def test_inject_notfound_is_a_business_outcome(tmp_path):
    result = await _run(tmp_path, "notfound")
    assert result.status == "business_outcome"
    assert result.code == "MEMBER_NOT_FOUND"


async def test_inject_permission_is_a_hard_failure(tmp_path):
    """SUPERVISOR_REQUIRED is a HARD_FAILURE classification (D016): whether it
    escalates is a separate, per-capability policy decision this probe
    artifact does not opt into."""
    result = await _run(tmp_path, "permission")
    assert result.status == "failure"
    assert result.code == "SUPERVISOR_REQUIRED"
    assert result.category == "hard_failure"


async def test_inject_timeout_is_a_hard_failure_and_destroys_the_session(tmp_path):
    """The session must not be treated as safely resumable: SESSION_EXPIRED
    is HARD_FAILURE, never RECOVERABLE, so replay stops rather than trying to
    continue a flow whose authenticated state no longer exists."""
    result = await _run(tmp_path, "timeout")
    assert result.status == "failure"
    assert result.code == "SESSION_EXPIRED"
    assert result.category == "hard_failure"


async def test_inject_maintenance_is_recoverable_and_bounded(tmp_path):
    result = await _run(tmp_path, "maintenance")
    # Either the bounded wait+reload recovers within budget (success) or it
    # is exhausted (failure/RETRY_EXHAUSTED) — both are acceptable outcomes of
    # a *bounded* policy-gated recovery; an unbounded retry would not be.
    if result.status == "success":
        return
    assert result.status == "failure"
    assert result.code in ("RETRY_EXHAUSTED", "MAINTENANCE_WINDOW")


async def test_inject_server_is_a_hard_failure(tmp_path):
    result = await _run(tmp_path, "server")
    assert result.status == "failure"
    assert result.code == "APPLICATION_ERROR"
    assert result.category == "hard_failure"


async def test_unrecognized_inject_value_is_ignored_by_the_target_and_succeeds(tmp_path):
    """MERIDIAN ignores an unrecognized `?inject=` value outright (verified
    live) rather than erroring — this pins that our own system does not
    misclassify the resulting *normal* page as anything else."""
    result = await _run(tmp_path, "not_a_real_injection_value_xyz")
    assert result.status == "success", result.model_dump()


async def test_bad_login_is_a_business_outcome_via_the_probe(tmp_path):
    """A natural (non-injected) business outcome, exercised through the same
    probe for completeness: wrong credentials never reach the member record."""
    profile = get_profile("meridian")
    artifact = _test_artifact(profile, None)
    settings = Settings(playwright_headless=True, evidence_dir=tmp_path / "evidence")
    evidence = EvidenceManager(settings.evidence_dir, f"live-badlogin-{uuid.uuid4().hex[:8]}")
    redactor = Redactor(text_patterns=profile.redaction_text_patterns)
    surface = PlaywrightWebSurface(
        settings,
        evidence,
        headless=True,
        heading_selector=profile.heading_selector,
        mask_selectors=profile.screenshot_mask_selectors,
        redactor=redactor,
        enable_tracing=profile.durable_traces,
    )
    engine = ReplayEngine(
        surface=surface,
        global_policy=PolicyEngine(profile.policy()),
        settings=settings,
        logger=RunLogger(evidence.log_path, redactor, evidence.run_id),
        evidence=evidence,
        redactor=redactor,
    )
    try:
        result = await engine.replay(
            artifact,
            {"operator_id": os.environ.get("MERIDIAN_TELLER_ID", ""), "password": "definitely-wrong", "branch": "MAIN-001", "member_number": "101555"},
        )
    finally:
        await surface.close()
    assert result.status == "business_outcome"
    assert result.code == "BAD_LOGIN"
