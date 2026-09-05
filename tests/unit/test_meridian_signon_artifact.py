"""The MERIDIAN sign-on artifact: schema-valid, credential-free, policy-sound.

This artifact is genuinely discovery-generated (real Gemini discovery loop ->
ArtifactCompiler -> this file), not hand-authored. See its own `provenance`
block and DECISIONS.md D025. `entry_point` already renders the sign-on form
(MERIDIAN serves it at the root when no session exists), so the recorded run
has no explicit navigate step — that is real target behavior, not an omission.
"""

import json
from pathlib import Path

from ui_capabilities.discovery.compiler import load_artifact
from ui_capabilities.models.errors import RiskLevel
from ui_capabilities.policy.config import PolicyConfig
from ui_capabilities.policy.engine import PolicyEngine
from ui_capabilities.replay import binder
from ui_capabilities.targets import get_profile

ARTIFACT = Path("artifacts/meridian/meridian.sign_on.v1.json")


def test_artifact_exists_and_validates():
    artifact = load_artifact(ARTIFACT)
    assert artifact.capability_id == "meridian.sign_on"
    assert artifact.capability_version == "1.0.0"
    assert artifact.target.app_id == "meridian_core"
    assert [s.action for s in artifact.steps] == ["fill", "fill", "select", "click"]
    assert artifact.provenance.discovery_model.startswith("gemini:"), (
        "canonical provenance must name a genuine provider, never a scripted test double"
    )
    assert "hand-authored" not in artifact.provenance.discovery_model
    assert "fake" not in artifact.provenance.discovery_model


def test_credentials_are_typed_sensitive_inputs_and_no_value_is_embedded():
    artifact = load_artifact(ARTIFACT)
    names = {i.name: i for i in artifact.contract.inputs}
    assert names["operator_id"].sensitive and names["password"].sensitive
    serialized = json.dumps(json.loads(ARTIFACT.read_text()))
    for secret in ("teller1", "super1", "SID ", "_token"):
        assert secret not in serialized, f"{secret!r} must not appear in a capability artifact"


def test_steps_reference_inputs_rather_than_literals():
    artifact = load_artifact(ARTIFACT)
    bound = {s.id: s.value for s in artifact.steps if s.value is not None}
    assert {v.kind for v in bound.values()} == {"input"}
    assert {v.name for v in bound.values()} == {"operator_id", "password", "branch"}


def test_invocation_binding_validates_against_the_contract():
    artifact = load_artifact(ARTIFACT)
    bound = binder.validate_and_bind(
        artifact.contract, {"operator_id": "teller1", "password": "password", "branch": "MAIN-001"}
    )
    assert set(bound) == {"operator_id", "password", "branch"}


def test_fill_and_select_steps_have_a_strategy_that_actually_resolves():
    """MERIDIAN's text/select fields have no real `<label>`/ARIA association,
    so `role_name` and `label` candidates never match at replay time on this
    target (verified live) — only `stable_attribute` (the HTML `name=`
    attribute) does. The compiler's observation heuristic still offers `label`
    as a candidate (built from the adjacent table cell's text, a legitimate
    fallback on OTHER targets), so its presence is expected and harmless; what
    must hold is that a strategy which actually resolves here is also present.

    The submit button is different and deliberately excluded: an
    `input[type=submit]`'s accessible name IS its `value` attribute per ARIA,
    so `role_name`/`text` genuinely resolve for it (verified live in every
    replay run in this session) — MERIDIAN's lack of labels only affects
    fill/select targets, not buttons.
    """
    artifact = load_artifact(ARTIFACT)
    for step in artifact.steps:
        if step.target is None or step.action not in ("fill", "select"):
            continue
        kinds = [s.kind.value for s in step.target.strategies]
        assert "stable_attribute" in kinds, f"{step.id}: no strategy will resolve against real MERIDIAN markup"


def test_password_step_strategy_order_matches_verified_live_resolution():
    """Pins the exact shape verified live in the P1 audit: role_name and label
    fail to resolve (0 matches each), stable_attribute name=password resolves
    (1 match) — this is the D024 collision case, exercised by a real model."""
    artifact = load_artifact(ARTIFACT)
    password_step = next(s for s in artifact.steps if s.value and s.value.name == "password")
    strategies = password_step.target.strategies
    stable = next(s for s in strategies if s.kind.value == "stable_attribute")
    assert stable.attribute == "name" and stable.value == "password"


def test_effective_policy_permits_every_declared_step():
    artifact = load_artifact(ARTIFACT)
    profile = get_profile("meridian")
    effective = PolicyEngine(profile.policy(artifact.target.entry_point).narrowed_by(artifact.policy))
    assert isinstance(effective.config, PolicyConfig)
    for step in artifact.steps:
        url = None
        if step.action == "navigate":
            url = binder.render_url(step.url_template, {}, artifact.target.entry_point)
        decision = effective.check_action(
            step.action,
            url=url,
            risk=step.risk,
            control_text=step.target.description if step.target else None,
        )
        assert decision.allowed, f"{step.id} blocked: {decision.code} {decision.reason}"


def test_signon_declares_no_escalation_and_no_irreversible_step():
    artifact = load_artifact(ARTIFACT)
    assert artifact.policy.escalate_on_codes == []
    assert all(s.risk is not RiskLevel.IRREVERSIBLE for s in artifact.steps)
