from pathlib import Path

import pytest

from tests.fixtures.factories import make_balance_artifact
from ui_capabilities.discovery.compiler import load_artifact
from ui_capabilities.models.artifact import InputValueRef, LiteralValue
from ui_capabilities.replay import binder

ENTRY = "http://127.0.0.1:8001/"
MERIDIAN_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "meridian"


def contract():
    return make_balance_artifact(ENTRY).contract


def test_bind_ok():
    bound = binder.validate_and_bind(contract(), {"member_id": "M-10003"})
    assert bound == {"member_id": "M-10003"}


def test_missing_required_input_rejected():
    with pytest.raises(binder.InvocationError, match="missing required"):
        binder.validate_and_bind(contract(), {})


def test_unknown_input_rejected():
    with pytest.raises(binder.InvocationError, match="unknown input"):
        binder.validate_and_bind(contract(), {"member_id": "M-10003", "extra": "x"})


def test_pattern_mismatch_rejected_before_any_browser_action():
    with pytest.raises(binder.InvocationError, match="pattern"):
        binder.validate_and_bind(contract(), {"member_id": "BAD"})


def _optional_string_contract():
    from ui_capabilities.models.artifact import CapabilityContract, InputSpec

    return CapabilityContract(
        inputs=[
            InputSpec(name="member_id", type="string", description="required id"),
            InputSpec(name="memo", type="string", required=False, description="optional memo"),
        ],
        outputs=[],
    )


def test_omitted_optional_string_binds_empty_string():
    """A step may unconditionally reference an optional field (`Fill Memo`,
    `Fill Notes`) — omitting it must not leave it unbound, or
    `resolve_value` raises 'was not bound' before any browser action."""
    bound = binder.validate_and_bind(_optional_string_contract(), {"member_id": "M-10003"})
    assert bound == {"member_id": "M-10003", "memo": ""}


def test_explicit_empty_optional_string_binds_empty_string():
    bound = binder.validate_and_bind(_optional_string_contract(), {"member_id": "M-10003", "memo": ""})
    assert bound == {"member_id": "M-10003", "memo": ""}


def test_supplied_optional_string_preserves_stripped_value():
    bound = binder.validate_and_bind(
        _optional_string_contract(), {"member_id": "M-10003", "memo": "  pay rent  "}
    )
    assert bound["memo"] == "pay rent"


def test_type_validation():
    from ui_capabilities.models.artifact import CapabilityContract, InputSpec

    c = CapabilityContract(inputs=[InputSpec(name="n", type="integer", description="")], outputs=[])
    with pytest.raises(binder.InvocationError, match="integer"):
        binder.validate_and_bind(c, {"n": "abc"})
    assert binder.validate_and_bind(c, {"n": "42"}) == {"n": "42"}


def test_resolve_value_input_ref_and_literal():
    assert binder.resolve_value(InputValueRef(name="member_id"), {"member_id": "M-10001"}) == "M-10001"
    assert binder.resolve_value(LiteralValue(value="Holiday Savings"), {}) == "Holiday Savings"
    with pytest.raises(binder.InvocationError, match="not bound"):
        binder.resolve_value(InputValueRef(name="ghost"), {})


def test_render_url_template():
    url = binder.render_url("/members/{member_id}/accounts", {"member_id": "M-10001"}, ENTRY)
    assert url == "http://127.0.0.1:8001/members/M-10001/accounts"
    with pytest.raises(binder.InvocationError, match="unbound"):
        binder.render_url("/members/{ghost}", {}, ENTRY)


def _fill_step(artifact, output_name: str):
    for step in artifact.steps:
        if step.action == "fill" and getattr(step.value, "name", None) == output_name:
            return step
    raise AssertionError(f"no fill step found for {output_name!r}")


def test_funds_transfer_without_memo_binds_empty_string_for_its_fill_step():
    """Reproduces the confirmed live bug: `meridian.funds_transfer` has an
    unconditional `Fill Memo` step even though `memo` is optional. Before the
    fix, omitting `memo` left it unbound and `resolve_value` raised "step
    references input 'memo' which was not bound"."""
    artifact = load_artifact(MERIDIAN_ARTIFACTS_DIR / "meridian.funds_transfer.v1.json")
    bound = binder.validate_and_bind(
        artifact.contract,
        {
            "operator_id": "teller1",
            "password": "s3cret",
            "branch": "MAIN-001",
            "member_number": "100234",
            "from_share": "100234-S0001-12",
            "to_share": "100234-MMKT-21",
            "amount": "1.00",
        },
    )
    assert bound["memo"] == ""
    step = _fill_step(artifact, "memo")
    assert binder.resolve_value(step.value, bound) == ""


