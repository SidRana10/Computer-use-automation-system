"""Extract modes and internal captures.

`value` mode exists because a per-transaction token lives in a hidden input and
has no rendered text. `internal` exists so that token can be read and verified
without becoming part of the capability's public contract.
"""

import pytest
from pydantic import ValidationError

from ui_capabilities.models.artifact import (
    CapabilityContract,
    InputSpec,
    OutputSpec,
    StepSpec,
)
from ui_capabilities.models.targets import LocatorKind, LocatorStrategy, TargetDescriptor
from tests.fixtures.factories import make_balance_artifact

ENTRY = "http://127.0.0.1:8001"


def _target(name: str) -> TargetDescriptor:
    return TargetDescriptor(
        description=f"field {name}",
        strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value=name)],
    )


def _token_step() -> StepSpec:
    return StepSpec(
        id="s_token",
        name="Read current transaction token",
        action="extract",
        target=_target("_token"),
        output_name="transaction_token",
        output_type="string",
        extract_mode="value",
        internal=True,
    )


def test_extract_mode_and_internal_are_extract_only():
    with pytest.raises(ValidationError, match="only valid on extract steps"):
        StepSpec(id="s1", name="click", action="click", target=_target("go"), extract_mode="value")
    with pytest.raises(ValidationError, match="only valid on extract steps"):
        StepSpec(id="s1", name="click", action="click", target=_target("go"), internal=True)


def test_internal_extract_needs_no_contract_output():
    artifact = make_balance_artifact(ENTRY)
    artifact = artifact.model_copy(update={"steps": list(artifact.steps) + [_token_step()]})
    artifact.model_validate(artifact.model_dump())  # re-validates cleanly


def test_internal_extract_must_not_publish_its_value():
    """Two independent guards stop an internal capture reaching the contract:
    the output cannot source from an internal step, and an internal step cannot
    name a declared output. Either firing is a correct refusal."""
    artifact = make_balance_artifact(ENTRY)
    data = artifact.model_dump()
    data["steps"].append(_token_step().model_dump())
    data["contract"]["outputs"].append(
        OutputSpec(
            name="transaction_token",
            type="string",
            description="leaked token",
            source_step_id="s_token",
        ).model_dump()
    )
    with pytest.raises(ValidationError, match="internal extract step"):
        type(artifact).model_validate(data)


def test_internal_extract_cannot_reuse_a_declared_output_name():
    """The second guard, reached when the output points at a public step."""
    artifact = make_balance_artifact(ENTRY)
    data = artifact.model_dump()
    published = data["contract"]["outputs"][0]["name"]
    step = _token_step().model_dump()
    step["output_name"] = published
    data["steps"].append(step)
    with pytest.raises(ValidationError, match="must not publish"):
        type(artifact).model_validate(data)


def test_public_extract_must_still_be_declared():
    artifact = make_balance_artifact(ENTRY)
    data = artifact.model_dump()
    step = _token_step().model_dump()
    step["internal"] = False
    data["steps"].append(step)
    with pytest.raises(ValidationError, match="not declared in contract"):
        type(artifact).model_validate(data)


def test_invocation_inputs_cannot_be_json():
    with pytest.raises(ValidationError, match="output-only type"):
        InputSpec(name="shares", type="json", description="not allowed")
    # but outputs can be
    assert OutputSpec(name="shares", type="json", description="ok", source_step_id="s1").type == "json"
    assert CapabilityContract().outputs == []
