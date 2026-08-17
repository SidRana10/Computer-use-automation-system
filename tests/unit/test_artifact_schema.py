import pytest
from pydantic import ValidationError

from tests.fixtures.factories import make_balance_artifact, make_subaccount_artifact
from ui_capabilities.models.artifact import (
    CapabilityArtifact,
    StepSpec,
)
from ui_capabilities.models.errors import RiskLevel
from ui_capabilities.models.targets import TargetDescriptor

ENTRY = "http://127.0.0.1:8001/"


def test_valid_artifact_round_trips():
    artifact = make_balance_artifact(ENTRY)
    dumped = artifact.model_dump_json()
    loaded = CapabilityArtifact.model_validate_json(dumped)
    assert loaded.capability_id == "member.get_savings_balance"
    assert loaded.steps[1].value.kind == "input"
    assert loaded.contract.outputs[0].type == "decimal"


def test_subaccount_artifact_declares_irreversible_risk():
    artifact = make_subaccount_artifact(ENTRY)
    assert artifact.risk_level == RiskLevel.IRREVERSIBLE
    assert artifact.steps[6].risk == RiskLevel.IRREVERSIBLE


def test_invalid_version_rejected():
    artifact = make_balance_artifact(ENTRY)
    data = artifact.model_dump()
    data["capability_version"] = "1.0"
    with pytest.raises(ValidationError, match="semver"):
        CapabilityArtifact.model_validate(data)


def test_output_must_reference_existing_extract_step():
    artifact = make_balance_artifact(ENTRY)
    data = artifact.model_dump()
    data["contract"]["outputs"][0]["source_step_id"] = "nope"
    with pytest.raises(ValidationError, match="unknown step"):
        CapabilityArtifact.model_validate(data)
    data["contract"]["outputs"][0]["source_step_id"] = "s3_click"
    with pytest.raises(ValidationError, match="not an extract step"):
        CapabilityArtifact.model_validate(data)


def test_step_referencing_undeclared_input_rejected():
    artifact = make_balance_artifact(ENTRY)
    data = artifact.model_dump()
    data["steps"][1]["value"] = {"kind": "input", "name": "not_declared"}
    with pytest.raises(ValidationError, match="undeclared input"):
        CapabilityArtifact.model_validate(data)


def test_targeted_action_requires_target():
    with pytest.raises(ValidationError, match="requires a target"):
        StepSpec(id="x", name="x", action="click")


def test_empty_locator_strategy_chain_rejected():
    with pytest.raises(ValidationError):
        TargetDescriptor(description="x", strategies=[])


def test_irreversible_step_requires_artifact_risk_declaration():
    artifact = make_subaccount_artifact(ENTRY)
    data = artifact.model_dump()
    data["risk_level"] = "safe"
    with pytest.raises(ValidationError, match="irreversible"):
        CapabilityArtifact.model_validate(data)


def test_missing_success_conditions_rejected():
    artifact = make_balance_artifact(ENTRY)
    data = artifact.model_dump()
    data["success_conditions"] = []
    with pytest.raises(ValidationError):
        CapabilityArtifact.model_validate(data)
