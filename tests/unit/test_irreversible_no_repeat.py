"""Once a risky/irreversible action is dispatched, automation never repeats it.

MERIDIAN's `/transfer/post` and `/hold/post` are real writes. If the response is
lost or the landed page is unexpected, the effect may already exist on the host.
Retrying would post the transaction twice, so replay may only re-observe,
classify, stop, or escalate.
"""

import uuid

import pytest

from tests.fixtures.factories import make_balance_artifact
from tests.fixtures.fakes import FakeSurface
from ui_capabilities.config import Settings
from ui_capabilities.models.artifact import CapabilityArtifact, ErrorRule, StepSpec
from ui_capabilities.models.conditions import ConditionKind, ConditionSpec
from ui_capabilities.models.errors import ErrorClassification, FailureCode, RiskLevel
from ui_capabilities.models.targets import LocatorKind, LocatorStrategy, TargetDescriptor
from ui_capabilities.observability.evidence import EvidenceManager
from ui_capabilities.observability.logger import RunLogger
from ui_capabilities.policy.config import PolicyConfig
from ui_capabilities.policy.engine import PolicyEngine
from ui_capabilities.policy.redaction import Redactor
from ui_capabilities.replay.engine import ReplayEngine

ENTRY = "http://127.0.0.1:8001"
MAINTENANCE = "The host is temporarily unavailable"


def _post_step(risk: RiskLevel) -> StepSpec:
    return StepSpec(
        id="s_post",
        name="Post Transfer",
        action="click",
        target=TargetDescriptor(
            description="button 'Post Transfer'",
            strategies=[LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Post Transfer")],
        ),
        risk=risk,
        checkpoint_after=[ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="TRANSACTION COMPLETE")],
    )


def _artifact(risk: RiskLevel, *, escalate_on: list[str] | None = None) -> CapabilityArtifact:
    base = make_balance_artifact(ENTRY)
    recoverable = ErrorRule(
        code="MAINTENANCE_WINDOW",
        classification=ErrorClassification.RECOVERABLE,
        when=[ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value=MAINTENANCE)],
        recovery=[],
        max_attempts=3,
        caller_message="maintenance",
    )
    # Effective policy is the strictest combination of global and artifact
    # policy, so the artifact must also permit the unattended write for the
    # no-repeat rule (rather than the approval gate) to be what is exercised.
    policy = base.policy.model_copy(
        update={
            "escalate_on_codes": escalate_on or [],
            "require_human_for": [],
            "max_unattended_risk": RiskLevel.IRREVERSIBLE,
        }
    )
    # the fake surface reports a synthetic title; fingerprint verification is
    # covered by its own tests and is not what these assert
    target = base.target.model_copy(update={"app_fingerprint": {}})
    return base.model_copy(
        update={
            "target": target,
            "preconditions": [],
            "success_conditions": [ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value=MAINTENANCE)],
            "steps": [_post_step(risk)],
            "contract": base.contract.model_copy(update={"outputs": []}),
            "error_rules": [recoverable],
            "risk_level": RiskLevel.IRREVERSIBLE if risk is RiskLevel.IRREVERSIBLE else base.risk_level,
            "policy": policy,
        }
    )


def _engine(tmp_path, surface, handoff=None) -> ReplayEngine:
    settings = Settings(evidence_dir=tmp_path / "evidence", max_recovery_attempts=3)
    run_id = f"test-{uuid.uuid4().hex[:8]}"
    evidence = EvidenceManager(settings.evidence_dir, run_id)
    redactor = Redactor()
    policy = PolicyConfig(
        allowed_domains=["127.0.0.1"],
        allowed_ports=[8001],
        allowed_route_patterns=["/", "/members/**"],
        allowed_actions=["navigate", "click", "fill", "select", "extract", "wait_for", "assert", "wait"],
        max_unattended_risk=RiskLevel.IRREVERSIBLE,   # allow the write unattended
        require_human_for=[],                          # so the no-repeat rule is what is under test
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


@pytest.mark.parametrize("risk", [RiskLevel.RISKY, RiskLevel.IRREVERSIBLE])
async def test_dispatched_write_is_never_dispatched_twice(tmp_path, risk):
    surface = FakeSurface(tmp_path, page_text=MAINTENANCE, url=f"{ENTRY}/members/M-10001/accounts")
    result = await _engine(tmp_path, surface).replay(_artifact(risk), {"member_id": "M-10001"})

    clicks = [a for a in surface.executed if a.kind == "click"]
    assert len(clicks) == 1, f"the write was dispatched {len(clicks)} times"
    assert result.status == "failure"
    assert result.code == FailureCode.IRREVERSIBLE_OUTCOME_UNCERTAIN
    assert "will not repeat it" in result.observed


async def test_safe_step_still_retries_normally(tmp_path):
    """The invariant must not disable ordinary recovery for non-write steps."""
    surface = FakeSurface(tmp_path, page_text=MAINTENANCE, url=f"{ENTRY}/members/M-10001/accounts")
    result = await _engine(tmp_path, surface).replay(_artifact(RiskLevel.SAFE), {"member_id": "M-10001"})

    clicks = [a for a in surface.executed if a.kind == "click"]
    assert len(clicks) > 1, "a safe step should still be retried within its recovery budget"
    assert result.status == "failure"
    assert result.code == FailureCode.RETRY_EXHAUSTED


async def test_uncertain_write_preserves_evidence(tmp_path):
    surface = FakeSurface(tmp_path, page_text=MAINTENANCE, url=f"{ENTRY}/members/M-10001/accounts")
    result = await _engine(tmp_path, surface).replay(_artifact(RiskLevel.IRREVERSIBLE), {"member_id": "M-10001"})
    assert result.evidence, "an uncertain write must leave evidence behind"
    assert surface.dom_snapshots, "a DOM snapshot must be captured for reconciliation"
