"""Offline scripted discovery (test double) exercising the full pipeline:
observe -> decide -> policy -> act -> record -> compile -> replay."""

import json

import pytest

from ui_capabilities.discovery.agent import DiscoveryAgent
from ui_capabilities.discovery.compiler import ArtifactCompiler
from ui_capabilities.discovery.fake_model import RogueModel, ScriptedBalanceModel
from ui_capabilities.discovery.profiles import demo_app_error_rules
from ui_capabilities.models.artifact import InputSpec, InputValueRef

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("demo_state", "cleanup_surface")]

MEMBER_SPEC = InputSpec(
    name="member_id", type="string", sensitive=True, pattern=r"M-\d{5}", description="Member identifier"
)
GOAL = "Look up member M-10001 and return their current savings balance."


def make_agent(harness, model):
    return DiscoveryAgent(
        surface=harness.surface,
        model=model,
        policy=harness.policy,
        settings=harness.settings,
        logger=harness.logger,
        evidence=harness.evidence,
        redactor=harness.redactor,
        handoff=None,
    )


async def test_scripted_discovery_compiles_and_replays_parameterized(demo_server, harness, replay_engine, tmp_path):
    agent = make_agent(harness, ScriptedBalanceModel())
    await harness.surface.start(demo_server)
    outcome = await agent.run(
        goal=GOAL,
        entry_point=demo_server,
        capability_id="member.get_savings_balance",
        input_specs=[MEMBER_SPEC],
        input_bindings={"member_id": "M-10001"},
    )
    assert outcome.status == "success", outcome.reason
    assert outcome.extracted_outputs["savings_balance"].endswith("2540.75")

    compiler = ArtifactCompiler(harness.policy, error_rules_factory=demo_app_error_rules)
    artifact = compiler.compile(outcome.run)
    serialized = artifact.model_dump_json()
    assert "M-10001" not in serialized
    assert "2540" not in serialized
    fill = next(s for s in artifact.steps if s.action == "fill")
    assert isinstance(fill.value, InputValueRef) and fill.value.name == "member_id"
    assert artifact.contract.outputs[0].name == "savings_balance"

    # discovery evidence log exists and is redacted
    log_text = harness.evidence.log_path.read_text()
    assert "discovery_succeeded" in log_text
    assert "M-10001" not in log_text
    assert "2540.75" not in log_text

    # the discovered artifact replays deterministically for a DIFFERENT member
    await harness.surface.close()
    result = await replay_engine().replay(artifact, {"member_id": "M-10003"})
    assert result.status == "success", getattr(result, "observed", result)
    assert result.outputs["savings_balance"] == pytest.approx(87.12)


async def test_rogue_model_navigation_blocked_before_surface_executes(demo_server, harness):
    agent = make_agent(harness, RogueModel())
    await harness.surface.start(demo_server)
    outcome = await agent.run(
        goal=GOAL,
        entry_point=demo_server,
        capability_id="member.get_savings_balance",
        input_specs=[MEMBER_SPEC],
        input_bindings={"member_id": "M-10001"},
    )
    # the off-domain action was recorded as blocked...
    blocked = [s for s in outcome.run.steps if not s.policy.allowed]
    assert blocked and blocked[0].policy.code == "DOMAIN_BLOCKED"
    assert blocked[0].result is None  # never executed
    # ...and the browser never left the demo app
    assert harness.surface.current_url().startswith(demo_server)
    # the run then escalated rather than proceeding
    assert outcome.status in ("escalated", "failed")
    log = [json.loads(line) for line in harness.evidence.log_path.read_text().splitlines()]
    assert any(e["event"] == "policy_blocked" for e in log)
