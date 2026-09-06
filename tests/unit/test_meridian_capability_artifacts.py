"""Cross-cutting checks over every committed MERIDIAN capability artifact:
genuine discovery provenance, no seed member numbers, no operator
credentials, and schema validity. One shared test protects all seven rather
than duplicating the same assertions per capability file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ui_capabilities.discovery.compiler import load_artifact

ARTIFACT_DIR = Path("artifacts/meridian")
REQUIRED_CAPABILITIES = {
    "meridian.sign_on",
    "meridian.member_inquiry",
    "meridian.get_member_balances",
    "meridian.funds_transfer",
    "meridian.open_share",
    "meridian.update_member_info",
    "meridian.place_hold",
}

# Public demo seed data (never a real secret) that must still never appear
# literally in a compiled artifact: these are invocation-specific runtime
# values (a search example, not a declared parameter) and must be
# parameterized away, exactly like any other bound input.
SEED_MEMBER_NUMBERS = ("100234", "100987", "101555", "102777", "103001")
DEMO_CREDENTIAL_VALUES = ("teller1", "super1")


def _artifact_paths() -> list[Path]:
    if not ARTIFACT_DIR.exists():
        return []
    return sorted(ARTIFACT_DIR.glob("*.v*.json"))


@pytest.fixture(scope="module")
def artifacts() -> dict[str, Path]:
    paths = _artifact_paths()
    if not paths:
        pytest.skip("no MERIDIAN artifacts present")
    by_id: dict[str, Path] = {}
    for path in paths:
        artifact = load_artifact(path)
        by_id[artifact.capability_id] = path
    return by_id


def test_all_seven_required_capabilities_are_present(artifacts):
    missing = REQUIRED_CAPABILITIES - set(artifacts)
    assert not missing, f"missing MERIDIAN capability artifacts: {sorted(missing)}"


def test_every_artifact_has_genuine_discovery_provenance(artifacts):
    for capability_id, path in artifacts.items():
        artifact = load_artifact(path)
        model = artifact.provenance.discovery_model
        assert model.startswith("gemini:") or model.startswith("anthropic:"), (
            f"{capability_id}: provenance.discovery_model {model!r} does not name a genuine provider "
            "(hand-authored/scripted artifacts are not valid production capabilities)"
        )
        assert "fake" not in model and "hand-authored" not in model, capability_id
        assert artifact.target.app_id == "meridian_core"


def test_no_seed_member_number_or_demo_credential_is_embedded(artifacts):
    for capability_id, path in artifacts.items():
        serialized = json.dumps(json.loads(path.read_text()))
        for value in SEED_MEMBER_NUMBERS + DEMO_CREDENTIAL_VALUES:
            assert value not in serialized, (
                f"{capability_id}: {value!r} (invocation-specific runtime data) leaked into the artifact"
            )


def test_every_artifact_error_rules_match_the_current_profile(artifacts):
    """`error_rules` are attached from the target profile at compile time
    (D008) and take no run input (D022) — they must always match the current
    factory output exactly, or a committed artifact is replaying against a
    stale rule set (found live: a rule added after `meridian.open_share` was
    compiled did not apply until the artifact's `error_rules` were re-synced)."""
    from ui_capabilities.targets.meridian import meridian_error_rules

    current_codes = [r.code for r in meridian_error_rules()]
    for capability_id, path in artifacts.items():
        artifact = load_artifact(path)
        assert [r.code for r in artifact.error_rules] == current_codes, capability_id


def test_every_artifact_validates_and_has_at_least_one_step(artifacts):
    for capability_id, path in artifacts.items():
        artifact = load_artifact(path)
        assert artifact.steps, capability_id
        assert artifact.success_conditions, capability_id
        assert artifact.capability_id == capability_id


def test_place_hold_declares_supervisor_required_escalation(artifacts):
    """D034: escalate_on_codes is never set by generic compilation — it is a
    deliberate per-capability policy decision. place_hold is the one
    capability whose supervisor-gated step needs it; sign_on explicitly
    declares none (D025), and no other capability has a supervisor-only step."""
    if "meridian.place_hold" not in artifacts:
        pytest.skip("meridian.place_hold not yet compiled")
    artifact = load_artifact(artifacts["meridian.place_hold"])
    assert artifact.policy.escalate_on_codes == ["SUPERVISOR_REQUIRED"]
    assert artifact.risk_level == "irreversible"


def test_no_password_literal_survives_outside_the_credential_exemption(artifacts):
    """The literal word "password" (the shared demo credential) must never
    appear except as the declared parameter name/description or the one
    narrow `stable_attribute name=password` exemption (D024)."""
    for capability_id, path in artifacts.items():
        blob = json.loads(path.read_text())
        for step in blob.get("steps", []):
            value = step.get("value")
            if value and value.get("kind") == "literal":
                assert "password" not in str(value.get("value", "")), capability_id
