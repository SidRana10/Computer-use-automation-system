from datetime import datetime, timezone

import pytest

from ui_capabilities.discovery.compiler import ArtifactCompiler
from ui_capabilities.discovery.profiles import demo_app_error_rules
from ui_capabilities.discovery.recorder import RecordedRun, RecordedStep, StateSnapshot
from ui_capabilities.models.actions import (
    ClickAction,
    ExtractAction,
    FillAction,
    SuggestedCondition,
    ValueSource,
)
from ui_capabilities.models.artifact import InputSpec, InputValueRef
from ui_capabilities.models.errors import CompileError
from ui_capabilities.models.targets import LocatorKind, LocatorStrategy
from ui_capabilities.policy.config import default_demo_policy
from ui_capabilities.policy.engine import PolicyDecision, PolicyEngine
from ui_capabilities.surfaces.base import ActionResult, ObservedElement

ENTRY = "http://127.0.0.1:8001/"
NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)
ALLOWED = PolicyDecision(allowed=True)
OK = ActionResult(ok=True)


def snap(path: str, heading: str | None, fp: str) -> StateSnapshot:
    return StateSnapshot(url=f"http://127.0.0.1:8001{path}", path=path, title="Northstar Credit Union — Member Servicing Console (Demo)", heading=heading, fingerprint=fp)


def element(kind: str, name: str, strategies: list[LocatorStrategy], **kwargs) -> ObservedElement:
    return ObservedElement(ref="e1", kind=kind, tag="x", accessible_name=name, candidate_strategies=strategies, **kwargs)


def make_run(fill_value_source: ValueSource | None = None, strategies: list[LocatorStrategy] | None = None) -> RecordedRun:
    search_field_strategies = strategies if strategies is not None else [
        LocatorStrategy(kind=LocatorKind.LABEL, value="Member ID"),
        LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="member_id"),
    ]
    steps = [
        RecordedStep(
            index=0,
            before=snap("/", "Dashboard", "f0"),
            action=ClickAction(element_ref="e1", rationale_summary="open search"),
            element=element("link", "Member Search", [LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="link", name="Member Search")]),
            policy=ALLOWED,
            result=OK,
            after=snap("/members/search", "Member Search", "f1"),
            started_at=NOW,
        ),
        RecordedStep(
            index=1,
            before=snap("/members/search", "Member Search", "f1"),
            action=FillAction(
                element_ref="e1",
                value_source=fill_value_source or ValueSource(input_name="member_id"),
                rationale_summary="enter id",
            ),
            element=element("textbox", "Member ID", search_field_strategies),
            policy=ALLOWED,
            result=OK,
            after=snap("/members/search", "Member Search", "f1b"),
            started_at=NOW,
        ),
        RecordedStep(
            index=2,
            before=snap("/members/search", "Member Search", "f1b"),
            action=ClickAction(element_ref="e1", rationale_summary="search"),
            element=element("button", "Search", [LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Search")]),
            policy=ALLOWED,
            result=OK,
            after=snap("/members/M-10001", "Member Summary", "f2"),
            started_at=NOW,
        ),
        RecordedStep(
            index=3,
            before=snap("/members/M-10001", "Member Summary", "f2"),
            action=ClickAction(element_ref="e1", rationale_summary="accounts"),
            element=element("link", "Accounts", [LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="link", name="Accounts")]),
            policy=ALLOWED,
            result=OK,
            after=snap("/members/M-10001/accounts", "Accounts", "f3"),
            started_at=NOW,
        ),
        RecordedStep(
            index=4,
            before=snap("/members/M-10001/accounts", "Accounts", "f3"),
            action=ExtractAction(element_ref="e1", output_name="savings_balance", output_type="decimal", rationale_summary="read"),
            element=element("cell", None, [LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="id", value="acct-sav-balance")], id_attr="acct-sav-balance"),
            policy=ALLOWED,
            result=ActionResult(ok=True, extracted_text="$2,540.75"),
            after=snap("/members/M-10001/accounts", "Accounts", "f3"),
            started_at=NOW,
        ),
    ]
    return RecordedRun(
        run_id="disc-test",
        goal="Look up member M-10001 and return their current savings balance.",
        capability_id="member.get_savings_balance",
        entry_point=ENTRY,
        target_app_name="Northstar Demo",
        model_name="fake",
        input_specs=[InputSpec(name="member_id", type="string", sensitive=True, pattern=r"M-\d{5}", description="Member identifier")],
        input_bindings={"member_id": "M-10001"},
        steps=steps,
        success=True,
        done_summary="balance extracted",
        suggested_success_condition=SuggestedCondition(kind="text_present", value="Savings"),
        final_state=snap("/members/M-10001/accounts", "Accounts", "f3"),
        app_fingerprint={"app_title": "Northstar Credit Union", "build_marker": "4.2.19-legacy"},
        finished_at=NOW,
    )


def compiler() -> ArtifactCompiler:
    return ArtifactCompiler(PolicyEngine(default_demo_policy(ENTRY)), error_rules_factory=demo_app_error_rules)


def test_compile_parameterizes_and_validates():
    artifact = compiler().compile(make_run())
    serialized = artifact.model_dump_json()
    # the concrete sensitive invocation value never appears anywhere
    assert "M-10001" not in serialized
    # goal text is parameterized, not dropped
    assert "{member_id}" in artifact.description
    # fill step references the declared input
    fill = next(s for s in artifact.steps if s.action == "fill")
    assert isinstance(fill.value, InputValueRef) and fill.value.name == "member_id"
    # checkpoints derived from navigation steps are parameterized globs
    search_click = next(s for s in artifact.steps if s.name.startswith("Click Search"))
    assert any(c.value == "/members/*" for c in search_click.checkpoint_after)
    assert any(c.value == "Member Summary" for c in search_click.checkpoint_after)
    # typed output wired to the extract step
    assert artifact.contract.outputs[0].name == "savings_balance"
    assert artifact.contract.outputs[0].type == "decimal"
    assert artifact.contract.outputs[0].source_step_id == next(s.id for s in artifact.steps if s.action == "extract")
    # extracted sensitive value is not embedded either
    assert "2540" not in serialized
    # provenance/version/fingerprint present
    assert artifact.provenance.discovery_run_id == "disc-test"
    assert artifact.target.app_fingerprint["build_marker"] == "4.2.19-legacy"
    assert artifact.error_rules  # app-profile rules attached


def test_compile_maps_literal_matching_binding_to_input_ref():
    run = make_run(fill_value_source=ValueSource(literal="M-10001"))
    artifact = compiler().compile(run)
    fill = next(s for s in artifact.steps if s.action == "fill")
    assert isinstance(fill.value, InputValueRef)
    assert "M-10001" not in artifact.model_dump_json()


def test_compile_fails_loudly_on_unparameterizable_sensitive_literal():
    run = make_run(fill_value_source=ValueSource(literal="prefix-M-10001-suffix"))
    with pytest.raises(CompileError, match="sensitive"):
        compiler().compile(run)


def test_compile_fails_without_durable_locators():
    run = make_run(strategies=[])
    with pytest.raises(CompileError, match="durable locator"):
        compiler().compile(run)


def test_compile_refuses_unsuccessful_run():
    run = make_run()
    run.success = False
    with pytest.raises(CompileError, match="did not succeed"):
        compiler().compile(run)


def test_recorded_run_serialization_excludes_bindings():
    run = make_run()
    assert "M-10001" not in str(run.model_dump().get("input_bindings", ""))
    assert "input_bindings" not in run.model_dump_json()
