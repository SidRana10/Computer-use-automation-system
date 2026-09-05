"""Artifact-scoped escalation routing.

MERIDIAN enforces supervisor gating *after* submit: a teller reaches an
"Authorization Required" page. The taxonomy still calls that a hard failure —
automation genuinely cannot proceed — while the capability's own policy decides
that a person must take it over. Routing is per capability, so the same detected
condition stays an ordinary failure for every capability that has not opted in.
"""

import uuid

from tests.fixtures.factories import make_balance_artifact
from tests.fixtures.fakes import FakeSurface
from ui_capabilities.config import Settings
from ui_capabilities.models.artifact import ErrorRule, StepSpec
from ui_capabilities.models.conditions import ConditionKind, ConditionSpec
from ui_capabilities.models.errors import ErrorClassification, RiskLevel
from ui_capabilities.models.targets import LocatorKind, LocatorStrategy, TargetDescriptor
from ui_capabilities.observability.evidence import EvidenceManager
from ui_capabilities.observability.logger import RunLogger
from ui_capabilities.policy.config import PolicyConfig
from ui_capabilities.policy.engine import PolicyEngine
from ui_capabilities.policy.redaction import Redactor
from ui_capabilities.replay.engine import ReplayEngine

ENTRY = "http://127.0.0.1:8001"
DENIED = "Operator profile teller1 is not authorized to perform this function."
SUPERVISOR_REQUIRED = "SUPERVISOR_REQUIRED"


def _artifact(escalate_on: list[str]):
    base = make_balance_artifact(ENTRY)
    rule = ErrorRule(
        code=SUPERVISOR_REQUIRED,
        classification=ErrorClassification.HARD_FAILURE,
        when=[ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="is not authorized to perform this function")],
        caller_message="MERIDIAN requires a supervisor profile for this function.",
    )
    step = StepSpec(
        id="s_continue",
        name="Continue",
        action="click",
        target=TargetDescriptor(
            description="button 'Continue'",
            strategies=[LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Continue")],
        ),
        risk=RiskLevel.SAFE,
        checkpoint_after=[ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="CONFIRM ACCOUNT HOLD")],
    )
    return base.model_copy(
        update={
            "target": base.target.model_copy(update={"app_fingerprint": {}}),
            "preconditions": [],
            "steps": [step],
            "contract": base.contract.model_copy(update={"outputs": []}),
            "success_conditions": [ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value=DENIED)],
            "error_rules": [rule],
            "policy": base.policy.model_copy(update={"escalate_on_codes": escalate_on}),
        }
    )


def _engine(tmp_path, surface, handoff=None):
    settings = Settings(evidence_dir=tmp_path / "evidence")
    run_id = f"test-{uuid.uuid4().hex[:8]}"
    evidence = EvidenceManager(settings.evidence_dir, run_id)
    redactor = Redactor()
    policy = PolicyConfig(
        allowed_domains=["127.0.0.1"],
        allowed_ports=[8001],
        allowed_route_patterns=["/", "/members/**"],
        allowed_actions=["navigate", "click", "fill", "select", "extract", "wait_for", "assert", "wait"],
    )
    return ReplayEngine(
        surface=surface,
        global_policy=PolicyEngine(policy),
        settings=settings,
        logger=RunLogger(evidence.log_path, redactor, run_id),
        evidence=evidence,
        redactor=redactor,
        handoff=handoff,
    )


async def test_opted_in_capability_escalates_the_detected_state(tmp_path):
    surface = FakeSurface(tmp_path, page_text=DENIED, url=f"{ENTRY}/members/M-10001/accounts")
    result = await _engine(tmp_path, surface).replay(_artifact([SUPERVISOR_REQUIRED]), {"member_id": "M-10001"})
    assert result.status == "escalated"
    assert result.code == SUPERVISOR_REQUIRED
    assert "supervisor" in result.message.lower()


async def test_same_condition_is_an_ordinary_failure_without_opt_in(tmp_path):
    """A 403 must not mean "escalate" for every capability."""
    surface = FakeSurface(tmp_path, page_text=DENIED, url=f"{ENTRY}/members/M-10001/accounts")
    result = await _engine(tmp_path, surface).replay(_artifact([]), {"member_id": "M-10001"})
    assert result.status == "failure"
    assert result.code == SUPERVISOR_REQUIRED


async def test_escalation_never_bypasses_the_gate(tmp_path):
    """Escalating must not click on through: no further action is dispatched."""
    surface = FakeSurface(tmp_path, page_text=DENIED, url=f"{ENTRY}/members/M-10001/accounts")
    await _engine(tmp_path, surface).replay(_artifact([SUPERVISOR_REQUIRED]), {"member_id": "M-10001"})
    assert len([a for a in surface.executed if a.kind == "click"]) == 1


def test_escalate_on_codes_is_artifact_scoped_only():
    """It lives on the artifact's policy block, not on global policy."""
    assert "escalate_on_codes" not in PolicyConfig.model_fields
    from ui_capabilities.models.artifact import CapabilityPolicy

    assert CapabilityPolicy.model_fields["escalate_on_codes"].default == []