def test_funds_transfer_with_memo_supplied_passes_through():
    artifact = load_artifact(MERIDIAN_ARTIFACTS_DIR / "meridian.funds_transfer.v1.json")
    bound = binder.validate_and_bind(
        artifact.contract,
        {
            "operator_id": "teller1",
            "password": "s3cret",
            "branch": "MAIN-001",
            "member_number": "100234",
            "from_share": "100234-S0001-12",
            "to_share": "100234-MMKT-21",
            "amount": "1.00",
            "memo": "  rent  ",
        },
    )
    assert bound["memo"] == "rent"
    step = _fill_step(artifact, "memo")
    assert binder.resolve_value(step.value, bound) == "rent"


def test_place_hold_without_notes_binds_empty_string_for_its_fill_step():
    """Reproduces the confirmed live bug for `meridian.place_hold`: an
    unconditional `Fill Notes` step even though `notes` is optional."""
    artifact = load_artifact(MERIDIAN_ARTIFACTS_DIR / "meridian.place_hold.v1.json")
    bound = binder.validate_and_bind(
        artifact.contract,
        {
            "operator_id": "teller1",
            "password": "s3cret",
            "branch": "MAIN-001",
            "member_number": "100234",
            "share": "100234-S0001-12",
            "reason_code": "FRAUD",
        },
    )
    assert bound["notes"] == ""
    step = _fill_step(artifact, "notes")
    assert binder.resolve_value(step.value, bound) == ""


def test_place_hold_with_notes_supplied_passes_through():
    artifact = load_artifact(MERIDIAN_ARTIFACTS_DIR / "meridian.place_hold.v1.json")
    bound = binder.validate_and_bind(
        artifact.contract,
        {
            "operator_id": "teller1",
            "password": "s3cret",
            "branch": "MAIN-001",
            "member_number": "100234",
            "share": "100234-S0001-12",
            "reason_code": "FRAUD",
            "notes": "  suspected fraud  ",
        },
    )
    assert bound["notes"] == "suspected fraud"
    step = _fill_step(artifact, "notes")
    assert binder.resolve_value(step.value, bound) == "suspected fraud"


# One representative, valid business invocation per MERIDIAN capability —
# used only to prove the binder fix generalizes: every step across all 7
# artifacts that references an input by name must resolve against `bound`,
# not just the two capabilities with a known-optional field (memo, notes).
_SAMPLE_INPUTS: dict[str, dict[str, str]] = {
    "meridian.sign_on": {},
    "meridian.member_inquiry": {"search_mode": "number", "search_value": "100234"},
    "meridian.get_member_balances": {"member_number": "100234"},
    "meridian.funds_transfer": {
        "member_number": "100234",
        "from_share": "100234-S0001-12",
        "to_share": "100234-MMKT-21",
        "amount": "1.00",
    },
    "meridian.open_share": {"member_number": "100234", "share_type": "MMKT", "initial_deposit": "50.00"},
    "meridian.update_member_info": {
        "member_number": "100234",
        "email": "ada@example.com",
        "phone": "555-1234",
        "address": "1 Main St",
    },
    "meridian.place_hold": {"member_number": "100234", "share": "100234-S0001-12", "reason_code": "FRAUD"},
}
_SERVER_SUPPLIED = {"operator_id": "teller1", "password": "s3cret", "branch": "MAIN-001"}


@pytest.mark.parametrize("capability_id", sorted(_SAMPLE_INPUTS))
def test_every_meridian_capability_binds_and_resolves_all_step_inputs(capability_id):
    """Goal 4 regression guard: for every one of the 7 committed artifacts, a
    valid business invocation must bind cleanly and every step that
    references an input by name must resolve against the bound values —
    the exact failure class (`resolve_value` raising "was not bound") that
    the memo/notes bug was one instance of, checked across the whole
    catalog rather than only the two capabilities known to be affected."""
    artifact = load_artifact(MERIDIAN_ARTIFACTS_DIR / f"{capability_id}.v1.json")
    provided = {**_SERVER_SUPPLIED, **_SAMPLE_INPUTS[capability_id]}
    bound = binder.validate_and_bind(artifact.contract, provided)
    for step in artifact.steps:
        if isinstance(step.value, InputValueRef):
            binder.resolve_value(step.value, bound)  # must not raise


def test_coerce_output_money_and_types():
    assert binder.coerce_output("b", "$2,540.75", "decimal") == pytest.approx(2540.75)
    assert binder.coerce_output("n", "42", "integer") == 42
    assert binder.coerce_output("f", "yes", "boolean") is True
    with pytest.raises(binder.OutputCoercionError):
        binder.coerce_output("b", "no balance", "decimal")
