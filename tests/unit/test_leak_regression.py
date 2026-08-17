"""Regression tests for the parameterization gap found in genuine Gemini run
disc-81829dead3: the model's DONE proposed a success condition whose value was
the extracted savings balance, which the compiler embedded into
success_conditions (the sensitive-value scanner then correctly refused to
save). Extracted runtime values must never survive into any artifact field —
and the same applies to locator strategies whose identity embeds a bound
sensitive input.
"""

from tests.fixtures.fakes import FakeSurface
from tests.unit.test_compiler import ENTRY, compiler, make_run

import pytest

from ui_capabilities.config import Settings
from ui_capabilities.discovery.agent import DiscoveryAgent
from ui_capabilities.models.actions import DoneAction, SuggestedCondition
from ui_capabilities.models.errors import CompileError
from ui_capabilities.models.targets import LocatorKind, LocatorStrategy
from ui_capabilities.observability.evidence import EvidenceManager
from ui_capabilities.observability.logger import RunLogger
from ui_capabilities.policy.config import default_demo_policy
from ui_capabilities.policy.engine import PolicyEngine
from ui_capabilities.policy.redaction import Redactor
from ui_capabilities.replay import binder


def test_extracted_value_in_suggested_success_condition_is_not_persisted():
    """The exact genuine-run leak: DONE suggested `text_present: <balance>`."""
    run = make_run()
    # the recorded extract in make_run produced "$2,540.75"
    run.suggested_success_condition = SuggestedCondition(kind="text_present", value="$2,540.75")
    artifact = compiler().compile(run)

    serialized = artifact.model_dump_json()
    assert "2540" not in serialized
    assert "M-10001" not in serialized
    # the invocation-specific condition was dropped; structural conditions remain
    assert artifact.success_conditions
    assert all("2540" not in (c.value or "") for c in artifact.success_conditions)
    assert any(c.value == "/members/*/accounts" for c in artifact.success_conditions)
    # the artifact still binds a different member cleanly
    assert binder.validate_and_bind(artifact.contract, {"member_id": "M-10003"}) == {"member_id": "M-10003"}


def test_unformatted_extracted_value_variant_is_also_caught():
    run = make_run()
    run.suggested_success_condition = SuggestedCondition(kind="text_present", value="2540.75")
    artifact = compiler().compile(run)
    assert all("2540" not in (c.value or "") for c in artifact.success_conditions)


def test_locator_strategy_embedding_runtime_value_is_dropped():
    run = make_run()
    run.steps[0].element.candidate_strategies = [
        LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="link", name="Member M-10001 profile"),
        LocatorStrategy(kind=LocatorKind.TEXT, value="Member M-10001 profile"),
        LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="id", value="member-profile-link"),
    ]
    artifact = compiler().compile(run)
    first_click = artifact.steps[0]
    kinds = [s.kind for s in first_click.target.strategies]
    assert kinds == [LocatorKind.STABLE_ATTRIBUTE]
    assert "M-10001" not in artifact.model_dump_json()


def test_compile_fails_loudly_when_only_invocation_dependent_locators_exist():
    run = make_run()
    run.steps[0].element.candidate_strategies = [
        LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="link", name="Member M-10001 profile"),
    ]
    with pytest.raises(CompileError, match="invocation-specific runtime value"):
        compiler().compile(run)


def test_runtime_value_in_target_description_is_scrubbed():
    run = make_run()
    run.steps[0].element.accessible_name = "Open record M-10001"
    run.steps[0].element.candidate_strategies = [
        LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="id", value="open-record-link"),
    ]
    artifact = compiler().compile(run)
    description = artifact.steps[0].target.description
    assert "M-10001" not in description
    assert "{member_id}" in description  # binding parameterized, not blanked


# ------------------------------------------------ agent-side rejection of DONE


def _agent(tmp_path, page_text: str) -> DiscoveryAgent:
    settings = Settings(evidence_dir=tmp_path / "evidence")
    evidence = EvidenceManager(settings.evidence_dir, "verify-test")
    redactor = Redactor()
    return DiscoveryAgent(
        surface=FakeSurface(tmp_path, page_text=page_text),
        model=None,  # not used by _verify_done
        policy=PolicyEngine(default_demo_policy(ENTRY)),
        settings=settings,
        logger=RunLogger(evidence.log_path, redactor, "verify-test"),
        evidence=evidence,
        redactor=redactor,
    )


async def test_verify_done_rejects_condition_embedding_extracted_value(tmp_path):
    agent = _agent(tmp_path, page_text="Accounts Savings $2540.75")
    done = DoneAction(
        success_summary="balance found",
        suggested_success_condition=SuggestedCondition(kind="text_present", value="$2540.75"),
    )
    ok, detail = await agent._verify_done(done, {"member_id": "M-10001"}, {"savings_balance": "$2540.75"})
    assert not ok
    assert "extracted values" in detail

    # differently formatted variants of the same value are also rejected
    done2 = DoneAction(
        success_summary="balance found",
        suggested_success_condition=SuggestedCondition(kind="text_present", value="2,540.75 available"),
    )
    ok2, _ = await agent._verify_done(done2, {"member_id": "M-10001"}, {"savings_balance": "$2540.75"})
    assert not ok2


async def test_verify_done_accepts_stable_ui_condition(tmp_path):
    agent = _agent(tmp_path, page_text="Accounts Savings $2540.75")
    done = DoneAction(
        success_summary="balance found",
        suggested_success_condition=SuggestedCondition(kind="text_present", value="Savings"),
    )
    ok, _ = await agent._verify_done(done, {"member_id": "M-10001"}, {"savings_balance": "$2540.75"})
    assert ok
